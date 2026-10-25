from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    CheckConstraint,
)
from sqlalchemy.orm import relationship
from backend.app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Account(Base):
    __tablename__ = "accounts"

    account_id = Column(String(64), primary_key=True, index=True)
    account_type = Column(String(50), nullable=False, index=True)
    customer_segment = Column(String(50), nullable=False, default="retail")
    created_at = Column(DateTime, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="active", index=True)
    synthetic_region = Column(String(64), nullable=True, index=True)
    synthetic_country_code = Column(String(8), nullable=True, index=True)
    synthetic_lat = Column(Float, nullable=True)
    synthetic_lng = Column(Float, nullable=True)
    kyc_tier = Column(String(32), nullable=False, default="tier_2")
    declared_monthly_turnover = Column(Float, nullable=False, default=5000.0)
    primary_currency = Column(String(8), nullable=False, default="USD")
    is_synthetic = Column(Boolean, nullable=False, default=True)
    dataset_id = Column(String(64), nullable=False, default="default", index=True)
    metadata_json = Column(JSON, nullable=True)

    outgoing_transactions = relationship(
        "Transaction",
        foreign_keys="Transaction.sender_account_id",
        back_populates="sender",
        cascade="all, delete-orphan",
    )
    incoming_transactions = relationship(
        "Transaction",
        foreign_keys="Transaction.receiver_account_id",
        back_populates="receiver",
        cascade="all, delete-orphan",
    )
    label = relationship(
        "SyntheticLabel",
        back_populates="account",
        uselist=False,
        cascade="all, delete-orphan",
    )
    feature_snapshots = relationship(
        "FeatureSnapshot",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    predictions = relationship(
        "ModelPrediction",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    alerts = relationship(
        "Alert",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    investigations = relationship(
        "Investigation",
        back_populates="account",
        cascade="all, delete-orphan",
    )


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(String(64), primary_key=True, index=True)
    sender_account_id = Column(
        String(64),
        ForeignKey("accounts.account_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    receiver_account_id = Column(
        String(64),
        ForeignKey("accounts.account_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timestamp = Column(DateTime, nullable=False, index=True)
    amount = Column(Float, nullable=False, index=True)
    currency = Column(String(8), nullable=False, default="USD")
    channel = Column(String(32), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="completed", index=True)
    is_synthetic = Column(Boolean, nullable=False, default=True)
    dataset_id = Column(String(64), nullable=False, default="default", index=True)
    metadata_json = Column(JSON, nullable=True)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transaction_positive_amount"),
        Index("ix_tx_sender_timestamp", "sender_account_id", "timestamp"),
        Index("ix_tx_receiver_timestamp", "receiver_account_id", "timestamp"),
    )

    sender = relationship(
        "Account",
        foreign_keys=[sender_account_id],
        back_populates="outgoing_transactions",
    )
    receiver = relationship(
        "Account",
        foreign_keys=[receiver_account_id],
        back_populates="incoming_transactions",
    )


class SyntheticLabel(Base):
    """
    Isolated label table for synthetic or imported training examples.
    Strictly separated from feature engineering inputs to prevent label/scenario leakage.
    """

    __tablename__ = "synthetic_labels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(
        String(64),
        ForeignKey("accounts.account_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    is_suspicious_mule = Column(Integer, nullable=False, index=True)
    archetype_category = Column(String(64), nullable=False, index=True)
    scenario_group_id = Column(String(64), nullable=True, index=True)
    label_source = Column(String(32), nullable=False, default="synthetic_generator")
    label_provenance = Column(JSON, nullable=True)
    dataset_id = Column(String(64), nullable=False, default="default", index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    account = relationship("Account", back_populates="label")


class FeatureSnapshot(Base):
    __tablename__ = "feature_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(
        String(64),
        ForeignKey("accounts.account_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_timestamp = Column(DateTime, nullable=False, index=True)
    feature_version = Column(String(32), nullable=False, default="v1")
    features_json = Column(JSON, nullable=False)
    incoming_tx_count = Column(Integer, nullable=False, default=0)
    outgoing_tx_count = Column(Integer, nullable=False, default=0)
    incoming_volume = Column(Float, nullable=False, default=0.0)
    outgoing_volume = Column(Float, nullable=False, default=0.0)
    unique_counterparties = Column(Integer, nullable=False, default=0)
    last_activity_at = Column(DateTime, nullable=True, index=True)

    __table_args__ = (
        Index("ix_feature_account_snapshot", "account_id", "snapshot_timestamp"),
    )

    account = relationship("Account", back_populates="feature_snapshots")


class ModelVersion(Base):
    __tablename__ = "model_versions"

    model_version = Column(String(64), primary_key=True, index=True)
    algorithm = Column(String(64), nullable=False, default="XGBClassifier")
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    dataset_id = Column(String(64), nullable=False)
    random_seed = Column(Integer, nullable=False, default=42)
    is_active = Column(Boolean, nullable=False, default=False, index=True)
    passed_evaluation = Column(Boolean, nullable=False, default=False)
    artifact_path = Column(String(256), nullable=False)
    metadata_path = Column(String(256), nullable=False)
    feature_schema_json = Column(JSON, nullable=False)
    metrics_json = Column(JSON, nullable=False)
    training_config_json = Column(JSON, nullable=False)
    feature_importance_json = Column(JSON, nullable=False)
    limitations_text = Column(Text, nullable=False)

    predictions = relationship(
        "ModelPrediction",
        back_populates="model",
        cascade="all, delete-orphan",
    )


class ModelPrediction(Base):
    __tablename__ = "model_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(
        String(64),
        ForeignKey("accounts.account_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_version = Column(
        String(64),
        ForeignKey("model_versions.model_version", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    predicted_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    raw_probability = Column(Float, nullable=False)
    calibrated_probability = Column(Float, nullable=False)
    normalized_risk_score = Column(Float, nullable=False, index=True)
    risk_category = Column(String(32), nullable=False, index=True)
    alert_priority = Column(String(32), nullable=False, index=True)
    top_factors_json = Column(JSON, nullable=True)
    explanation_summary = Column(String(512), nullable=True)

    __table_args__ = (
        Index("ix_pred_account_score", "account_id", "normalized_risk_score"),
    )

    account = relationship("Account", back_populates="predictions")
    model = relationship("ModelVersion", back_populates="predictions")


class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(String(64), primary_key=True, index=True)
    account_id = Column(
        String(64),
        ForeignKey("accounts.account_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_version = Column(String(64), nullable=False)
    risk_score = Column(Float, nullable=False, index=True)
    risk_category = Column(String(32), nullable=False, index=True)
    priority = Column(String(32), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="open", index=True)
    reason_summary = Column(String(512), nullable=False)
    triggered_factors_json = Column(JSON, nullable=True)
    assigned_to = Column(String(64), nullable=True)
    decision_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=utcnow)

    account = relationship("Account", back_populates="alerts")


class Investigation(Base):
    __tablename__ = "investigations"

    investigation_id = Column(String(64), primary_key=True, index=True)
    account_id = Column(
        String(64),
        ForeignKey("accounts.account_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(256), nullable=False)
    status = Column(String(48), nullable=False, default="open", index=True)
    priority = Column(String(32), nullable=False, default="high", index=True)
    assigned_to = Column(String(64), nullable=False, default="Unassigned")
    risk_score_at_open = Column(Float, nullable=False, default=0.0)
    findings_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=utcnow, index=True)

    account = relationship("Account", back_populates="investigations")
    notes = relationship(
        "InvestigationNote",
        back_populates="investigation",
        cascade="all, delete-orphan",
        order_by="InvestigationNote.created_at.desc()",
    )
    evidence_items = relationship(
        "EvidenceItem",
        back_populates="investigation",
        cascade="all, delete-orphan",
        order_by="EvidenceItem.created_at.desc()",
    )


class InvestigationNote(Base):
    __tablename__ = "investigation_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    investigation_id = Column(
        String(64),
        ForeignKey("investigations.investigation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author = Column(String(64), nullable=False, default="Analyst")
    note_type = Column(String(32), nullable=False, default="analyst_note")
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)

    investigation = relationship("Investigation", back_populates="notes")


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    investigation_id = Column(
        String(64),
        ForeignKey("investigations.investigation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_type = Column(String(48), nullable=False)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=False)
    reference_id = Column(String(64), nullable=True)
    metadata_json = Column(JSON, nullable=True)
    added_by = Column(String(64), nullable=False, default="Analyst")
    created_at = Column(DateTime, nullable=False, default=utcnow)

    investigation = relationship("Investigation", back_populates="evidence_items")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(64), nullable=False, index=True)
    actor = Column(String(64), nullable=False, default="System", index=True)
    target_type = Column(String(48), nullable=False, index=True)
    target_id = Column(String(64), nullable=False, index=True)
    action_summary = Column(String(512), nullable=False)
    details_json = Column(JSON, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=utcnow, index=True)


class DatasetTrainingMetadata(Base):
    __tablename__ = "dataset_training_metadata"

    run_id = Column(String(64), primary_key=True, index=True)
    run_type = Column(String(48), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    dataset_id = Column(String(64), nullable=False, index=True)
    random_seed = Column(Integer, nullable=True)
    account_count = Column(Integer, nullable=False, default=0)
    transaction_count = Column(Integer, nullable=False, default=0)
    parameters_json = Column(JSON, nullable=True)
    summary_json = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


class SystemConfig(Base):
    __tablename__ = "system_configs"

    config_key = Column(String(64), primary_key=True)
    config_value_json = Column(JSON, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=utcnow)
    updated_by = Column(String(64), nullable=False, default="System")

