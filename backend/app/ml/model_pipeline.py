import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sqlalchemy.orm import Session

from backend.app.config import DATA_DIR, METADATA_DIR, MODELS_DIR
from backend.app.ml.feature_engineering import (
    FEATURE_DEFINITIONS,
    FEATURE_DESC_MAP,
    FEATURE_DISPLAY_MAP,
    FEATURE_NAMES,
    FORBIDDEN_LEAKAGE_COLUMNS,
    compute_account_features,
)
from backend.app.ml.risk_scoring import (
    RISK_SCORING_METHODOLOGY,
    classify_risk_score,
    get_active_thresholds,
    probability_to_normalized_score,
)
from backend.app.models.entities import (
    Account,
    Alert,
    DatasetTrainingMetadata,
    EvidenceItem,
    FeatureSnapshot,
    Investigation,
    InvestigationNote,
    ModelPrediction,
    ModelVersion,
    SyntheticLabel,
    Transaction,
    utcnow,
)
from backend.app.security.audit import record_audit_event

MODEL_LIMITATIONS_STATEMENT = (
    "1. Synthetic Data Disclaimer: This model was trained and evaluated on synthetic financial transaction patterns. "
    "High test metrics on synthetic data do NOT guarantee equivalent performance on real-world banking records.\n"
    "2. Decision Support Only: Risk scores and SHAP feature attributions are investigative leads, not proof of criminal conduct.\n"
    "3. Legitimate High-Velocity Overlap: Small businesses, payment collection aggregators, and shared household accounts "
    "can exhibit high counterparty fan-in or rapid turnover that mimics money-mule behavior.\n"
    "4. Observational Scope: Graph centrality and holding-time estimates reflect only transfers visible within the platform."
)


class SmoothIsotonicCalibrator:
    """
    Combines empirical isotonic regression calibration on the validation split with smooth logistic
    probabilities so risk scores remain strictly monotonic, well-calibrated, and continuous across 0-100.
    """

    def __init__(self, iso_weight: float = 0.55) -> None:
        self.iso = IsotonicRegression(y_min=0.001, y_max=0.999, out_of_bounds="clip")
        self.iso_weight = iso_weight

    def fit(self, raw_probs: np.ndarray, y_true: np.ndarray) -> "SmoothIsotonicCalibrator":
        self.iso.fit(np.asarray(raw_probs, dtype=np.float64), np.asarray(y_true, dtype=np.float64))
        return self

    def predict(self, raw_probs: np.ndarray | List[float]) -> np.ndarray:
        arr = np.asarray(raw_probs, dtype=np.float64)
        iso_p = self.iso.predict(arr)
        blended = self.iso_weight * iso_p + (1.0 - self.iso_weight) * arr
        return np.clip(blended, 0.001, 0.999)


def _scenario_aware_split(
    df: pd.DataFrame,
    random_seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Splits labeled account features into Train (70%), Validation (15%), and Test (15%) sets
    while keeping connected scenario groups (`scenario_group_id`) together in the same split
    to prevent network/ring leakage across splits.
    """
    groups = df["scenario_group_id"].fillna(df["account_id"]).values
    gss_outer = GroupShuffleSplit(n_splits=1, test_size=0.30, random_state=random_seed)
    train_idx, temp_idx = next(gss_outer.split(df, df["is_suspicious_mule"], groups=groups))

    train_df = df.iloc[train_idx].copy()
    temp_df = df.iloc[temp_idx].copy()

    temp_groups = temp_df["scenario_group_id"].fillna(temp_df["account_id"]).values
    gss_inner = GroupShuffleSplit(n_splits=1, test_size=0.50, random_state=random_seed + 1)
    val_idx, test_idx = next(
        gss_inner.split(temp_df, temp_df["is_suspicious_mule"], groups=temp_groups)
    )

    val_df = temp_df.iloc[val_idx].copy()
    test_df = temp_df.iloc[test_idx].copy()
    return train_df, val_df, test_df


def sanitize_feature_input(raw_features: pd.DataFrame | Dict[str, Any]) -> pd.DataFrame:
    """
    Safely coerces missing, malformed, NaN, Inf, or out-of-range inputs into a clean float64 DataFrame
    aligned strictly with FEATURE_NAMES.
    """
    if isinstance(raw_features, dict):
        df = pd.DataFrame([raw_features])
    else:
        df = raw_features.copy()

    clean_data: Dict[str, np.ndarray] = {}
    n_rows = len(df)
    for col in FEATURE_NAMES:
        if col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce")
            arr = series.to_numpy(dtype=np.float64, na_value=0.0)
            arr = np.nan_to_num(arr, nan=0.0, posinf=1e6, neginf=0.0)
            arr = np.clip(arr, -1e6, 1e8)
            clean_data[col] = arr
        else:
            clean_data[col] = np.zeros(n_rows, dtype=np.float64)

    return pd.DataFrame(clean_data, index=df.index)[FEATURE_NAMES]


def compute_shap_contributions_batch(
    booster: xgb.Booster,
    X_clean: pd.DataFrame,
    top_k: int = 6,
) -> List[List[Dict[str, Any]]]:
    """
    Computes exact TreeSHAP feature contributions using XGBoost's native TreeSHAP engine
    (pred_contribs=True), returning top positive and negative drivers for each account.
    """
    dmat = xgb.DMatrix(X_clean[FEATURE_NAMES], feature_names=FEATURE_NAMES)
    # shape: (n_samples, n_features + 1), last column is bias (base value)
    contribs = booster.predict(dmat, pred_contribs=True)
    values_mat = X_clean[FEATURE_NAMES].to_numpy(dtype=np.float64)

    results: List[List[Dict[str, Any]]] = []
    for row_idx in range(len(X_clean)):
        row_shap = contribs[row_idx, :-1]
        row_vals = values_mat[row_idx]
        order = np.argsort(np.abs(row_shap))[::-1][:top_k]
        row_factors: List[Dict[str, Any]] = []
        for feat_idx in order:
            fname = FEATURE_NAMES[int(feat_idx)]
            s_val = float(row_shap[int(feat_idx)])
            f_val = float(row_vals[int(feat_idx)])
            row_factors.append(
                {
                    "feature": fname,
                    "display_name": FEATURE_DISPLAY_MAP.get(fname, fname),
                    "feature_value": round(f_val, 3),
                    "shap_value": round(s_val, 4),
                    "direction": "increases_risk" if s_val >= 0 else "decreases_risk",
                    "description": FEATURE_DESC_MAP.get(fname, ""),
                }
            )
        results.append(row_factors)
    return results


def build_human_explanation_summary(top_factors: List[Dict[str, Any]], risk_category: str) -> str:
    pos_drivers = [f["display_name"] for f in top_factors if f["shap_value"] > 0.08][:3]
    if not pos_drivers:
        return f"{risk_category} risk profile; behavioral indicators within baseline parameters."
    return f"{risk_category} triage signal driven by {', '.join(pos_drivers)}."


def evaluate_predictions_at_thresholds(
    y_true: np.ndarray,
    norm_scores: np.ndarray,
    thresholds_to_eval: List[float],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for thresh in thresholds_to_eval:
        y_pred = (norm_scores >= thresh).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
        prec = float(precision_score(y_true, y_pred, zero_division=0))
        rec = float(recall_score(y_true, y_pred, zero_division=0))
        f1 = float(f1_score(y_true, y_pred, zero_division=0))
        fpr = float(fp / max(1, (fp + tn)))
        fnr = float(fn / max(1, (fn + tp)))
        rows.append(
            {
                "threshold_score": float(thresh),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1_score": round(f1, 4),
                "false_positive_rate": round(fpr, 4),
                "false_negative_rate": round(fnr, 4),
                "flagged_count": int(tp + fp),
                "true_positives": int(tp),
                "false_positives": int(fp),
                "true_negatives": int(tn),
                "false_negatives": int(fn),
            }
        )
    return rows


def train_and_evaluate_model(
    db: Session,
    dataset_id: Optional[str] = None,
    random_seed: int = 42,
    n_estimators: int = 160,
    max_depth: int = 5,
    learning_rate: float = 0.07,
    activate_if_passed: bool = True,
    score_all_accounts: bool = True,
    actor: str = "ML Engineering Lead",
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> Dict[str, Any]:
    """
    Executes the end-to-end XGBoost training, validation calibration, held-out test set evaluation,
    artifact persistence, and batch account scoring pipeline.
    """
    if progress_callback:
        progress_callback(10.0, "Loading accounts, transactions, and isolated labels from database")

    accounts_q = db.query(Account)
    tx_q = db.query(Transaction)
    labels_q = db.query(SyntheticLabel)

    if dataset_id:
        accounts_q = accounts_q.filter(Account.dataset_id == dataset_id)
        tx_q = tx_q.filter(Transaction.dataset_id == dataset_id)
        labels_q = labels_q.filter(SyntheticLabel.dataset_id == dataset_id)

    accounts_rows = [
        {
            "account_id": a.account_id,
            "account_type": a.account_type,
            "created_at": a.created_at,
            "status": a.status,
            "declared_monthly_turnover": a.declared_monthly_turnover,
            "dataset_id": a.dataset_id,
        }
        for a in accounts_q.all()
    ]
    if not accounts_rows:
        raise ValueError("No accounts found in the database to train on. Generate or import data first.")

    accounts_df = pd.DataFrame(accounts_rows)
    resolved_dataset_id = dataset_id or str(accounts_df["dataset_id"].iloc[0])

    tx_rows = [
        {
            "transaction_id": t.transaction_id,
            "sender_account_id": t.sender_account_id,
            "receiver_account_id": t.receiver_account_id,
            "timestamp": t.timestamp,
            "amount": t.amount,
            "currency": t.currency,
            "channel": t.channel,
            "status": t.status,
        }
        for t in tx_q.all()
    ]
    transactions_df = pd.DataFrame(tx_rows)

    label_rows = [
        {
            "account_id": l.account_id,
            "is_suspicious_mule": int(l.is_suspicious_mule),
            "archetype_category": l.archetype_category,
            "scenario_group_id": l.scenario_group_id,
        }
        for l in labels_q.all()
    ]
    if not label_rows:
        raise ValueError("No training labels found in synthetic_labels table.")
    labels_df = pd.DataFrame(label_rows)

    run_id = f"run-train-{uuid.uuid4().hex[:8]}"
    train_meta = DatasetTrainingMetadata(
        run_id=run_id,
        run_type="model_training",
        status="running",
        dataset_id=resolved_dataset_id,
        random_seed=random_seed,
        account_count=len(accounts_df),
        transaction_count=len(transactions_df),
        parameters_json={
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "random_seed": random_seed,
        },
        started_at=utcnow(),
    )
    db.add(train_meta)
    db.commit()

    if progress_callback:
        progress_callback(28.0, "Engineering 26 behavioral, temporal, and graph topology features")

    features_df = compute_account_features(accounts_df, transactions_df)

    # Verify zero leakage columns in feature matrix
    leaked_cols = FORBIDDEN_LEAKAGE_COLUMNS.intersection(set(FEATURE_NAMES))
    if leaked_cols:
        raise RuntimeError(f"Feature leakage guard triggered: {leaked_cols}")

    # Persist FeatureSnapshots in database
    if progress_callback:
        progress_callback(45.0, "Saving engineered feature snapshots to database")

    db.query(FeatureSnapshot).delete()
    now_ts = utcnow()
    snap_mappings: List[Dict[str, Any]] = []
    feat_records = features_df.to_dict(orient="records")
    for row in feat_records:
        f_dict = {k: round(float(row[k]), 4) for k in FEATURE_NAMES}
        last_act = row.get("last_activity_at")
        if pd.isna(last_act):
            last_act = None
        snap_mappings.append(
            {
                "account_id": row["account_id"],
                "snapshot_timestamp": now_ts,
                "feature_version": "v1.0",
                "features_json": f_dict,
                "incoming_tx_count": int(row["incoming_tx_count"]),
                "outgoing_tx_count": int(row["outgoing_tx_count"]),
                "incoming_volume": round(float(row["incoming_volume"]), 2),
                "outgoing_volume": round(float(row["outgoing_volume"]), 2),
                "unique_counterparties": int(row["unique_counterparties"]),
                "last_activity_at": last_act,
            }
        )
    db.bulk_insert_mappings(FeatureSnapshot, snap_mappings)
    db.commit()

    # Merge features with isolated labels for supervised learning
    labeled_df = features_df.merge(labels_df, on="account_id", how="inner")
    if labeled_df["is_suspicious_mule"].nunique() < 2:
        raise ValueError("Labels must contain both positive (1) and negative (0) examples.")

    if progress_callback:
        progress_callback(55.0, "Splitting dataset into scenario-isolated Train / Validation / Test splits")

    train_df, val_df, test_df = _scenario_aware_split(labeled_df, random_seed=random_seed)

    X_train = sanitize_feature_input(train_df[FEATURE_NAMES])
    y_train = train_df["is_suspicious_mule"].to_numpy(dtype=np.int32)

    X_val = sanitize_feature_input(val_df[FEATURE_NAMES])
    y_val = val_df["is_suspicious_mule"].to_numpy(dtype=np.int32)

    X_test = sanitize_feature_input(test_df[FEATURE_NAMES])
    y_test = test_df["is_suspicious_mule"].to_numpy(dtype=np.int32)

    neg_count = int((y_train == 0).sum())
    pos_count = max(1, int((y_train == 1).sum()))
    scale_pos_weight = float(np.sqrt(neg_count / pos_count))

    if progress_callback:
        progress_callback(68.0, "Training XGBoost classifier & fitting validation probability calibrator")

    clf = xgb.XGBClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_weight=3,
        reg_lambda=1.5,
        scale_pos_weight=scale_pos_weight,
        objective="binary:logistic",
        eval_metric="aucpr",
        random_state=random_seed,
        n_jobs=4,
    )
    clf.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    # Fit Smooth Isotonic Calibrator on Validation Split
    val_raw_probs = clf.predict_proba(X_val)[:, 1]
    calibrator = SmoothIsotonicCalibrator(iso_weight=0.55)
    calibrator.fit(val_raw_probs, y_val)

    if progress_callback:
        progress_callback(78.0, "Evaluating model strictly on held-out Test split")

    # Held-out Test Set Evaluation (NEVER report training performance as test performance)
    test_raw_probs = clf.predict_proba(X_test)[:, 1]
    test_cal_probs = calibrator.predict(test_raw_probs)
    test_norm_scores = probability_to_normalized_score(test_cal_probs)

    active_thresholds = get_active_thresholds(db)
    high_threshold = active_thresholds["high"]
    y_test_pred = (test_norm_scores >= high_threshold).astype(int)

    tn, fp, fn, tp = confusion_matrix(y_test, y_test_pred, labels=[0, 1]).ravel()
    test_precision = float(precision_score(y_test, y_test_pred, zero_division=0))
    test_recall = float(recall_score(y_test, y_test_pred, zero_division=0))
    test_f1 = float(f1_score(y_test, y_test_pred, zero_division=0))
    test_roc_auc = float(roc_auc_score(y_test, test_cal_probs))
    test_pr_auc = float(average_precision_score(y_test, test_cal_probs))
    brier_raw = float(brier_score_loss(y_test, test_raw_probs))
    brier_cal = float(brier_score_loss(y_test, test_cal_probs))
    fpr = float(fp / max(1, (fp + tn)))
    fnr = float(fn / max(1, (fn + tp)))

    # Validation set threshold sweep
    val_cal_probs = calibrator.predict(val_raw_probs)
    val_norm_scores = probability_to_normalized_score(val_cal_probs)
    threshold_analysis = evaluate_predictions_at_thresholds(
        y_test, test_norm_scores, [35.0, 50.0, 65.0, 75.0, 85.0]
    )
    validation_threshold_analysis = evaluate_predictions_at_thresholds(
        y_val, val_norm_scores, [35.0, 50.0, 65.0, 75.0, 85.0]
    )

    # Archetype error analysis on Test Set (False Positives & False Negatives by archetype)
    test_eval_df = test_df[["account_id", "archetype_category", "is_suspicious_mule"]].copy()
    test_eval_df["predicted_high_risk"] = y_test_pred
    test_eval_df["risk_score"] = test_norm_scores

    fp_by_archetype = (
        test_eval_df[(test_eval_df["is_suspicious_mule"] == 0) & (test_eval_df["predicted_high_risk"] == 1)][
            "archetype_category"
        ]
        .value_counts()
        .to_dict()
    )
    fn_by_archetype = (
        test_eval_df[(test_eval_df["is_suspicious_mule"] == 1) & (test_eval_df["predicted_high_risk"] == 0)][
            "archetype_category"
        ]
        .value_counts()
        .to_dict()
    )

    # Feature Importance ranking
    importances = clf.feature_importances_
    importance_list = [
        {
            "feature": fname,
            "display_name": FEATURE_DISPLAY_MAP.get(fname, fname),
            "importance": round(float(imp), 4),
            "description": FEATURE_DESC_MAP.get(fname, ""),
        }
        for fname, imp in sorted(
            zip(FEATURE_NAMES, importances), key=lambda x: x[1], reverse=True
        )
    ]

    passed_evaluation = bool(test_roc_auc >= 0.70 and test_pr_auc >= 0.30)

    existing_count = db.query(ModelVersion).count()
    model_version_str = f"v1.{existing_count}.0-xgb"

    artifact_file = MODELS_DIR / f"{model_version_str}.joblib"
    metadata_file = METADATA_DIR / f"{model_version_str}_metadata.json"
    report_file = DATA_DIR / "reports" / f"{model_version_str}_evaluation_report.json"

    metrics_payload = {
        "evaluation_split": "held_out_test_set",
        "decision_threshold_score": high_threshold,
        "precision": round(test_precision, 4),
        "recall": round(test_recall, 4),
        "f1_score": round(test_f1, 4),
        "roc_auc": round(test_roc_auc, 4),
        "pr_auc": round(test_pr_auc, 4),
        "brier_score_raw": round(brier_raw, 4),
        "brier_score_calibrated": round(brier_cal, 4),
        "false_positive_rate": round(fpr, 4),
        "false_negative_rate": round(fnr, 4),
        "confusion_matrix": {
            "true_negatives": int(tn),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "true_positives": int(tp),
        },
        "class_distribution": {
            "train": {
                "total": len(train_df),
                "positive_mules": int(y_train.sum()),
                "negative_legit": int((y_train == 0).sum()),
            },
            "validation": {
                "total": len(val_df),
                "positive_mules": int(y_val.sum()),
                "negative_legit": int((y_val == 0).sum()),
            },
            "test": {
                "total": len(test_df),
                "positive_mules": int(y_test.sum()),
                "negative_legit": int((y_test == 0).sum()),
            },
        },
        "threshold_performance": threshold_analysis,
        "validation_threshold_performance": validation_threshold_analysis,
        "false_positives_by_archetype": fp_by_archetype,
        "false_negatives_by_archetype": fn_by_archetype,
        "synthetic_disclaimer": (
            "Evaluated on held-out synthetic test accounts. Synthetic performance does not guarantee real-world banking accuracy."
        ),
    }

    training_config_payload = {
        "algorithm": "XGBClassifier + IsotonicRegression Calibration",
        "n_estimators": n_estimators,
        "max_depth": max_depth,
        "learning_rate": learning_rate,
        "scale_pos_weight": round(scale_pos_weight, 3),
        "random_seed": random_seed,
        "split_strategy": "Scenario-Group-Aware Stratified Split (70% Train / 15% Val / 15% Test)",
    }

    # Save bundle to disk
    joblib.dump(
        {
            "model_version": model_version_str,
            "classifier": clf,
            "calibrator": calibrator,
            "feature_names": FEATURE_NAMES,
            "thresholds": active_thresholds,
        },
        artifact_file,
    )

    full_metadata = {
        "model_version": model_version_str,
        "created_at": utcnow().isoformat(),
        "dataset_id": resolved_dataset_id,
        "random_seed": random_seed,
        "passed_evaluation": passed_evaluation,
        "feature_schema": FEATURE_DEFINITIONS,
        "metrics": metrics_payload,
        "training_config": training_config_payload,
        "feature_importance": importance_list,
        "risk_scoring_methodology": RISK_SCORING_METHODOLOGY,
        "limitations": MODEL_LIMITATIONS_STATEMENT,
    }
    metadata_file.write_text(json.dumps(full_metadata, indent=2), encoding="utf-8")
    report_file.write_text(json.dumps(full_metadata, indent=2), encoding="utf-8")

    should_activate = bool(activate_if_passed and passed_evaluation)
    if should_activate:
        db.query(ModelVersion).update({ModelVersion.is_active: False})

    model_ver_record = ModelVersion(
        model_version=model_version_str,
        algorithm="XGBClassifier",
        created_at=utcnow(),
        dataset_id=resolved_dataset_id,
        random_seed=random_seed,
        is_active=should_activate,
        passed_evaluation=passed_evaluation,
        artifact_path=str(artifact_file),
        metadata_path=str(metadata_file),
        feature_schema_json=FEATURE_DEFINITIONS,
        metrics_json=metrics_payload,
        training_config_json=training_config_payload,
        feature_importance_json=importance_list,
        limitations_text=MODEL_LIMITATIONS_STATEMENT,
    )
    db.add(model_ver_record)
    db.commit()

    record_audit_event(
        db=db,
        event_type="model_training",
        actor=actor,
        target_type="model",
        target_id=model_version_str,
        action_summary=(
            f"Trained & evaluated model '{model_version_str}' on dataset '{resolved_dataset_id}' "
            f"(Test ROC-AUC={test_roc_auc:.3f}, PR-AUC={test_pr_auc:.3f}, F1={test_f1:.3f}, Activated={should_activate})."
        ),
        details={
            "model_version": model_version_str,
            "passed_evaluation": passed_evaluation,
            "activated": should_activate,
            "test_roc_auc": round(test_roc_auc, 4),
            "test_pr_auc": round(test_pr_auc, 4),
            "test_f1": round(test_f1, 4),
        },
    )

    scoring_summary = None
    if score_all_accounts and should_activate:
        if progress_callback:
            progress_callback(88.0, "Scoring all accounts, computing SHAP explanations, and generating alerts")
        scoring_summary = score_accounts_with_active_model(
            db=db,
            features_df=features_df,
            model_version_str=model_version_str,
            actor=actor,
        )

    train_meta.status = "completed"
    train_meta.summary_json = {
        "model_version": model_version_str,
        "metrics": metrics_payload,
        "scoring_summary": scoring_summary,
    }
    train_meta.completed_at = utcnow()
    db.commit()

    return {
        "model_version": model_version_str,
        "passed_evaluation": passed_evaluation,
        "is_active": should_activate,
        "metrics": metrics_payload,
        "feature_importance": importance_list[:12],
        "scoring_summary": scoring_summary,
    }


def load_model_bundle(db: Session, model_version_str: Optional[str] = None) -> Dict[str, Any]:
    if model_version_str:
        mv = db.query(ModelVersion).filter(ModelVersion.model_version == model_version_str).first()
    else:
        mv = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()
    if not mv:
        raise FileNotFoundError("No active trained model version found. Please train a model first.")
    artifact_path = Path(mv.artifact_path)
    if not artifact_path.exists():
        raise FileNotFoundError(f"Model artifact file missing on disk: {artifact_path}")
    bundle = joblib.load(artifact_path)
    bundle["db_record"] = mv
    return bundle


def score_accounts_with_active_model(
    db: Session,
    features_df: Optional[pd.DataFrame] = None,
    model_version_str: Optional[str] = None,
    actor: str = "System",
) -> Dict[str, Any]:
    """
    Runs batch inference across all eligible accounts using the active model, computes exact TreeSHAP
    explanations for flagged accounts, stores ModelPrediction rows, and creates Alerts & initial Investigations.
    """
    bundle = load_model_bundle(db, model_version_str)
    clf: xgb.XGBClassifier = bundle["classifier"]
    calibrator: IsotonicRegression = bundle["calibrator"]
    resolved_version: str = bundle["model_version"]
    thresholds = get_active_thresholds(db)

    if features_df is None:
        snaps = db.query(FeatureSnapshot).all()
        if not snaps:
            raise ValueError("No engineered feature snapshots available for scoring.")
        rows = []
        for s in snaps:
            r = {"account_id": s.account_id}
            r.update(s.features_json or {})
            rows.append(r)
        features_df = pd.DataFrame(rows)

    X_all = sanitize_feature_input(features_df[FEATURE_NAMES])
    raw_probs = clf.predict_proba(X_all)[:, 1]
    cal_probs = calibrator.predict(raw_probs)
    norm_scores = probability_to_normalized_score(cal_probs)

    # Compute exact TreeSHAP for all accounts with score >= moderate threshold (and top 500 accounts)
    booster = clf.get_booster()
    mod_threshold = thresholds["moderate"]
    high_threshold = thresholds["high"]
    crit_threshold = thresholds["critical"]

    explain_mask = norm_scores >= mod_threshold
    explain_indices = np.where(explain_mask)[0]
    shap_by_idx: Dict[int, List[Dict[str, Any]]] = {}

    if len(explain_indices) > 0:
        X_explain = X_all.iloc[explain_indices]
        batch_shap = compute_shap_contributions_batch(booster, X_explain, top_k=6)
        for local_i, global_i in enumerate(explain_indices):
            shap_by_idx[int(global_i)] = batch_shap[local_i]

    db.query(ModelPrediction).filter(ModelPrediction.model_version == resolved_version).delete()
    db.query(Alert).delete()

    now_ts = utcnow()
    pred_mappings: List[Dict[str, Any]] = []
    alert_mappings: List[Dict[str, Any]] = []

    account_ids = features_df["account_id"].tolist()
    counts_by_cat = {"Low": 0, "Moderate": 0, "High": 0, "Critical": 0}

    # Sort indices descending by score so highest risk alerts get created cleanly
    sorted_indices = np.argsort(norm_scores)[::-1]
    alert_counter = 1

    for idx in sorted_indices:
        i = int(idx)
        acc_id = str(account_ids[i])
        r_prob = round(float(raw_probs[i]), 4)
        c_prob = round(float(cal_probs[i]), 4)
        n_score = round(float(norm_scores[i]), 2)
        cat_info = classify_risk_score(n_score, thresholds)
        r_cat = cat_info["risk_category"]
        priority = cat_info["alert_priority"]
        counts_by_cat[r_cat] = counts_by_cat.get(r_cat, 0) + 1

        top_factors = shap_by_idx.get(i, [])
        summary_str = build_human_explanation_summary(top_factors, r_cat)

        pred_mappings.append(
            {
                "account_id": acc_id,
                "model_version": resolved_version,
                "predicted_at": now_ts,
                "raw_probability": r_prob,
                "calibrated_probability": c_prob,
                "normalized_risk_score": n_score,
                "risk_category": r_cat,
                "alert_priority": priority,
                "top_factors_json": top_factors,
                "explanation_summary": summary_str,
            }
        )

        # Generate Alerts for High & Critical accounts (cap open alert queue at 350 for responsive triage)
        if n_score >= high_threshold and alert_counter <= 350:
            alert_mappings.append(
                {
                    "alert_id": f"ALT-{10000 + alert_counter}",
                    "account_id": acc_id,
                    "model_version": resolved_version,
                    "risk_score": n_score,
                    "risk_category": r_cat,
                    "priority": priority,
                    "status": "open" if alert_counter > 12 else "in_review",
                    "reason_summary": summary_str,
                    "triggered_factors_json": top_factors[:4],
                    "assigned_to": "Sarah Chen" if alert_counter <= 6 else ("Marcus Vance" if alert_counter <= 12 else None),
                    "created_at": now_ts,
                    "updated_at": now_ts,
                }
            )
            alert_counter += 1

    db.bulk_insert_mappings(ModelPrediction, pred_mappings)
    db.bulk_insert_mappings(Alert, alert_mappings)
    db.commit()

    # Seed initial active investigations for the top 8 Critical/High flagged accounts if none exist yet
    if db.query(Investigation).count() == 0 and len(alert_mappings) > 0:
        analysts = [
            "Sarah Chen (Lead AML Investigator)",
            "Marcus Vance (Senior FIU Analyst)",
            "Elena Rostova (Network Intelligence)",
            "David Kim (Financial Crime Unit)",
        ]
        statuses = ["in_progress", "in_progress", "open", "escalated_sar", "in_progress", "open", "in_progress", "closed_confirmed_mule"]
        for k, alt in enumerate(alert_mappings[:8]):
            inv_id = f"INV-{202500 + k + 1}"
            acc_id = alt["account_id"]
            analyst = analysts[k % len(analysts)]
            st = statuses[k % len(statuses)]
            inv = Investigation(
                investigation_id=inv_id,
                account_id=acc_id,
                title=f"High-Velocity Network & Pass-Through Review — {acc_id}",
                status=st,
                priority="critical" if alt["risk_category"] == "Critical" else "high",
                assigned_to=analyst,
                risk_score_at_open=alt["risk_score"],
                findings_summary=(
                    f"Automated triage flagged {acc_id} with score {alt['risk_score']}/100 ({alt['risk_category']}). "
                    f"Primary signal: {alt['reason_summary']}"
                ),
                created_at=now_ts,
                updated_at=now_ts,
            )
            db.add(inv)
            db.flush()

            note = InvestigationNote(
                investigation_id=inv_id,
                author=analyst,
                note_type="analyst_note",
                content=(
                    f"Initial review opened from Alert {alt['alert_id']}. Tracing upstream funding sources and "
                    f"rapid onward transfer counterparties in Network Intelligence graph."
                ),
                created_at=now_ts,
            )
            db.add(note)

            ev = EvidenceItem(
                investigation_id=inv_id,
                evidence_type="shap_explanation",
                title=f"Model Attribution Snapshot ({resolved_version})",
                description=alt["reason_summary"],
                reference_id=acc_id,
                metadata_json={"top_factors": alt["triggered_factors_json"]},
                added_by="FlyGuard AI Triage Engine",
                created_at=now_ts,
            )
            db.add(ev)
        db.commit()

    return {
        "model_version": resolved_version,
        "total_scored": len(pred_mappings),
        "risk_distribution": counts_by_cat,
        "alerts_created": len(alert_mappings),
    }


def explain_single_account(
    db: Session,
    account_id: str,
) -> Dict[str, Any]:
    """
    Computes full 26-feature exact TreeSHAP explanation for any single account on demand,
    handling missing or malformed features gracefully.
    """
    snap = (
        db.query(FeatureSnapshot)
        .filter(FeatureSnapshot.account_id == account_id)
        .order_by(FeatureSnapshot.snapshot_timestamp.desc())
        .first()
    )
    if not snap:
        raise ValueError(f"Feature snapshot not found for account '{account_id}'.")

    bundle = load_model_bundle(db)
    clf: xgb.XGBClassifier = bundle["classifier"]
    calibrator: IsotonicRegression = bundle["calibrator"]
    model_version: str = bundle["model_version"]
    thresholds = get_active_thresholds(db)

    X_row = sanitize_feature_input(snap.features_json or {})
    raw_prob = float(clf.predict_proba(X_row)[0, 1])
    cal_prob = float(calibrator.predict([raw_prob])[0])
    norm_score = float(probability_to_normalized_score(cal_prob))
    cat_info = classify_risk_score(norm_score, thresholds)

    booster = clf.get_booster()
    dmat = xgb.DMatrix(X_row[FEATURE_NAMES], feature_names=FEATURE_NAMES)
    contribs = booster.predict(dmat, pred_contribs=True)[0]
    base_value = float(contribs[-1])
    shap_vals = contribs[:-1]

    all_factors: List[Dict[str, Any]] = []
    for idx, fname in enumerate(FEATURE_NAMES):
        s_val = float(shap_vals[idx])
        f_val = float(X_row.iloc[0][fname])
        all_factors.append(
            {
                "feature": fname,
                "display_name": FEATURE_DISPLAY_MAP.get(fname, fname),
                "feature_value": round(f_val, 4),
                "shap_value": round(s_val, 4),
                "direction": "increases_risk" if s_val >= 0 else "decreases_risk",
                "description": FEATURE_DESC_MAP.get(fname, ""),
            }
        )

    all_factors.sort(key=lambda x: abs(x["shap_value"]), reverse=True)

    return {
        "account_id": account_id,
        "model_version": model_version,
        "raw_probability": round(raw_prob, 4),
        "calibrated_probability": round(cal_prob, 4),
        "normalized_risk_score": round(norm_score, 2),
        "risk_category": cat_info["risk_category"],
        "alert_priority": cat_info["alert_priority"],
        "base_log_odds": round(base_value, 4),
        "explanation_summary": build_human_explanation_summary(all_factors[:6], cat_info["risk_category"]),
        "positive_contributors": [f for f in all_factors if f["shap_value"] > 0][:8],
        "negative_contributors": [f for f in all_factors if f["shap_value"] < 0][:8],
        "all_features": all_factors,
        "disclaimer": (
            "SHAP attributions explain how mathematical features influenced the XGBoost prediction. "
            "Model explanations are decision-support signals, NOT confirmed legal evidence."
        ),
    }


def simulate_what_if(
    db: Session,
    account_id: str,
    feature_overrides: Dict[str, float],
    actor: str = "Investigator",
) -> Dict[str, Any]:
    """
    Runs a non-destructive hypothetical sensitivity analysis on an account's feature vector
    without modifying any historical transactions or persisted predictions.
    """
    snap = (
        db.query(FeatureSnapshot)
        .filter(FeatureSnapshot.account_id == account_id)
        .order_by(FeatureSnapshot.snapshot_timestamp.desc())
        .first()
    )
    if not snap:
        raise ValueError(f"Feature snapshot not found for account '{account_id}'.")

    bundle = load_model_bundle(db)
    clf: xgb.XGBClassifier = bundle["classifier"]
    calibrator: IsotonicRegression = bundle["calibrator"]
    model_version: str = bundle["model_version"]
    thresholds = get_active_thresholds(db)
    booster = clf.get_booster()

    orig_dict = dict(snap.features_json or {})
    hypo_dict = dict(orig_dict)
    applied_changes: List[Dict[str, Any]] = []

    for k, v in feature_overrides.items():
        if k in FEATURE_NAMES:
            old_v = float(orig_dict.get(k, 0.0))
            new_v = float(v)
            hypo_dict[k] = new_v
            if abs(new_v - old_v) > 1e-6:
                applied_changes.append(
                    {
                        "feature": k,
                        "display_name": FEATURE_DISPLAY_MAP.get(k, k),
                        "original_value": round(old_v, 3),
                        "hypothetical_value": round(new_v, 3),
                        "delta": round(new_v - old_v, 3),
                    }
                )

    X_pair = sanitize_feature_input(pd.DataFrame([orig_dict, hypo_dict]))
    raw_probs = clf.predict_proba(X_pair)[:, 1]
    cal_probs = calibrator.predict(raw_probs)
    norm_scores = probability_to_normalized_score(cal_probs)

    orig_score = float(norm_scores[0])
    hypo_score = float(norm_scores[1])
    orig_cat = classify_risk_score(orig_score, thresholds)
    hypo_cat = classify_risk_score(hypo_score, thresholds)

    shap_pair = compute_shap_contributions_batch(booster, X_pair, top_k=8)

    record_audit_event(
        db=db,
        event_type="what_if_simulation",
        actor=actor,
        target_type="account",
        target_id=account_id,
        action_summary=(
            f"Ran hypothetical What-If simulation on {account_id}: score {orig_score:.1f} -> {hypo_score:.1f} "
            f"({orig_cat['risk_category']} -> {hypo_cat['risk_category']})."
        ),
        details={
            "is_hypothetical": True,
            "original_score": orig_score,
            "hypothetical_score": hypo_score,
            "applied_changes": applied_changes,
        },
    )

    return {
        "is_hypothetical": True,
        "hypothetical_notice": (
            "HYPOTHETICAL SIMULATION ONLY: Historical transaction records and official account risk scores "
            "have NOT been modified."
        ),
        "account_id": account_id,
        "model_version": model_version,
        "original": {
            "raw_probability": round(float(raw_probs[0]), 4),
            "calibrated_probability": round(float(cal_probs[0]), 4),
            "normalized_risk_score": orig_score,
            "risk_category": orig_cat["risk_category"],
            "alert_priority": orig_cat["alert_priority"],
            "top_factors": shap_pair[0],
        },
        "hypothetical": {
            "raw_probability": round(float(raw_probs[1]), 4),
            "calibrated_probability": round(float(cal_probs[1]), 4),
            "normalized_risk_score": hypo_score,
            "risk_category": hypo_cat["risk_category"],
            "alert_priority": hypo_cat["alert_priority"],
            "top_factors": shap_pair[1],
        },
        "score_delta": round(hypo_score - orig_score, 2),
        "probability_delta": round(float(cal_probs[1] - cal_probs[0]), 4),
        "applied_changes": applied_changes,
        "editable_features": [
            {
                "name": f["name"],
                "display_name": f["display_name"],
                "category": f["category"],
                "current_value": round(float(orig_dict.get(f["name"], 0.0)), 3),
                "description": f["description"],
            }
            for f in FEATURE_DEFINITIONS
        ],
    }
