import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import SessionLocal, get_db, reset_db
from backend.app.graph.network_service import get_account_ego_network, trace_transaction_path
from backend.app.ml.feature_engineering import FEATURE_DEFINITIONS
from backend.app.ml.model_pipeline import (
    explain_single_account,
    score_accounts_with_active_model,
    simulate_what_if,
    train_and_evaluate_model,
)
from backend.app.ml.risk_scoring import (
    RISK_SCORING_METHODOLOGY,
    get_active_thresholds,
    update_active_thresholds,
)
from backend.app.ml.synthetic_generator import (
    generate_synthetic_dataset,
    persist_synthetic_dataset,
    validate_dataset_frames,
)
from backend.app.models.entities import (
    Account,
    Alert,
    AuditEvent,
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
from backend.app.schemas.api_schemas import (
    AccountSummarySchema,
    AlertSchema,
    AlertUpdateRequest,
    DatabaseHealthResponse,
    EvidenceItemCreate,
    GraphPathQueryRequest,
    HealthResponse,
    InvestigationCreateRequest,
    InvestigationNoteCreate,
    InvestigationUpdateRequest,
    ModelTrainRequest,
    PaginatedAccountsResponse,
    PaginatedTransactionsResponse,
    RiskThresholdConfig,
    SyntheticGenerationRequest,
    TransactionSchema,
    WhatIfSimulationRequest,
)
from backend.app.security.audit import record_audit_event
from backend.app.services.intelligence_service import (
    get_financial_context_feed,
    get_global_activity_map_data,
    get_overview_intelligence,
    get_risk_analytics_summary,
)
from backend.app.utils.jobs import job_manager

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse, tags=["System"])
def get_health(db: Session = Depends(get_db)) -> HealthResponse:
    active_model = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()
    return HealthResponse(
        status="healthy",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        active_model_version=active_model.model_version if active_model else None,
        timestamp=utcnow(),
    )


@router.get("/health/db", response_model=DatabaseHealthResponse, tags=["System"])
def get_database_health(db: Session = Depends(get_db)) -> DatabaseHealthResponse:
    acc_cnt = db.query(func.count(Account.account_id)).scalar() or 0
    tx_cnt = db.query(func.count(Transaction.transaction_id)).scalar() or 0
    flagged_cnt = (
        db.query(func.count(ModelPrediction.id))
        .filter(ModelPrediction.risk_category.in_(["High", "Critical"]))
        .scalar()
        or 0
    )
    alerts_cnt = (
        db.query(func.count(Alert.alert_id))
        .filter(Alert.status.in_(["open", "in_review", "escalated"]))
        .scalar()
        or 0
    )
    inv_cnt = (
        db.query(func.count(Investigation.investigation_id))
        .filter(Investigation.status.in_(["open", "in_progress", "escalated_sar"]))
        .scalar()
        or 0
    )
    sample_acc = db.query(Account.dataset_id).first()
    engine_name = "SQLite (WAL Mode)" if settings.database_url.startswith("sqlite") else "PostgreSQL"
    return DatabaseHealthResponse(
        status="connected",
        engine=engine_name,
        accounts_count=acc_cnt,
        transactions_count=tx_cnt,
        flagged_accounts_count=flagged_cnt,
        open_alerts_count=alerts_cnt,
        active_investigations_count=inv_cnt,
        latest_dataset_id=sample_acc[0] if sample_acc else None,
    )


@router.get("/overview", tags=["Intelligence"])
def api_get_overview(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return get_overview_intelligence(db)


@router.get("/map/activity", tags=["Intelligence"])
def api_get_global_map(
    min_amount: float = Query(0.0, ge=0.0),
    risk_filter: str = Query("all"),
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return get_global_activity_map_data(
        db=db,
        min_amount=min_amount,
        risk_filter=risk_filter,
        days=days,
    )


@router.get("/accounts", response_model=PaginatedAccountsResponse, tags=["Accounts"])
def list_accounts(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    search: Optional[str] = Query(None),
    risk_category: Optional[str] = Query(None),
    min_risk_score: Optional[float] = Query(None, ge=0.0, le=100.0),
    account_type: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    flagged_only: bool = Query(False),
    sort_by: str = Query("risk_score"),
    sort_dir: str = Query("desc"),
    db: Session = Depends(get_db),
) -> PaginatedAccountsResponse:
    q = (
        db.query(Account, ModelPrediction, FeatureSnapshot)
        .outerjoin(ModelPrediction, Account.account_id == ModelPrediction.account_id)
        .outerjoin(FeatureSnapshot, Account.account_id == FeatureSnapshot.account_id)
    )

    if search:
        term = f"%{search.strip()}%"
        q = q.filter(
            or_(
                Account.account_id.ilike(term),
                Account.synthetic_region.ilike(term),
                Account.account_type.ilike(term),
            )
        )
    if risk_category and risk_category.lower() != "all":
        q = q.filter(ModelPrediction.risk_category == risk_category)
    if min_risk_score is not None:
        q = q.filter(ModelPrediction.normalized_risk_score >= min_risk_score)
    if flagged_only:
        q = q.filter(ModelPrediction.risk_category.in_(["Moderate", "High", "Critical"]))
    if account_type and account_type.lower() != "all":
        q = q.filter(Account.account_type == account_type)
    if region and region.lower() != "all":
        q = q.filter(Account.synthetic_region == region)

    total = q.count()

    sort_col_map = {
        "risk_score": ModelPrediction.normalized_risk_score,
        "incoming_volume": FeatureSnapshot.incoming_volume,
        "outgoing_volume": FeatureSnapshot.outgoing_volume,
        "unique_counterparties": FeatureSnapshot.unique_counterparties,
        "last_activity_at": FeatureSnapshot.last_activity_at,
        "created_at": Account.created_at,
    }
    sort_col = sort_col_map.get(sort_by, ModelPrediction.normalized_risk_score)
    if sort_dir.lower() == "asc":
        q = q.order_by(sort_col.asc().nulls_last(), Account.account_id.asc())
    else:
        q = q.order_by(sort_col.desc().nulls_last(), Account.account_id.asc())

    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    acc_ids = [r[0].account_id for r in rows]
    inv_map: Dict[str, Investigation] = {}
    if acc_ids:
        for inv in db.query(Investigation).filter(Investigation.account_id.in_(acc_ids)).all():
            inv_map[inv.account_id] = inv

    items: List[AccountSummarySchema] = []
    for acc, pred, snap in rows:
        inv = inv_map.get(acc.account_id)
        items.append(
            AccountSummarySchema(
                account_id=acc.account_id,
                account_type=acc.account_type,
                customer_segment=acc.customer_segment,
                created_at=acc.created_at,
                status=acc.status,
                synthetic_region=acc.synthetic_region,
                synthetic_country_code=acc.synthetic_country_code,
                kyc_tier=acc.kyc_tier,
                declared_monthly_turnover=acc.declared_monthly_turnover,
                primary_currency=acc.primary_currency,
                is_synthetic=acc.is_synthetic,
                risk_score=round(float(pred.normalized_risk_score), 2) if pred else 0.0,
                raw_probability=round(float(pred.raw_probability), 4) if pred else 0.0,
                calibrated_probability=round(float(pred.calibrated_probability), 4) if pred else 0.0,
                risk_category=pred.risk_category if pred else "Low",
                alert_priority=pred.alert_priority if pred else "None",
                incoming_tx_count=int(snap.incoming_tx_count) if snap else 0,
                outgoing_tx_count=int(snap.outgoing_tx_count) if snap else 0,
                incoming_volume=round(float(snap.incoming_volume), 2) if snap else 0.0,
                outgoing_volume=round(float(snap.outgoing_volume), 2) if snap else 0.0,
                unique_counterparties=int(snap.unique_counterparties) if snap else 0,
                last_activity_at=snap.last_activity_at if snap else None,
                explanation_summary=pred.explanation_summary if pred else None,
                top_factors=(pred.top_factors_json or []) if pred else [],
                investigation_status=inv.status if inv else None,
                investigation_id=inv.investigation_id if inv else None,
            )
        )

    return PaginatedAccountsResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/accounts/{account_id}", tags=["Accounts"])
def get_account_detail(account_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    acc = db.query(Account).filter(Account.account_id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' not found.")

    pred = db.query(ModelPrediction).filter(ModelPrediction.account_id == account_id).first()
    snap = db.query(FeatureSnapshot).filter(FeatureSnapshot.account_id == account_id).first()
    alerts = (
        db.query(Alert)
        .filter(Alert.account_id == account_id)
        .order_by(Alert.created_at.desc())
        .all()
    )
    invs = (
        db.query(Investigation)
        .filter(Investigation.account_id == account_id)
        .order_by(Investigation.updated_at.desc())
        .all()
    )
    audits = (
        db.query(AuditEvent)
        .filter(AuditEvent.target_id == account_id)
        .order_by(AuditEvent.timestamp.desc())
        .limit(20)
        .all()
    )

    shap_detail = None
    try:
        shap_detail = explain_single_account(db, account_id)
    except Exception:
        shap_detail = None

    return {
        "account": {
            "account_id": acc.account_id,
            "account_type": acc.account_type,
            "customer_segment": acc.customer_segment,
            "created_at": acc.created_at.isoformat(),
            "status": acc.status,
            "synthetic_region": acc.synthetic_region,
            "synthetic_country_code": acc.synthetic_country_code,
            "kyc_tier": acc.kyc_tier,
            "declared_monthly_turnover": acc.declared_monthly_turnover,
            "primary_currency": acc.primary_currency,
            "is_synthetic": acc.is_synthetic,
            "dataset_id": acc.dataset_id,
        },
        "risk_profile": {
            "model_version": pred.model_version if pred else None,
            "raw_probability": round(float(pred.raw_probability), 4) if pred else 0.0,
            "calibrated_probability": round(float(pred.calibrated_probability), 4) if pred else 0.0,
            "normalized_risk_score": round(float(pred.normalized_risk_score), 2) if pred else 0.0,
            "risk_category": pred.risk_category if pred else "Low",
            "alert_priority": pred.alert_priority if pred else "None",
            "explanation_summary": pred.explanation_summary if pred else None,
            "top_factors": (pred.top_factors_json or []) if pred else [],
        },
        "features": snap.features_json if snap else {},
        "activity_summary": {
            "incoming_tx_count": snap.incoming_tx_count if snap else 0,
            "outgoing_tx_count": snap.outgoing_tx_count if snap else 0,
            "incoming_volume": snap.incoming_volume if snap else 0.0,
            "outgoing_volume": snap.outgoing_volume if snap else 0.0,
            "unique_counterparties": snap.unique_counterparties if snap else 0,
            "last_activity_at": snap.last_activity_at.isoformat() if (snap and snap.last_activity_at) else None,
        },
        "shap_explanation": shap_detail,
        "alerts": [
            {
                "alert_id": a.alert_id,
                "risk_score": a.risk_score,
                "risk_category": a.risk_category,
                "priority": a.priority,
                "status": a.status,
                "reason_summary": a.reason_summary,
                "created_at": a.created_at.isoformat(),
            }
            for a in alerts
        ],
        "investigations": [
            {
                "investigation_id": i.investigation_id,
                "title": i.title,
                "status": i.status,
                "priority": i.priority,
                "assigned_to": i.assigned_to,
                "risk_score_at_open": i.risk_score_at_open,
                "findings_summary": i.findings_summary,
                "created_at": i.created_at.isoformat(),
                "updated_at": i.updated_at.isoformat(),
            }
            for i in invs
        ],
        "audit_history": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "actor": e.actor,
                "action_summary": e.action_summary,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in audits
        ],
    }


@router.get("/accounts/{account_id}/transactions", response_model=PaginatedTransactionsResponse, tags=["Accounts"])
def get_account_transactions(
    account_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    direction: str = Query("all"),
    db: Session = Depends(get_db),
) -> PaginatedTransactionsResponse:
    q = db.query(Transaction)
    if direction == "incoming":
        q = q.filter(Transaction.receiver_account_id == account_id)
    elif direction == "outgoing":
        q = q.filter(Transaction.sender_account_id == account_id)
    else:
        q = q.filter(
            or_(
                Transaction.sender_account_id == account_id,
                Transaction.receiver_account_id == account_id,
            )
        )

    total = q.count()
    rows = q.order_by(Transaction.timestamp.desc()).offset((page - 1) * page_size).limit(page_size).all()

    involved = {t.sender_account_id for t in rows} | {t.receiver_account_id for t in rows}
    pred_map: Dict[str, ModelPrediction] = {}
    if involved:
        for p in db.query(ModelPrediction).filter(ModelPrediction.account_id.in_(list(involved))).all():
            pred_map[p.account_id] = p

    items = [
        TransactionSchema(
            transaction_id=t.transaction_id,
            sender_account_id=t.sender_account_id,
            receiver_account_id=t.receiver_account_id,
            timestamp=t.timestamp,
            amount=t.amount,
            currency=t.currency,
            channel=t.channel,
            status=t.status,
            is_synthetic=t.is_synthetic,
            sender_risk_score=pred_map[t.sender_account_id].normalized_risk_score if t.sender_account_id in pred_map else 0.0,
            sender_risk_category=pred_map[t.sender_account_id].risk_category if t.sender_account_id in pred_map else "Low",
            receiver_risk_score=pred_map[t.receiver_account_id].normalized_risk_score if t.receiver_account_id in pred_map else 0.0,
            receiver_risk_category=pred_map[t.receiver_account_id].risk_category if t.receiver_account_id in pred_map else "Low",
            metadata_json=t.metadata_json,
        )
        for t in rows
    ]
    return PaginatedTransactionsResponse(total=total, page=page, page_size=page_size, items=items)


@router.get("/transactions", response_model=PaginatedTransactionsResponse, tags=["Transactions"])
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    search: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    min_amount: Optional[float] = Query(None, ge=0.0),
    max_amount: Optional[float] = Query(None, ge=0.0),
    risk_category: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    sort_by: str = Query("timestamp"),
    sort_dir: str = Query("desc"),
    db: Session = Depends(get_db),
) -> PaginatedTransactionsResponse:
    q = db.query(Transaction)

    if search:
        term = f"%{search.strip()}%"
        q = q.filter(
            or_(
                Transaction.transaction_id.ilike(term),
                Transaction.sender_account_id.ilike(term),
                Transaction.receiver_account_id.ilike(term),
            )
        )
    if account_id:
        q = q.filter(
            or_(
                Transaction.sender_account_id == account_id.strip(),
                Transaction.receiver_account_id == account_id.strip(),
            )
        )
    if channel and channel.lower() != "all":
        q = q.filter(Transaction.channel == channel)
    if min_amount is not None:
        q = q.filter(Transaction.amount >= min_amount)
    if max_amount is not None:
        q = q.filter(Transaction.amount <= max_amount)
    if start_date is not None:
        q = q.filter(Transaction.timestamp >= start_date)
    if end_date is not None:
        q = q.filter(Transaction.timestamp <= end_date)
    if risk_category and risk_category.lower() != "all":
        risk_acc_subq = (
            db.query(ModelPrediction.account_id)
            .filter(ModelPrediction.risk_category == risk_category)
            .subquery()
        )
        q = q.filter(
            or_(
                Transaction.sender_account_id.in_(risk_acc_subq),
                Transaction.receiver_account_id.in_(risk_acc_subq),
            )
        )

    total = q.count()
    sort_col = Transaction.amount if sort_by == "amount" else Transaction.timestamp
    if sort_dir.lower() == "asc":
        q = q.order_by(sort_col.asc())
    else:
        q = q.order_by(sort_col.desc())

    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    involved = {t.sender_account_id for t in rows} | {t.receiver_account_id for t in rows}
    pred_map: Dict[str, ModelPrediction] = {}
    if involved:
        for p in db.query(ModelPrediction).filter(ModelPrediction.account_id.in_(list(involved))).all():
            pred_map[p.account_id] = p

    items = [
        TransactionSchema(
            transaction_id=t.transaction_id,
            sender_account_id=t.sender_account_id,
            receiver_account_id=t.receiver_account_id,
            timestamp=t.timestamp,
            amount=t.amount,
            currency=t.currency,
            channel=t.channel,
            status=t.status,
            is_synthetic=t.is_synthetic,
            sender_risk_score=pred_map[t.sender_account_id].normalized_risk_score if t.sender_account_id in pred_map else 0.0,
            sender_risk_category=pred_map[t.sender_account_id].risk_category if t.sender_account_id in pred_map else "Low",
            receiver_risk_score=pred_map[t.receiver_account_id].normalized_risk_score if t.receiver_account_id in pred_map else 0.0,
            receiver_risk_category=pred_map[t.receiver_account_id].risk_category if t.receiver_account_id in pred_map else "Low",
            metadata_json=t.metadata_json,
        )
        for t in rows
    ]
    return PaginatedTransactionsResponse(total=total, page=page, page_size=page_size, items=items)


@router.get("/transactions/{transaction_id}", tags=["Transactions"])
def get_transaction_detail(transaction_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    tx = db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found.")

    s_acc = db.query(Account).filter(Account.account_id == tx.sender_account_id).first()
    r_acc = db.query(Account).filter(Account.account_id == tx.receiver_account_id).first()
    s_pred = db.query(ModelPrediction).filter(ModelPrediction.account_id == tx.sender_account_id).first()
    r_pred = db.query(ModelPrediction).filter(ModelPrediction.account_id == tx.receiver_account_id).first()

    pair_txs = (
        db.query(Transaction)
        .filter(
            or_(
                (Transaction.sender_account_id == tx.sender_account_id)
                & (Transaction.receiver_account_id == tx.receiver_account_id),
                (Transaction.sender_account_id == tx.receiver_account_id)
                & (Transaction.receiver_account_id == tx.sender_account_id),
            )
        )
        .order_by(Transaction.timestamp.desc())
        .limit(10)
        .all()
    )

    return {
        "transaction": {
            "transaction_id": tx.transaction_id,
            "sender_account_id": tx.sender_account_id,
            "receiver_account_id": tx.receiver_account_id,
            "timestamp": tx.timestamp.isoformat(),
            "amount": tx.amount,
            "currency": tx.currency,
            "channel": tx.channel,
            "status": tx.status,
            "is_synthetic": tx.is_synthetic,
        },
        "sender": {
            "account_id": tx.sender_account_id,
            "account_type": s_acc.account_type if s_acc else "unknown",
            "synthetic_region": s_acc.synthetic_region if s_acc else None,
            "risk_score": s_pred.normalized_risk_score if s_pred else 0.0,
            "risk_category": s_pred.risk_category if s_pred else "Low",
            "explanation_summary": s_pred.explanation_summary if s_pred else None,
        },
        "receiver": {
            "account_id": tx.receiver_account_id,
            "account_type": r_acc.account_type if r_acc else "unknown",
            "synthetic_region": r_acc.synthetic_region if r_acc else None,
            "risk_score": r_pred.normalized_risk_score if r_pred else 0.0,
            "risk_category": r_pred.risk_category if r_pred else "Low",
            "explanation_summary": r_pred.explanation_summary if r_pred else None,
        },
        "corridor_history": [
            {
                "transaction_id": pt.transaction_id,
                "sender_account_id": pt.sender_account_id,
                "receiver_account_id": pt.receiver_account_id,
                "amount": pt.amount,
                "channel": pt.channel,
                "timestamp": pt.timestamp.isoformat(),
            }
            for pt in pair_txs
        ],
    }


@router.get("/graph/account/{account_id}", tags=["Graph Intelligence"])
def api_get_account_graph(
    account_id: str,
    hops: int = Query(1, ge=1, le=3),
    direction: str = Query("all"),
    min_amount: float = Query(0.0, ge=0.0),
    min_risk_score: float = Query(0.0, ge=0.0, le=100.0),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    max_nodes: int = Query(85, ge=10, le=200),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        return get_account_ego_network(
            db=db,
            center_account_id=account_id,
            hops=hops,
            direction=direction,
            min_amount=min_amount,
            min_risk_score=min_risk_score,
            start_date=start_date,
            end_date=end_date,
            max_nodes=max_nodes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/graph/trace-path", tags=["Graph Intelligence"])
def api_trace_graph_path(
    req: GraphPathQueryRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return trace_transaction_path(
        db=db,
        source_account_id=req.source_account_id.strip(),
        target_account_id=req.target_account_id.strip(),
        max_hops=req.max_hops,
    )


@router.get("/explain/{account_id}", tags=["Explainable AI"])
def api_explain_account(account_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        return explain_single_account(db=db, account_id=account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/what-if", tags=["What-If Lab"])
def api_run_what_if(
    req: WhatIfSimulationRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        return simulate_what_if(
            db=db,
            account_id=req.account_id,
            feature_overrides=req.feature_overrides,
            actor=req.actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/alerts", tags=["Alerts"])
def list_alerts(
    status: Optional[str] = Query(None),
    risk_category: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    q = db.query(Alert)
    if status and status.lower() != "all":
        q = q.filter(Alert.status == status)
    if risk_category and risk_category.lower() != "all":
        q = q.filter(Alert.risk_category == risk_category)
    total = q.count()
    items = q.order_by(Alert.risk_score.desc(), Alert.created_at.desc()).limit(limit).all()
    return {
        "total": total,
        "items": [AlertSchema.model_validate(a).model_dump() for a in items],
    }


@router.patch("/alerts/{alert_id}", response_model=AlertSchema, tags=["Alerts"])
def update_alert(
    alert_id: str,
    req: AlertUpdateRequest,
    db: Session = Depends(get_db),
) -> AlertSchema:
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")

    old_status = alert.status
    alert.status = req.status
    if req.assigned_to is not None:
        alert.assigned_to = req.assigned_to
    if req.decision_notes is not None:
        alert.decision_notes = req.decision_notes
    alert.updated_at = utcnow()
    db.commit()
    db.refresh(alert)

    record_audit_event(
        db=db,
        event_type="alert_decision",
        actor=req.actor,
        target_type="alert",
        target_id=alert_id,
        action_summary=f"Updated alert {alert_id} (account {alert.account_id}) status: {old_status} -> {req.status}.",
        details={
            "account_id": alert.account_id,
            "old_status": old_status,
            "new_status": req.status,
            "decision_notes": req.decision_notes,
        },
    )
    return AlertSchema.model_validate(alert)


@router.get("/investigations", tags=["Investigations"])
def list_investigations(
    status: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    q = db.query(Investigation)
    if status and status.lower() != "all":
        q = q.filter(Investigation.status == status)
    if account_id:
        q = q.filter(Investigation.account_id == account_id)

    items = q.order_by(Investigation.updated_at.desc()).all()
    return {
        "total": len(items),
        "items": [
            {
                "investigation_id": inv.investigation_id,
                "account_id": inv.account_id,
                "title": inv.title,
                "status": inv.status,
                "priority": inv.priority,
                "assigned_to": inv.assigned_to,
                "risk_score_at_open": inv.risk_score_at_open,
                "findings_summary": inv.findings_summary,
                "notes_count": len(inv.notes),
                "evidence_count": len(inv.evidence_items),
                "created_at": inv.created_at.isoformat(),
                "updated_at": inv.updated_at.isoformat(),
            }
            for inv in items
        ],
    }


@router.post("/investigations", tags=["Investigations"])
def create_investigation(
    req: InvestigationCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    acc = db.query(Account).filter(Account.account_id == req.account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail=f"Account '{req.account_id}' not found.")

    existing = (
        db.query(Investigation)
        .filter(
            Investigation.account_id == req.account_id,
            Investigation.status.in_(["open", "in_progress", "escalated_sar"]),
        )
        .first()
    )
    if existing:
        return get_investigation_detail(existing.investigation_id, db)

    pred = db.query(ModelPrediction).filter(ModelPrediction.account_id == req.account_id).first()
    score_val = float(pred.normalized_risk_score) if pred else 0.0

    inv_id = f"INV-{uuid.uuid4().hex[:6].upper()}"
    now_ts = utcnow()
    inv = Investigation(
        investigation_id=inv_id,
        account_id=req.account_id,
        title=req.title or f"Account Network & Flow Investigation — {req.account_id}",
        status="in_progress",
        priority=req.priority,
        assigned_to=req.assigned_to,
        risk_score_at_open=score_val,
        findings_summary=pred.explanation_summary if pred else "Investigation opened by analyst.",
        created_at=now_ts,
        updated_at=now_ts,
    )
    db.add(inv)
    db.flush()

    note_text = req.initial_note or f"Investigation workspace initialized for {req.account_id} (Risk Score: {score_val:.1f}/100)."
    db.add(
        InvestigationNote(
            investigation_id=inv_id,
            author=req.actor,
            note_type="analyst_note",
            content=note_text,
            created_at=now_ts,
        )
    )
    db.commit()

    record_audit_event(
        db=db,
        event_type="investigation_created",
        actor=req.actor,
        target_type="investigation",
        target_id=inv_id,
        action_summary=f"Opened investigation {inv_id} for account {req.account_id}.",
        details={"account_id": req.account_id, "priority": req.priority, "assigned_to": req.assigned_to},
    )
    return get_investigation_detail(inv_id, db)


@router.get("/investigations/{investigation_id}", tags=["Investigations"])
def get_investigation_detail(
    investigation_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    inv = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")

    acc_detail = get_account_detail(inv.account_id, db)
    audits = (
        db.query(AuditEvent)
        .filter(
            or_(
                AuditEvent.target_id == investigation_id,
                AuditEvent.target_id == inv.account_id,
            )
        )
        .order_by(AuditEvent.timestamp.desc())
        .limit(25)
        .all()
    )

    return {
        "investigation": {
            "investigation_id": inv.investigation_id,
            "account_id": inv.account_id,
            "title": inv.title,
            "status": inv.status,
            "priority": inv.priority,
            "assigned_to": inv.assigned_to,
            "risk_score_at_open": inv.risk_score_at_open,
            "findings_summary": inv.findings_summary,
            "created_at": inv.created_at.isoformat(),
            "updated_at": inv.updated_at.isoformat(),
        },
        "notes": [
            {
                "id": n.id,
                "author": n.author,
                "note_type": n.note_type,
                "content": n.content,
                "created_at": n.created_at.isoformat(),
            }
            for n in inv.notes
        ],
        "evidence": [
            {
                "id": ev.id,
                "evidence_type": ev.evidence_type,
                "title": ev.title,
                "description": ev.description,
                "reference_id": ev.reference_id,
                "metadata_json": ev.metadata_json,
                "added_by": ev.added_by,
                "created_at": ev.created_at.isoformat(),
            }
            for ev in inv.evidence_items
        ],
        "account_context": acc_detail,
        "audit_trail": [
            {
                "id": a.id,
                "event_type": a.event_type,
                "actor": a.actor,
                "target_type": a.target_type,
                "target_id": a.target_id,
                "action_summary": a.action_summary,
                "timestamp": a.timestamp.isoformat(),
            }
            for a in audits
        ],
    }


@router.patch("/investigations/{investigation_id}", tags=["Investigations"])
def update_investigation(
    investigation_id: str,
    req: InvestigationUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    inv = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")

    changes: List[str] = []
    if req.status and req.status != inv.status:
        changes.append(f"status: {inv.status} -> {req.status}")
        inv.status = req.status
    if req.priority and req.priority != inv.priority:
        changes.append(f"priority: {inv.priority} -> {req.priority}")
        inv.priority = req.priority
    if req.assigned_to and req.assigned_to != inv.assigned_to:
        changes.append(f"assigned_to: {inv.assigned_to} -> {req.assigned_to}")
        inv.assigned_to = req.assigned_to
    if req.findings_summary is not None:
        inv.findings_summary = req.findings_summary
        changes.append("updated findings summary")

    inv.updated_at = utcnow()

    if changes:
        db.add(
            InvestigationNote(
                investigation_id=investigation_id,
                author=req.actor,
                note_type="status_change",
                content=f"Updated investigation ({', '.join(changes)}).",
                created_at=utcnow(),
            )
        )
    db.commit()

    record_audit_event(
        db=db,
        event_type="investigation_status_change",
        actor=req.actor,
        target_type="investigation",
        target_id=investigation_id,
        action_summary=f"Updated investigation {investigation_id} ({', '.join(changes) or 'no-op'}).",
        details={"account_id": inv.account_id, "status": inv.status, "priority": inv.priority},
    )
    return get_investigation_detail(investigation_id, db)


@router.post("/investigations/{investigation_id}/notes", tags=["Investigations"])
def add_investigation_note(
    investigation_id: str,
    req: InvestigationNoteCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    inv = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")

    note = InvestigationNote(
        investigation_id=investigation_id,
        author=req.author,
        note_type=req.note_type,
        content=req.content,
        created_at=utcnow(),
    )
    inv.updated_at = utcnow()
    db.add(note)
    db.commit()

    record_audit_event(
        db=db,
        event_type="investigation_note_added",
        actor=req.author,
        target_type="investigation",
        target_id=investigation_id,
        action_summary=f"Added investigative note to {investigation_id} (account {inv.account_id}).",
        details={"account_id": inv.account_id, "note_type": req.note_type},
    )
    return get_investigation_detail(investigation_id, db)


@router.post("/investigations/{investigation_id}/evidence", tags=["Investigations"])
def add_investigation_evidence(
    investigation_id: str,
    req: EvidenceItemCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    inv = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")

    ev = EvidenceItem(
        investigation_id=investigation_id,
        evidence_type=req.evidence_type,
        title=req.title,
        description=req.description,
        reference_id=req.reference_id,
        metadata_json=req.metadata_json,
        added_by=req.added_by,
        created_at=utcnow(),
    )
    inv.updated_at = utcnow()
    db.add(ev)
    db.commit()

    record_audit_event(
        db=db,
        event_type="evidence_added",
        actor=req.added_by,
        target_type="investigation",
        target_id=investigation_id,
        action_summary=f"Attached evidence '{req.title}' ({req.evidence_type}) to {investigation_id}.",
        details={"account_id": inv.account_id, "reference_id": req.reference_id},
    )
    return get_investigation_detail(investigation_id, db)


@router.get("/analytics/risk", tags=["Analytics"])
def api_get_risk_analytics(
    risk_category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return get_risk_analytics_summary(db=db, risk_category=risk_category)


@router.get("/context", tags=["Context"])
def api_get_financial_context() -> Dict[str, Any]:
    return get_financial_context_feed()


@router.get("/audit", tags=["Governance & Audit"])
def list_audit_events(
    event_type: Optional[str] = Query(None),
    actor: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    q = db.query(AuditEvent)
    if event_type and event_type.lower() != "all":
        q = q.filter(AuditEvent.event_type == event_type)
    if actor and actor.lower() != "all":
        q = q.filter(AuditEvent.actor.ilike(f"%{actor}%"))
    if target_type and target_type.lower() != "all":
        q = q.filter(AuditEvent.target_type == target_type)
    if search:
        term = f"%{search.strip()}%"
        q = q.filter(
            or_(
                AuditEvent.action_summary.ilike(term),
                AuditEvent.target_id.ilike(term),
                AuditEvent.actor.ilike(term),
            )
        )

    total = q.count()
    events = q.order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc()).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "actor": e.actor,
                "target_type": e.target_type,
                "target_id": e.target_id,
                "action_summary": e.action_summary,
                "details_json": e.details_json,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events
        ],
    }


@router.get("/models", tags=["Model Management"])
def list_models(db: Session = Depends(get_db)) -> Dict[str, Any]:
    models = db.query(ModelVersion).order_by(ModelVersion.created_at.desc()).all()
    runs = (
        db.query(DatasetTrainingMetadata)
        .order_by(DatasetTrainingMetadata.started_at.desc())
        .limit(15)
        .all()
    )
    return {
        "active_model_version": next((m.model_version for m in models if m.is_active), None),
        "feature_schema": FEATURE_DEFINITIONS,
        "risk_scoring_methodology": RISK_SCORING_METHODOLOGY,
        "thresholds": get_active_thresholds(db),
        "models": [
            {
                "model_version": m.model_version,
                "algorithm": m.algorithm,
                "created_at": m.created_at.isoformat(),
                "dataset_id": m.dataset_id,
                "random_seed": m.random_seed,
                "is_active": m.is_active,
                "passed_evaluation": m.passed_evaluation,
                "artifact_path": m.artifact_path,
                "metrics": m.metrics_json,
                "training_config": m.training_config_json,
                "feature_importance": (m.feature_importance_json or [])[:12],
                "limitations": m.limitations_text,
            }
            for m in models
        ],
        "recent_runs": [
            {
                "run_id": r.run_id,
                "run_type": r.run_type,
                "status": r.status,
                "dataset_id": r.dataset_id,
                "random_seed": r.random_seed,
                "account_count": r.account_count,
                "transaction_count": r.transaction_count,
                "started_at": r.started_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in runs
        ],
    }


@router.post("/models/{model_version}/activate", tags=["Model Management"])
def activate_model_version(
    model_version: str,
    actor: str = Query("ML Governance Lead"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    target = db.query(ModelVersion).filter(ModelVersion.model_version == model_version).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"Model version '{model_version}' not found.")
    if not target.passed_evaluation:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_version}' did not pass minimum evaluation gates and cannot be activated.",
        )

    db.query(ModelVersion).update({ModelVersion.is_active: False})
    target.is_active = True
    db.commit()

    scoring = score_accounts_with_active_model(db=db, model_version_str=model_version, actor=actor)
    record_audit_event(
        db=db,
        event_type="model_activation",
        actor=actor,
        target_type="model",
        target_id=model_version,
        action_summary=f"Activated model version '{model_version}' and re-scored {scoring['total_scored']:,} accounts.",
        details=scoring,
    )
    return {"status": "activated", "model_version": model_version, "scoring_summary": scoring}


@router.get("/settings/thresholds", tags=["Settings"])
def api_get_thresholds(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return {
        "thresholds": get_active_thresholds(db),
        "methodology": RISK_SCORING_METHODOLOGY,
    }


@router.put("/settings/thresholds", tags=["Settings"])
def api_update_thresholds(
    req: RiskThresholdConfig,
    rescore: bool = Query(True),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        updated = update_active_thresholds(
            db=db,
            moderate=req.moderate,
            high=req.high,
            critical=req.critical,
            updated_by=req.updated_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    scoring_res = None
    if rescore and db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first():
        scoring_res = score_accounts_with_active_model(db=db, actor=req.updated_by)

    record_audit_event(
        db=db,
        event_type="threshold_update",
        actor=req.updated_by,
        target_type="system",
        target_id="risk_thresholds",
        action_summary=f"Updated risk score thresholds: Moderate={updated['moderate']}, High={updated['high']}, Critical={updated['critical']}.",
        details={"thresholds": updated, "rescored": rescore},
    )
    return {"thresholds": updated, "scoring_summary": scoring_res}


@router.post("/data/generate", tags=["Data & Pipeline"])
def api_generate_synthetic_data(
    req: SyntheticGenerationRequest,
    background: bool = Query(False),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    def _pipeline_worker(progress_callback: Optional[Callable[[float, str], None]] = None) -> Dict[str, Any]:
        worker_db = SessionLocal()
        try:
            gen_bundle = generate_synthetic_dataset(
                num_accounts=req.num_accounts,
                num_transactions=req.num_transactions,
                random_seed=req.random_seed,
                suspicious_rate=req.suspicious_rate,
                progress_callback=progress_callback,
            )
            persist_res = persist_synthetic_dataset(
                db=worker_db,
                gen_bundle=gen_bundle,
                reset_existing=req.reset_existing,
                actor=req.actor,
            )
            train_res = None
            if req.auto_train_and_score:
                train_res = train_and_evaluate_model(
                    db=worker_db,
                    dataset_id=gen_bundle["dataset_id"],
                    random_seed=req.random_seed,
                    activate_if_passed=True,
                    score_all_accounts=True,
                    actor=req.actor,
                    progress_callback=progress_callback,
                )
            return {
                "generation": persist_res,
                "training": train_res,
            }
        finally:
            worker_db.close()

    if background:
        job = job_manager.run_in_background(
            job_type="synthetic_generation_and_training",
            description=f"Generate {req.num_accounts:,} accounts & {req.num_transactions:,} transactions (seed={req.random_seed})",
            fn=_pipeline_worker,
            metadata=req.model_dump(),
        )
        return {"mode": "background", "job": job}

    res = _pipeline_worker()
    return {"mode": "synchronous", **res}


@router.post("/models/train", tags=["Model Management"])
def api_train_model(
    req: ModelTrainRequest,
    background: bool = Query(False),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    def _train_worker(progress_callback: Optional[Callable[[float, str], None]] = None) -> Dict[str, Any]:
        worker_db = SessionLocal()
        try:
            return train_and_evaluate_model(
                db=worker_db,
                dataset_id=req.dataset_id,
                random_seed=req.random_seed,
                n_estimators=req.n_estimators,
                max_depth=req.max_depth,
                learning_rate=req.learning_rate,
                activate_if_passed=req.activate_if_passed,
                score_all_accounts=req.score_all_accounts,
                actor=req.actor,
                progress_callback=progress_callback,
            )
        finally:
            worker_db.close()

    if background:
        job = job_manager.run_in_background(
            job_type="model_training",
            description=f"Train XGBoost model (n_estimators={req.n_estimators}, max_depth={req.max_depth})",
            fn=_train_worker,
            metadata=req.model_dump(),
        )
        return {"mode": "background", "job": job}

    res = _train_worker()
    return {"mode": "synchronous", **res}


@router.post("/data/validate-import", tags=["Data & Pipeline"])
def api_validate_and_import_dataset(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Validates external/imported JSON records for accounts and transactions, checking schema
    and referential integrity before importing.
    """
    acc_list = payload.get("accounts", [])
    tx_list = payload.get("transactions", [])
    if not acc_list or not tx_list:
        raise HTTPException(status_code=400, detail="Payload must include non-empty 'accounts' and 'transactions' lists.")

    acc_df = pd.DataFrame(acc_list)
    tx_df = pd.DataFrame(tx_list)
    val_res = validate_dataset_frames(acc_df, tx_df)
    if not val_res["valid"]:
        raise HTTPException(status_code=400, detail={"message": "Dataset validation failed", "errors": val_res["errors"]})

    record_audit_event(
        db=db,
        event_type="dataset_import",
        actor=payload.get("actor", "Data Engineer"),
        target_type="dataset",
        target_id=payload.get("dataset_id", "imported-batch"),
        action_summary=f"Validated dataset batch ({len(acc_df)} accounts, {len(tx_df)} transactions).",
        details=val_res,
    )
    return {"status": "validated", "validation": val_res}


@router.post("/settings/reset-db", tags=["Settings"])
def api_reset_database(
    actor: str = Query("System Administrator"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        reset_db(force=False)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    record_audit_event(
        db=db,
        event_type="database_reset",
        actor=actor,
        target_type="system",
        target_id="database",
        action_summary="Development database was reset to a clean state.",
    )
    return {"status": "reset_complete"}


@router.get("/jobs", tags=["System"])
def api_list_jobs() -> Dict[str, Any]:
    return {"items": job_manager.list_jobs()}


@router.get("/jobs/{job_id}", tags=["System"])
def api_get_job(job_id: str) -> Dict[str, Any]:
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job

