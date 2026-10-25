from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from backend.app.models.entities import AuditEvent, utcnow

SENSITIVE_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "authorization",
    "credential",
    "ssn",
}


def sanitize_audit_payload(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if payload is None:
        return None
    sanitized: Dict[str, Any] = {}
    for k, v in payload.items():
        key_lower = str(k).lower()
        if any(s in key_lower for s in SENSITIVE_KEYS):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_audit_payload(v)
        else:
            sanitized[k] = v
    return sanitized


def record_audit_event(
    db: Session,
    event_type: str,
    actor: str,
    target_type: str,
    target_id: str,
    action_summary: str,
    details: Optional[Dict[str, Any]] = None,
    commit: bool = True,
) -> AuditEvent:
    clean_details = sanitize_audit_payload(details)
    event = AuditEvent(
        event_type=event_type,
        actor=actor or "System",
        target_type=target_type,
        target_id=str(target_id),
        action_summary=action_summary,
        details_json=clean_details,
        timestamp=utcnow(),
    )
    db.add(event)
    if commit:
        db.commit()
        db.refresh(event)
    return event

