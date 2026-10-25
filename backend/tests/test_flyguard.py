from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config import settings
from backend.app.database import Base, get_db, reset_db
from backend.app.main import app
from backend.app.ml.feature_engineering import (
    FEATURE_NAMES,
    FORBIDDEN_LEAKAGE_COLUMNS,
    compute_account_features,
)
from backend.app.ml.model_pipeline import (
    explain_single_account,
    sanitize_feature_input,
    simulate_what_if,
    train_and_evaluate_model,
)
from backend.app.ml.risk_scoring import (
    classify_risk_score,
    probability_to_normalized_score,
)
from backend.app.ml.synthetic_generator import (
    generate_synthetic_dataset,
    persist_synthetic_dataset,
    validate_dataset_frames,
)
from backend.app.security.audit import sanitize_audit_payload


@pytest.fixture(scope="module")
def test_db_session(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "test_flyguard.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    session = TestingSessionLocal()
    # Generate a fast 400-account, 3500-transaction synthetic dataset for integration tests
    bundle = generate_synthetic_dataset(
        num_accounts=400,
        num_transactions=3500,
        random_seed=99,
        suspicious_rate=0.10,
    )
    persist_synthetic_dataset(db=session, gen_bundle=bundle, reset_existing=False, actor="Pytest")
    train_and_evaluate_model(
        db=session,
        dataset_id=bundle["dataset_id"],
        random_seed=99,
        n_estimators=40,
        max_depth=4,
        activate_if_passed=True,
        score_all_accounts=True,
        actor="Pytest",
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield session
    app.dependency_overrides.clear()
    session.close()


def test_synthetic_generator_reproducibility_and_no_leakage():
    b1 = generate_synthetic_dataset(num_accounts=250, num_transactions=1500, random_seed=123)
    b2 = generate_synthetic_dataset(num_accounts=250, num_transactions=1500, random_seed=123)

    assert b1["accounts_df"]["account_id"].tolist() == b2["accounts_df"]["account_id"].tolist()
    assert b1["transactions_df"]["amount"].tolist() == b2["transactions_df"]["amount"].tolist()

    val = validate_dataset_frames(b1["accounts_df"], b1["transactions_df"], b1["labels_df"])
    assert val["valid"] is True
    assert len(val["errors"]) == 0

    # Ensure no label columns exist in accounts or transactions DataFrames
    for col in ("is_suspicious_mule", "archetype_category", "scenario_group_id", "label_provenance"):
        assert col not in b1["accounts_df"].columns
        assert col not in b1["transactions_df"].columns

    # Ensure ordinary, hard-negative, and mule archetypes are all generated
    archetypes = set(b1["labels_df"]["archetype_category"].unique())
    assert any(a.startswith("ordinary_") for a in archetypes)
    assert any(a.startswith("hard_negative_") for a in archetypes)
    assert any(a.startswith("mule_") for a in archetypes)


def test_feature_engineering_temporal_cutoff_prevents_leakage():
    t0 = datetime(2025, 1, 1, 12, 0, 0)
    t_past = datetime(2025, 2, 1, 12, 0, 0)
    t_cutoff = datetime(2025, 2, 15, 12, 0, 0)
    t_future = datetime(2025, 3, 10, 12, 0, 0)

    acc_df = pd.DataFrame(
        [
            {
                "account_id": "AC-1",
                "account_type": "individual",
                "created_at": t0,
                "status": "active",
                "declared_monthly_turnover": 5000.0,
            },
            {
                "account_id": "AC-2",
                "account_type": "individual",
                "created_at": t0,
                "status": "active",
                "declared_monthly_turnover": 5000.0,
            },
        ]
    )
    tx_df = pd.DataFrame(
        [
            {
                "transaction_id": "TX-PAST",
                "sender_account_id": "AC-1",
                "receiver_account_id": "AC-2",
                "timestamp": t_past,
                "amount": 500.0,
                "currency": "USD",
                "channel": "ach",
                "status": "completed",
            },
            {
                "transaction_id": "TX-FUTURE",
                "sender_account_id": "AC-1",
                "receiver_account_id": "AC-2",
                "timestamp": t_future,
                "amount": 99999.0,
                "currency": "USD",
                "channel": "wire",
                "status": "completed",
            },
        ]
    )

    feats_at_cutoff = compute_account_features(acc_df, tx_df, as_of_timestamp=t_cutoff)
    ac1_row = feats_at_cutoff[feats_at_cutoff["account_id"] == "AC-1"].iloc[0]

    # Future $99,999 transaction must NOT be included when as_of_timestamp is t_cutoff
    assert ac1_row["outgoing_tx_count"] == 1.0
    assert ac1_row["outgoing_volume"] == 500.0
    assert FORBIDDEN_LEAKAGE_COLUMNS.isdisjoint(set(FEATURE_NAMES))


def test_malformed_and_out_of_range_feature_sanitization():
    malformed = {
        "incoming_tx_count": "not_a_number",
        "outgoing_volume": float("inf"),
        "rapid_passthrough_ratio": float("nan"),
        "unexpected_column": 12345,
    }
    clean_df = sanitize_feature_input(malformed)
    assert list(clean_df.columns) == FEATURE_NAMES
    assert not clean_df.isna().any().any()
    assert np.isfinite(clean_df.to_numpy()).all()


def test_risk_scoring_and_secret_redaction():
    assert probability_to_normalized_score(0.0) == 0.0
    assert 34.0 <= probability_to_normalized_score(0.15) <= 36.0
    assert 64.0 <= probability_to_normalized_score(0.45) <= 66.0
    assert probability_to_normalized_score(1.0) == 100.0

    cat = classify_risk_score(88.0, {"moderate": 35.0, "high": 65.0, "critical": 85.0})
    assert cat["risk_category"] == "Critical"
    assert cat["alert_priority"] == "Urgent"

    raw_audit = {"actor": "admin", "password": "my_secret_password", "nested": {"api_key": "12345", "ok": 1}}
    sanitized = sanitize_audit_payload(raw_audit)
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["nested"]["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["ok"] == 1


def test_production_db_reset_guard(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(PermissionError):
        reset_db(force=False)


def test_end_to_end_api_workflow(test_db_session):
    client = TestClient(app)

    # 1. Health & DB Health
    r_health = client.get("/api/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "healthy"
    assert r_health.json()["active_model_version"] is not None

    r_db = client.get("/api/health/db")
    assert r_db.status_code == 200
    assert r_db.json()["accounts_count"] == 400
    assert r_db.json()["transactions_count"] == 3500

    # 2. Overview & Global Map
    r_ov = client.get("/api/overview")
    assert r_ov.status_code == 200
    ov_data = r_ov.json()
    assert ov_data["kpis"]["total_accounts"] == 400
    assert len(ov_data["volume_trends"]) > 0

    r_map = client.get("/api/map/activity")
    assert r_map.status_code == 200
    assert "SYNTHETIC GEOGRAPHIC DATA" in r_map.json()["synthetic_disclaimer"]
    assert len(r_map.json()["hubs"]) > 0

    # 3. Flagged Accounts & Account Detail
    r_acc = client.get("/api/accounts?flagged_only=true&page_size=10")
    assert r_acc.status_code == 200
    flagged_items = r_acc.json()["items"]
    assert len(flagged_items) > 0
    top_acc_id = flagged_items[0]["account_id"]

    r_detail = client.get(f"/api/accounts/{top_acc_id}")
    assert r_detail.status_code == 200
    assert r_detail.json()["account"]["account_id"] == top_acc_id
    assert r_detail.json()["shap_explanation"] is not None

    # 4. Graph Intelligence & Path Tracing
    r_graph = client.get(f"/api/graph/account/{top_acc_id}?hops=2")
    assert r_graph.status_code == 200
    g_data = r_graph.json()
    assert g_data["center_account_id"] == top_acc_id
    assert len(g_data["nodes"]) >= 1
    assert len(g_data["edges"]) >= 1

    edge0 = g_data["edges"][0]
    r_trace = client.post(
        "/api/graph/trace-path",
        json={
            "source_account_id": edge0["source"],
            "target_account_id": edge0["target"],
            "max_hops": 3,
        },
    )
    assert r_trace.status_code == 200
    assert r_trace.json()["found"] is True

    # 5. Explainable AI & Non-Destructive What-If Analysis
    r_exp = client.get(f"/api/explain/{top_acc_id}")
    assert r_exp.status_code == 200
    orig_score = r_exp.json()["normalized_risk_score"]

    r_whatif = client.post(
        "/api/what-if",
        json={
            "account_id": top_acc_id,
            "feature_overrides": {
                "rapid_passthrough_ratio": 0.0,
                "passthrough_symmetry_score": 0.05,
                "median_holding_time_hours": 240.0,
            },
            "actor": "Pytest Investigator",
        },
    )
    assert r_whatif.status_code == 200
    wi_data = r_whatif.json()
    assert wi_data["is_hypothetical"] is True
    assert wi_data["original"]["normalized_risk_score"] == orig_score

    # Verify original account score in DB was NOT modified by What-If analysis
    r_exp_after = client.get(f"/api/explain/{top_acc_id}")
    assert r_exp_after.json()["normalized_risk_score"] == orig_score

    # 6. Investigation Workspace Creation, Notes & Evidence
    r_inv_create = client.post(
        "/api/investigations",
        json={
            "account_id": top_acc_id,
            "title": f"Pytest Investigation for {top_acc_id}",
            "priority": "critical",
            "assigned_to": "Test Analyst",
            "actor": "Test Analyst",
        },
    )
    assert r_inv_create.status_code == 200
    inv_id = r_inv_create.json()["investigation"]["investigation_id"]

    r_note = client.post(
        f"/api/investigations/{inv_id}/notes",
        json={"author": "Test Analyst", "note_type": "analyst_note", "content": "Verified rapid onward wires."},
    )
    assert r_note.status_code == 200
    assert any("Verified rapid onward wires." in n["content"] for n in r_note.json()["notes"])

    r_ev = client.post(
        f"/api/investigations/{inv_id}/evidence",
        json={
            "evidence_type": "transaction_chain",
            "title": "Primary Wire Hop",
            "description": "Linked transaction edge",
            "reference_id": edge0["transaction_ids"][0] if edge0["transaction_ids"] else top_acc_id,
            "added_by": "Test Analyst",
        },
    )
    assert r_ev.status_code == 200
    assert len(r_ev.json()["evidence"]) >= 1

    # 7. Risk Analytics, Context, Models & Audit Trail
    assert client.get("/api/analytics/risk").status_code == 200
    assert client.get("/api/context").status_code == 200
    assert client.get("/api/models").status_code == 200
    r_audit = client.get("/api/audit")
    assert r_audit.status_code == 200
    assert r_audit.json()["total"] > 0

