from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    environment: str
    active_model_version: Optional[str] = None
    timestamp: datetime


class DatabaseHealthResponse(BaseModel):
    status: str
    engine: str
    accounts_count: int
    transactions_count: int
    flagged_accounts_count: int
    open_alerts_count: int
    active_investigations_count: int
    latest_dataset_id: Optional[str] = None


class RiskThresholdConfig(BaseModel):
    moderate: float = Field(default=35.0, ge=5.0, le=90.0)
    high: float = Field(default=65.0, ge=10.0, le=95.0)
    critical: float = Field(default=85.0, ge=20.0, le=99.0)
    updated_by: str = "Analyst"


class ShapContribution(BaseModel):
    feature: str
    display_name: str
    feature_value: float
    shap_value: float
    direction: str  # "increases_risk" | "decreases_risk"
    description: str


class AccountSummarySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: str
    account_type: str
    customer_segment: str
    created_at: datetime
    status: str
    synthetic_region: Optional[str] = None
    synthetic_country_code: Optional[str] = None
    kyc_tier: str
    declared_monthly_turnover: float
    primary_currency: str
    is_synthetic: bool = True
    risk_score: float = 0.0
    raw_probability: float = 0.0
    calibrated_probability: float = 0.0
    risk_category: str = "Low"
    alert_priority: str = "None"
    incoming_tx_count: int = 0
    outgoing_tx_count: int = 0
    incoming_volume: float = 0.0
    outgoing_volume: float = 0.0
    unique_counterparties: int = 0
    last_activity_at: Optional[datetime] = None
    explanation_summary: Optional[str] = None
    top_factors: List[Dict[str, Any]] = []
    investigation_status: Optional[str] = None
    investigation_id: Optional[str] = None


class PaginatedAccountsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[AccountSummarySchema]


class TransactionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_id: str
    sender_account_id: str
    receiver_account_id: str
    timestamp: datetime
    amount: float
    currency: str
    channel: str
    status: str
    is_synthetic: bool = True
    sender_risk_score: Optional[float] = None
    sender_risk_category: Optional[str] = None
    receiver_risk_score: Optional[float] = None
    receiver_risk_category: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class PaginatedTransactionsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[TransactionSchema]


class AlertSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alert_id: str
    account_id: str
    model_version: str
    risk_score: float
    risk_category: str
    priority: str
    status: str
    reason_summary: str
    triggered_factors_json: Optional[List[Dict[str, Any]]] = None
    assigned_to: Optional[str] = None
    decision_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AlertUpdateRequest(BaseModel):
    status: str = Field(..., description="open | in_review | escalated | resolved_suspicious | dismissed_false_positive")
    assigned_to: Optional[str] = None
    decision_notes: Optional[str] = None
    actor: str = "Senior Investigator"


class InvestigationNoteCreate(BaseModel):
    author: str = "Senior Investigator"
    note_type: str = "analyst_note"
    content: str = Field(..., min_length=1)


class EvidenceItemCreate(BaseModel):
    evidence_type: str = "transaction_chain"
    title: str
    description: str
    reference_id: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    added_by: str = "Senior Investigator"


class InvestigationCreateRequest(BaseModel):
    account_id: str
    title: Optional[str] = None
    priority: str = "high"
    assigned_to: str = "Sarah Chen (AML Lead)"
    initial_note: Optional[str] = None
    actor: str = "Sarah Chen (AML Lead)"


class InvestigationUpdateRequest(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    findings_summary: Optional[str] = None
    actor: str = "Sarah Chen (AML Lead)"


class SyntheticGenerationRequest(BaseModel):
    num_accounts: int = Field(default=20000, ge=100, le=100000)
    num_transactions: int = Field(default=200000, ge=500, le=1000000)
    random_seed: int = Field(default=42, ge=1)
    suspicious_rate: float = Field(default=0.06, ge=0.01, le=0.35)
    reset_existing: bool = True
    auto_train_and_score: bool = True
    actor: str = "System Administrator"


class ModelTrainRequest(BaseModel):
    dataset_id: Optional[str] = None
    random_seed: int = 42
    n_estimators: int = Field(default=160, ge=20, le=600)
    max_depth: int = Field(default=5, ge=2, le=12)
    learning_rate: float = Field(default=0.07, ge=0.01, le=0.5)
    activate_if_passed: bool = True
    score_all_accounts: bool = True
    actor: str = "ML Engineering Lead"


class WhatIfSimulationRequest(BaseModel):
    account_id: str
    feature_overrides: Dict[str, float]
    actor: str = "Investigator"


class GraphPathQueryRequest(BaseModel):
    source_account_id: str
    target_account_id: str
    max_hops: int = Field(default=4, ge=1, le=6)

