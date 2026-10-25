from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.ml.risk_scoring import RISK_SCORING_METHODOLOGY, get_active_thresholds
from backend.app.models.entities import (
    Account,
    Alert,
    DatasetTrainingMetadata,
    FeatureSnapshot,
    Investigation,
    ModelPrediction,
    ModelVersion,
    SyntheticLabel,
    Transaction,
)


def get_overview_intelligence(db: Session) -> Dict[str, Any]:
    total_accounts = db.query(func.count(Account.account_id)).scalar() or 0
    total_transactions = db.query(func.count(Transaction.transaction_id)).scalar() or 0
    total_volume = float(db.query(func.sum(Transaction.amount)).scalar() or 0.0)

    active_model = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()
    active_ver = active_model.model_version if active_model else None

    cat_rows = (
        db.query(ModelPrediction.risk_category, func.count(ModelPrediction.id))
        .group_by(ModelPrediction.risk_category)
        .all()
    )
    risk_dist = {"Low": 0, "Moderate": 0, "High": 0, "Critical": 0}
    for cat, cnt in cat_rows:
        if cat in risk_dist:
            risk_dist[cat] = int(cnt)

    high_risk_accounts = risk_dist["High"] + risk_dist["Critical"]
    critical_accounts = risk_dist["Critical"]

    open_alerts = (
        db.query(func.count(Alert.alert_id))
        .filter(Alert.status.in_(["open", "in_review", "escalated"]))
        .scalar()
        or 0
    )
    active_investigations = (
        db.query(func.count(Investigation.investigation_id))
        .filter(Investigation.status.in_(["open", "in_progress", "escalated_sar"]))
        .scalar()
        or 0
    )

    # Transaction volume trends (last 14 days of dataset timeline)
    max_ts = db.query(func.max(Transaction.timestamp)).scalar()
    volume_trends: List[Dict[str, Any]] = []
    if max_ts:
        start_trend = max_ts - timedelta(days=13)
        recent_txs = (
            db.query(
                Transaction.timestamp,
                Transaction.amount,
                Transaction.sender_account_id,
                Transaction.receiver_account_id,
            )
            .filter(Transaction.timestamp >= start_trend)
            .all()
        )
        high_risk_ids = {
            r[0]
            for r in db.query(ModelPrediction.account_id)
            .filter(ModelPrediction.risk_category.in_(["High", "Critical"]))
            .all()
        }
        daily_tot: Dict[str, float] = defaultdict(float)
        daily_susp: Dict[str, float] = defaultdict(float)
        daily_cnt: Dict[str, int] = defaultdict(int)
        for ts, amt, s_id, r_id in recent_txs:
            day_str = ts.strftime("%Y-%m-%d")
            daily_tot[day_str] += float(amt)
            daily_cnt[day_str] += 1
            if s_id in high_risk_ids or r_id in high_risk_ids:
                daily_susp[day_str] += float(amt)

        for d_offset in range(14):
            d_str = (start_trend + timedelta(days=d_offset)).strftime("%Y-%m-%d")
            volume_trends.append(
                {
                    "date": d_str,
                    "total_volume": round(daily_tot.get(d_str, 0.0), 2),
                    "suspicious_volume": round(daily_susp.get(d_str, 0.0), 2),
                    "transaction_count": daily_cnt.get(d_str, 0),
                }
            )

    # Recent alerts
    recent_alerts_q = db.query(Alert).order_by(Alert.risk_score.desc(), Alert.created_at.desc()).limit(8).all()
    recent_alerts = [
        {
            "alert_id": a.alert_id,
            "account_id": a.account_id,
            "risk_score": a.risk_score,
            "risk_category": a.risk_category,
            "priority": a.priority,
            "status": a.status,
            "reason_summary": a.reason_summary,
            "created_at": a.created_at.isoformat(),
        }
        for a in recent_alerts_q
    ]

    # Recently investigated accounts
    recent_invs_q = (
        db.query(Investigation).order_by(Investigation.updated_at.desc()).limit(6).all()
    )
    recent_investigations = [
        {
            "investigation_id": inv.investigation_id,
            "account_id": inv.account_id,
            "title": inv.title,
            "status": inv.status,
            "priority": inv.priority,
            "assigned_to": inv.assigned_to,
            "risk_score_at_open": inv.risk_score_at_open,
            "updated_at": inv.updated_at.isoformat(),
        }
        for inv in recent_invs_q
    ]

    # Top synthetic regions by high-risk account concentration
    reg_rows = (
        db.query(
            Account.synthetic_region,
            Account.synthetic_country_code,
            func.count(Account.account_id),
            func.avg(ModelPrediction.normalized_risk_score),
        )
        .join(ModelPrediction, Account.account_id == ModelPrediction.account_id)
        .filter(ModelPrediction.risk_category.in_(["High", "Critical"]))
        .group_by(Account.synthetic_region, Account.synthetic_country_code)
        .order_by(func.count(Account.account_id).desc())
        .limit(6)
        .all()
    )
    regional_breakdown = [
        {
            "region": r[0] or "Unspecified",
            "country_code": r[1] or "UN",
            "flagged_count": int(r[2]),
            "share_pct": round(100.0 * int(r[2]) / max(1, high_risk_accounts), 1),
            "avg_risk_score": round(float(r[3] or 0.0), 1),
        }
        for r in reg_rows
    ]

    # Recent high-risk transaction feed
    recent_feed_q = (
        db.query(Transaction, ModelPrediction.normalized_risk_score, ModelPrediction.risk_category)
        .join(ModelPrediction, Transaction.sender_account_id == ModelPrediction.account_id)
        .filter(ModelPrediction.risk_category.in_(["High", "Critical"]))
        .order_by(Transaction.timestamp.desc())
        .limit(8)
        .all()
    )
    live_feed = [
        {
            "transaction_id": tx.transaction_id,
            "sender_account_id": tx.sender_account_id,
            "receiver_account_id": tx.receiver_account_id,
            "amount": tx.amount,
            "currency": tx.currency,
            "channel": tx.channel,
            "timestamp": tx.timestamp.isoformat(),
            "sender_risk_score": round(float(score), 1),
            "sender_risk_category": cat,
        }
        for tx, score, cat in recent_feed_q
    ]

    # High-risk network summaries (top flagged accounts by degree + volume)
    top_network_hubs_q = (
        db.query(Account, ModelPrediction, FeatureSnapshot)
        .join(ModelPrediction, Account.account_id == ModelPrediction.account_id)
        .join(FeatureSnapshot, Account.account_id == FeatureSnapshot.account_id)
        .filter(ModelPrediction.risk_category.in_(["Critical", "High"]))
        .order_by(ModelPrediction.normalized_risk_score.desc())
        .limit(5)
        .all()
    )
    high_risk_networks = [
        {
            "hub_account_id": acc.account_id,
            "synthetic_region": acc.synthetic_region,
            "risk_score": pred.normalized_risk_score,
            "risk_category": pred.risk_category,
            "unique_counterparties": snap.unique_counterparties,
            "total_turnover": round(float(snap.incoming_volume + snap.outgoing_volume), 2),
            "pattern_summary": pred.explanation_summary,
        }
        for acc, pred, snap in top_network_hubs_q
    ]

    return {
        "kpis": {
            "total_accounts": total_accounts,
            "total_transactions": total_transactions,
            "total_volume": round(total_volume, 2),
            "high_risk_accounts": high_risk_accounts,
            "critical_accounts": critical_accounts,
            "open_alerts": open_alerts,
            "active_investigations": active_investigations,
            "active_model_version": active_ver,
            "last_data_timestamp": max_ts.isoformat() if max_ts else None,
        },
        "risk_distribution": risk_dist,
        "volume_trends": volume_trends,
        "recent_alerts": recent_alerts,
        "recent_investigations": recent_investigations,
        "regional_breakdown": regional_breakdown,
        "live_transaction_feed": live_feed,
        "high_risk_networks": high_risk_networks,
        "is_synthetic_data": True,
    }


def get_global_activity_map_data(
    db: Session,
    min_amount: float = 0.0,
    risk_filter: str = "all",
    days: int = 90,
) -> Dict[str, Any]:
    """
    Aggregates synthetic regional hubs and cross-region transaction corridors where supporting
    synthetic coordinate metadata exists. Explicitly marks all geographic data as synthetic.
    """
    max_ts = db.query(func.max(Transaction.timestamp)).scalar()
    cutoff_ts = (max_ts - timedelta(days=days)) if max_ts else None

    hub_rows = (
        db.query(
            Account.synthetic_region,
            Account.synthetic_country_code,
            func.avg(Account.synthetic_lat),
            func.avg(Account.synthetic_lng),
            func.count(Account.account_id),
            func.avg(ModelPrediction.normalized_risk_score),
        )
        .outerjoin(ModelPrediction, Account.account_id == ModelPrediction.account_id)
        .filter(Account.synthetic_region.isnot(None))
        .group_by(Account.synthetic_region, Account.synthetic_country_code)
        .all()
    )

    flagged_by_reg = dict(
        db.query(Account.synthetic_region, func.count(Account.account_id))
        .join(ModelPrediction, Account.account_id == ModelPrediction.account_id)
        .filter(ModelPrediction.risk_category.in_(["High", "Critical"]))
        .group_by(Account.synthetic_region)
        .all()
    )

    hubs: List[Dict[str, Any]] = []
    hub_coords: Dict[str, Dict[str, Any]] = {}
    for reg, country, lat, lng, cnt, avg_score in hub_rows:
        if lat is None or lng is None:
            continue
        flagged_cnt = int(flagged_by_reg.get(reg, 0))
        hub_info = {
            "region": reg,
            "country_code": country,
            "lat": round(float(lat), 4),
            "lng": round(float(lng), 4),
            "total_accounts": int(cnt),
            "flagged_accounts": flagged_cnt,
            "avg_risk_score": round(float(avg_score or 0.0), 2),
            "is_synthetic_location": True,
        }
        hubs.append(hub_info)
        hub_coords[reg] = hub_info

    # Sample recent high-value or high-risk transactions for cross-region corridors
    tx_q = db.query(Transaction)
    if cutoff_ts:
        tx_q = tx_q.filter(Transaction.timestamp >= cutoff_ts)
    if min_amount > 0:
        tx_q = tx_q.filter(Transaction.amount >= min_amount)

    sample_txs = tx_q.order_by(Transaction.amount.desc()).limit(1500).all()
    involved_ids = {t.sender_account_id for t in sample_txs} | {t.receiver_account_id for t in sample_txs}

    acc_reg_map: Dict[str, str] = {}
    acc_score_map: Dict[str, float] = {}
    acc_cat_map: Dict[str, str] = {}

    if involved_ids:
        id_list = list(involved_ids)
        for aid, s_reg in db.query(Account.account_id, Account.synthetic_region).filter(Account.account_id.in_(id_list)).all():
            if s_reg:
                acc_reg_map[aid] = s_reg
        for aid, sc, cat in (
            db.query(
                ModelPrediction.account_id,
                ModelPrediction.normalized_risk_score,
                ModelPrediction.risk_category,
            )
            .filter(ModelPrediction.account_id.in_(id_list))
            .all()
        ):
            acc_score_map[aid] = float(sc)
            acc_cat_map[aid] = str(cat)

    corridor_agg: Dict[ tuple, Dict[str, Any] ] = {}
    for tx in sample_txs:
        s_reg = acc_reg_map.get(tx.sender_account_id)
        r_reg = acc_reg_map.get(tx.receiver_account_id)
        if not s_reg or not r_reg or s_reg == r_reg:
            continue
        if s_reg not in hub_coords or r_reg not in hub_coords:
            continue

        max_cat = acc_cat_map.get(tx.sender_account_id, "Low")
        max_sc = max(
            acc_score_map.get(tx.sender_account_id, 0.0),
            acc_score_map.get(tx.receiver_account_id, 0.0),
        )
        if risk_filter == "high_only" and max_sc < 65.0:
            continue
        if risk_filter == "critical_only" and max_sc < 85.0:
            continue

        key = (s_reg, r_reg)
        if key not in corridor_agg:
            corridor_agg[key] = {
                "corridor_id": f"{s_reg} -> {r_reg}",
                "source_region": s_reg,
                "target_region": r_reg,
                "source_lat": hub_coords[s_reg]["lat"],
                "source_lng": hub_coords[s_reg]["lng"],
                "target_lat": hub_coords[r_reg]["lat"],
                "target_lng": hub_coords[r_reg]["lng"],
                "transaction_count": 0,
                "total_volume": 0.0,
                "max_risk_score": 0.0,
                "sample_transaction_id": tx.transaction_id,
                "sample_sender": tx.sender_account_id,
                "sample_receiver": tx.receiver_account_id,
            }
        c = corridor_agg[key]
        c["transaction_count"] += 1
        c["total_volume"] = round(c["total_volume"] + float(tx.amount), 2)
        c["max_risk_score"] = round(max(c["max_risk_score"], max_sc), 1)

    corridors = sorted(
        list(corridor_agg.values()), key=lambda x: x["total_volume"], reverse=True
    )[:30]

    return {
        "synthetic_disclaimer": (
            "SYNTHETIC GEOGRAPHIC DATA: Regional hubs and transfer corridors represent simulated regional metadata "
            "assigned by the synthetic generator. Precise street/GPS coordinates are never fabricated for accounts."
        ),
        "hubs": hubs,
        "corridors": corridors,
        "filters_applied": {
            "min_amount": min_amount,
            "risk_filter": risk_filter,
            "days": days,
        },
    }


def get_risk_analytics_summary(
    db: Session,
    risk_category: Optional[str] = None,
) -> Dict[str, Any]:
    active_model = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()
    thresholds = get_active_thresholds(db)

    # Risk score histogram in 10-point buckets (0-10, 10-20, ..., 90-100)
    preds_q = db.query(ModelPrediction.normalized_risk_score, ModelPrediction.risk_category)
    if risk_category and risk_category != "all":
        preds_q = preds_q.filter(ModelPrediction.risk_category == risk_category)
    pred_rows = preds_q.all()

    buckets = [
        {"range": f"{b}-{b + 10}", "min": b, "max": b + 10, "count": 0}
        for b in range(0, 100, 10)
    ]
    cat_counts = {"Low": 0, "Moderate": 0, "High": 0, "Critical": 0}
    for sc, cat in pred_rows:
        idx = min(9, max(0, int(float(sc) // 10)))
        buckets[idx]["count"] += 1
        if cat in cat_counts:
            cat_counts[cat] += 1

    # Channel analytics
    ch_rows = (
        db.query(
            Transaction.channel,
            func.count(Transaction.transaction_id),
            func.sum(Transaction.amount),
            func.avg(Transaction.amount),
        )
        .group_by(Transaction.channel)
        .all()
    )
    channel_patterns = [
        {
            "channel": ch,
            "transaction_count": int(cnt),
            "total_volume": round(float(vol or 0.0), 2),
            "avg_amount": round(float(avg_a or 0.0), 2),
        }
        for ch, cnt, vol, avg_a in ch_rows
    ]
    channel_patterns.sort(key=lambda x: x["total_volume"], reverse=True)

    # Archetype risk comparison (how the model scores each synthetic archetype)
    arch_rows = (
        db.query(
            SyntheticLabel.archetype_category,
            SyntheticLabel.is_suspicious_mule,
            func.count(SyntheticLabel.id),
            func.avg(ModelPrediction.normalized_risk_score),
        )
        .join(ModelPrediction, SyntheticLabel.account_id == ModelPrediction.account_id)
        .group_by(SyntheticLabel.archetype_category, SyntheticLabel.is_suspicious_mule)
        .all()
    )
    archetype_analytics = [
        {
            "archetype": arch,
            "ground_truth_is_mule": bool(is_mule),
            "account_count": int(cnt),
            "avg_predicted_risk_score": round(float(avg_sc or 0.0), 2),
        }
        for arch, is_mule, cnt, avg_sc in arch_rows
    ]
    archetype_analytics.sort(key=lambda x: x["avg_predicted_risk_score"], reverse=True)

    return {
        "active_model_version": active_model.model_version if active_model else None,
        "thresholds": thresholds,
        "risk_scoring_methodology": RISK_SCORING_METHODOLOGY,
        "score_histogram": buckets,
        "category_distribution": cat_counts,
        "channel_patterns": channel_patterns,
        "archetype_analytics": archetype_analytics,
        "model_metrics": active_model.metrics_json if active_model else None,
        "feature_importance": (active_model.feature_importance_json or [])[:12] if active_model else [],
        "limitations": active_model.limitations_text if active_model else "",
    }


def get_financial_context_feed() -> Dict[str, Any]:
    """
    Returns clearly labeled reference AML typologies and public regulatory context without pretending
    to stream live external market feeds.
    """
    return {
        "mode": "offline_reference_typologies",
        "live_api_configured": False,
        "honest_status_banner": (
            "OFFLINE TYPOLOGY & REGULATORY REFERENCE MODE: No external news or live market API is configured. "
            "Below are curated Financial Action Task Force (FATF) and FinCEN money-mule typology advisories "
            "used to contextualize model signals during local investigations."
        ),
        "typology_advisories": [
            {
                "id": "CTX-FATF-01",
                "category": "AML Typology",
                "title": "Rapid Pass-Through & Short Holding-Time Mule Funnels",
                "authority": "FATF / Egmont Group Typology Brief",
                "severity": "High",
                "summary": (
                    "Professional money-mule networks frequently receive P2P or wire inflows from multiple unrelated "
                    "victims and forward 90-98% of funds within 3 hours via instant rails or crypto off-ramps."
                ),
                "corroborating_features": [
                    "rapid_passthrough_ratio",
                    "median_holding_time_hours",
                    "passthrough_symmetry_score",
                ],
                "false_positive_guidance": (
                    "Verify whether the account belongs to a licensed payment aggregator, escrow service, or active merchant."
                ),
            },
            {
                "id": "CTX-FINCEN-02",
                "category": "Structuring & Smurfing",
                "title": "Fan-Out Splitting Below Reporting Thresholds",
                "authority": "FinCEN Financial Crime Advisory",
                "severity": "High",
                "summary": (
                    "Layering nodes often receive consolidated wire deposits and rapidly disperse funds across 5-15 "
                    "distinct destination accounts in increments below statutory reporting thresholds."
                ),
                "corroborating_features": [
                    "out_degree",
                    "in_out_count_ratio",
                    "turnover_to_declared_ratio",
                ],
                "false_positive_guidance": (
                    "Compare outbound destinations against recurring vendor or payroll disbursements in small business accounts."
                ),
            },
            {
                "id": "CTX-EBA-03",
                "category": "Account Takeover / Dormant Mule",
                "title": "Dormant Account Reactivation & Velocity Spike",
                "authority": "European Banking Authority (EBA) Risk Guidelines",
                "severity": "Critical",
                "summary": (
                    "Seasoned accounts that remain inactive for 60+ days and abruptly process high-value cross-border "
                    "or instant transfers exceeding 5x declared monthly turnover warrant immediate review."
                ),
                "corroborating_features": [
                    "dormancy_burst_indicator",
                    "dormancy_gap_days",
                    "burst_ratio_7d_vs_90d",
                ],
                "false_positive_guidance": (
                    "Check for legitimate life events such as property sales, tuition payments, or seasonal business cycles."
                ),
            },
            {
                "id": "CTX-GRAPH-04",
                "category": "Network Topology",
                "title": "Circular Layering Rings & Multi-Hop Chains",
                "authority": "Financial Intelligence Unit (FIU) Graph Playbook",
                "severity": "High",
                "summary": (
                    "Closed directed loops (A -> B -> C -> D -> A) and 4-hop sequential chains obscure beneficial "
                    "ownership and audit trails across accounts."
                ),
                "corroborating_features": [
                    "cycle_participation_score",
                    "pagerank_score",
                    "clustering_coefficient",
                ],
                "false_positive_guidance": (
                    "Distinguish circular layering from small household expense-sharing groups by checking holding times and volumes."
                ),
            },
        ],
    }

