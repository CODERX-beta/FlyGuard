export type RiskCategory = "Critical" | "High" | "Moderate" | "Low";

export interface ShapFactor {
  feature: string;
  display_name: string;
  feature_value: number;
  shap_value: number;
  direction: "increases_risk" | "decreases_risk";
  description: string;
}

export interface AccountSummary {
  account_id: string;
  account_type: string;
  customer_segment: string;
  created_at: string;
  status: string;
  synthetic_region?: string | null;
  synthetic_country_code?: string | null;
  kyc_tier: string;
  declared_monthly_turnover: number;
  primary_currency: string;
  is_synthetic: boolean;
  risk_score: number;
  raw_probability: number;
  calibrated_probability: number;
  risk_category: RiskCategory;
  alert_priority: string;
  incoming_tx_count: number;
  outgoing_tx_count: number;
  incoming_volume: number;
  outgoing_volume: number;
  unique_counterparties: number;
  last_activity_at?: string | null;
  explanation_summary?: string | null;
  top_factors: ShapFactor[];
  investigation_status?: string | null;
  investigation_id?: string | null;
}

export interface PaginatedAccounts {
  total: number;
  page: number;
  page_size: number;
  items: AccountSummary[];
}

export interface TransactionRecord {
  transaction_id: string;
  sender_account_id: string;
  receiver_account_id: string;
  timestamp: string;
  amount: number;
  currency: string;
  channel: string;
  status: string;
  is_synthetic: boolean;
  sender_risk_score?: number;
  sender_risk_category?: RiskCategory;
  receiver_risk_score?: number;
  receiver_risk_category?: RiskCategory;
}

export interface PaginatedTransactions {
  total: number;
  page: number;
  page_size: number;
  items: TransactionRecord[];
}

export interface GraphNodeData {
  account_id: string;
  account_type?: string;
  customer_segment?: string;
  status?: string;
  synthetic_region?: string;
  synthetic_country_code?: string;
  risk_score: number;
  raw_probability?: number;
  calibrated_probability?: number;
  risk_category: RiskCategory;
  explanation_summary?: string;
  top_factors?: ShapFactor[];
  incoming_tx_count: number;
  outgoing_tx_count: number;
  incoming_volume: number;
  outgoing_volume: number;
  unique_counterparties: number;
  last_activity_at?: string | null;
  investigation_id?: string | null;
  investigation_status?: string | null;
  is_center: boolean;
  hop_distance: number;
  cluster_id: number;
  in_suspicious_path: boolean;
  subgraph_in_degree: number;
  subgraph_out_degree: number;
}

export interface GraphEdgeData {
  edge_id: string;
  source: string;
  target: string;
  transaction_count: number;
  total_amount: number;
  channels: string[];
  transaction_ids: string[];
  first_timestamp: string;
  last_timestamp: string;
  is_suspicious: boolean;
}

export interface EgoNetworkResponse {
  center_account_id: string;
  hops: number;
  direction: string;
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  clusters: Array<{
    cluster_id: number;
    node_count: number;
    average_risk_score: number;
    sample_accounts: string[];
  }>;
  shared_counterparties: Array<{
    account_id: string;
    connected_count: number;
    connected_accounts: string[];
    risk_score: number;
    risk_category: RiskCategory;
  }>;
  suspicious_paths: Array<{
    pattern_type: string;
    nodes: string[];
    total_amount: number;
    explanation: string;
  }>;
  stats: {
    node_count: number;
    edge_count: number;
    total_subgraph_volume: number;
    high_risk_nodes: number;
    suspicious_edges: number;
  };
  disclaimer: string;
}

export interface TracePathResponse {
  found: boolean;
  source_account_id: string;
  target_account_id: string;
  path_mode: string | null;
  nodes: Array<Record<string, any>>;
  node_ids?: string[];
  hops: Array<{
    hop_index: number;
    sender_account_id: string;
    receiver_account_id: string;
    transaction_count: number;
    total_amount: number;
    latest_timestamp: string | null;
    sample_transaction_ids: string[];
    channel: string;
  }>;
  total_amount: number;
  total_transactions: number;
  time_span_hours: number;
}

