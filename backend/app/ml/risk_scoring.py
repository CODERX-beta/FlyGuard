from typing import Any, Dict, List, Optional
import numpy as np
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.models.entities import SystemConfig, utcnow

RISK_SCORING_METHODOLOGY = {
    "title": "FlyGuard AI Multi-Stage Risk Scoring & Triage Layer",
    "disclaimer": (
        "A normalized risk score is an investigative triage signal on a 0-100 index, NOT a direct percentage "
        "probability of criminal guilt. A score of 80 does NOT mean an 80% probability of money laundering. "
        "All high-risk predictions require human investigator review and corroborating evidence."
    ),
    "stages": [
        {
            "stage": 1,
            "field": "raw_probability",
            "description": "Unadjusted logistic output probability from the XGBoost ensemble classifier.",
        },
        {
            "stage": 2,
            "field": "calibrated_probability",
            "description": "Empirical probability calibrated on the held-out validation split via isotonic regression.",
        },
        {
            "stage": 3,
            "field": "normalized_risk_score",
            "description": (
                "Piecewise-linear monotonic mapping of calibrated probability onto a 0-100 operational triage scale: "
                "[0.00-0.15 -> 0-35], [0.15-0.45 -> 35-65], [0.45-0.78 -> 65-85], [0.78-1.00 -> 85-100]."
            ),
        },
        {
            "stage": 4,
            "field": "risk_category",
            "description": "Configurable categorical band (Low, Moderate, High, Critical) applied to the normalized score.",
        },
        {
            "stage": 5,
            "field": "alert_priority",
            "description": "Operational queue priority (None, Low, Medium, High, Urgent) for AML triage workflows.",
        },
    ],
}


def get_active_thresholds(db: Optional[Session] = None) -> Dict[str, float]:
    default_thresholds = {
        "moderate": float(settings.risk_threshold_moderate),
        "high": float(settings.risk_threshold_high),
        "critical": float(settings.risk_threshold_critical),
    }
    if db is None:
        return default_thresholds
    try:
        cfg = db.query(SystemConfig).filter(SystemConfig.config_key == "risk_thresholds").first()
        if cfg and isinstance(cfg.config_value_json, dict):
            return {
                "moderate": float(cfg.config_value_json.get("moderate", default_thresholds["moderate"])),
                "high": float(cfg.config_value_json.get("high", default_thresholds["high"])),
                "critical": float(cfg.config_value_json.get("critical", default_thresholds["critical"])),
            }
    except Exception:
        pass
    return default_thresholds


def update_active_thresholds(
    db: Session,
    moderate: float,
    high: float,
    critical: float,
    updated_by: str = "Analyst",
) -> Dict[str, float]:
    if not (5.0 <= moderate < high < critical <= 99.0):
        raise ValueError(
            "Invalid threshold ordering: must satisfy 5 <= moderate < high < critical <= 99."
        )
    payload = {
        "moderate": round(float(moderate), 2),
        "high": round(float(high), 2),
        "critical": round(float(critical), 2),
    }
    cfg = db.query(SystemConfig).filter(SystemConfig.config_key == "risk_thresholds").first()
    if cfg:
        cfg.config_value_json = payload
        cfg.updated_at = utcnow()
        cfg.updated_by = updated_by
    else:
        cfg = SystemConfig(
            config_key="risk_thresholds",
            config_value_json=payload,
            updated_at=utcnow(),
            updated_by=updated_by,
        )
        db.add(cfg)
    db.commit()
    return payload


def probability_to_normalized_score(calibrated_prob: np.ndarray | float) -> np.ndarray | float:
    """
    Maps calibrated probability [0.0, 1.0] onto a 0-100 operational triage scale using a documented
    monotonic piecewise-linear function.
    """
    xp = np.array([0.0, 0.15, 0.45, 0.78, 1.00], dtype=np.float64)
    fp = np.array([0.0, 35.0, 65.0, 85.0, 100.0], dtype=np.float64)
    arr = np.clip(np.asarray(calibrated_prob, dtype=np.float64), 0.0, 1.0)
    scores = np.interp(arr, xp, fp)
    if np.isscalar(calibrated_prob):
        return round(float(scores), 2)
    return np.round(scores, 2)


def classify_risk_score(
    score: float,
    thresholds: Optional[Dict[str, float]] = None,
) -> Dict[str, str]:
    if thresholds is None:
        thresholds = get_active_thresholds(None)

    mod_t = thresholds["moderate"]
    high_t = thresholds["high"]
    crit_t = thresholds["critical"]

    if score >= crit_t:
        return {"risk_category": "Critical", "alert_priority": "Urgent"}
    elif score >= high_t:
        return {"risk_category": "High", "alert_priority": "High"}
    elif score >= mod_t:
        return {"risk_category": "Moderate", "alert_priority": "Medium"}
    else:
        return {"risk_category": "Low", "alert_priority": "None"}

