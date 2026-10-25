from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
import numpy as np
import pandas as pd

FORBIDDEN_LEAKAGE_COLUMNS = {
    "account_id",
    "transaction_id",
    "is_suspicious_mule",
    "archetype_category",
    "scenario_group_id",
    "label_source",
    "label_provenance",
    "dataset_id",
    "is_synthetic",
}

FEATURE_DEFINITIONS: List[Dict[str, str]] = [
    {
        "name": "incoming_tx_count",
        "display_name": "Incoming Transaction Count",
        "dtype": "float64",
        "category": "velocity",
        "description": "Total number of historical incoming transfers received up to the analysis cutoff.",
        "limitations": "High for legitimate merchants and payment collectors as well as fan-in mules.",
    },
    {
        "name": "outgoing_tx_count",
        "display_name": "Outgoing Transaction Count",
        "dtype": "float64",
        "category": "velocity",
        "description": "Total number of historical outgoing transfers sent up to the analysis cutoff.",
        "limitations": "Payroll accounts and splitter mules both exhibit elevated outgoing counts.",
    },
    {
        "name": "incoming_volume",
        "display_name": "Incoming Volume (USD)",
        "dtype": "float64",
        "category": "volume",
        "description": "Aggregate monetary value of incoming transfers before the cutoff timestamp.",
        "limitations": "Must be contextualized against declared turnover and account segment.",
    },
    {
        "name": "outgoing_volume",
        "display_name": "Outgoing Volume (USD)",
        "dtype": "float64",
        "category": "volume",
        "description": "Aggregate monetary value of outgoing transfers before the cutoff timestamp.",
        "limitations": "High volume alone does not imply illicit activity.",
    },
    {
        "name": "avg_incoming_amount",
        "display_name": "Average Incoming Amount",
        "dtype": "float64",
        "category": "volume",
        "description": "Mean monetary value per incoming transfer.",
        "limitations": "Sensitive to single large legitimate deposits such as property or bonus payments.",
    },
    {
        "name": "avg_outgoing_amount",
        "display_name": "Average Outgoing Amount",
        "dtype": "float64",
        "category": "volume",
        "description": "Mean monetary value per outgoing transfer.",
        "limitations": "May appear moderate when large sums are split across many smaller transfers.",
    },
    {
        "name": "tx_amount_std",
        "display_name": "Transaction Amount Std Dev",
        "dtype": "float64",
        "category": "variability",
        "description": "Standard deviation of transaction amounts across all account activity.",
        "limitations": "Zero or low for accounts with very few transactions.",
    },
    {
        "name": "tx_amount_cv",
        "display_name": "Transaction Amount Variability (CV)",
        "dtype": "float64",
        "category": "variability",
        "description": "Coefficient of variation (std / mean) measuring uniformity vs dispersion of transfer sizes.",
        "limitations": "Fixed-amount structuring rings may show artificially low variability.",
    },
    {
        "name": "unique_counterparties",
        "display_name": "Distinct Counterparties",
        "dtype": "float64",
        "category": "network",
        "description": "Total distinct sender and receiver accounts interacting with this account.",
        "limitations": "Retail businesses naturally transact with many distinct customers.",
    },
    {
        "name": "in_out_count_ratio",
        "display_name": "Incoming-to-Outgoing Count Ratio",
        "dtype": "float64",
        "category": "passthrough",
        "description": "Ratio of incoming transaction count to outgoing transaction count.",
        "limitations": "High values occur in both funnel mules and merchant collection accounts.",
    },
    {
        "name": "out_in_volume_ratio",
        "display_name": "Outgoing-to-Incoming Value Ratio",
        "dtype": "float64",
        "category": "passthrough",
        "description": "Ratio of total outgoing volume to total incoming volume.",
        "limitations": "Values near 0.90-1.02 indicate near-complete pass-through when paired with short holding times.",
    },
    {
        "name": "passthrough_symmetry_score",
        "display_name": "Pass-Through Volume Symmetry",
        "dtype": "float64",
        "category": "passthrough",
        "description": "Closeness of incoming and outgoing volume to 1:1 parity (1 - |in - out| / max(in, out)).",
        "limitations": "Requires holding-time context to distinguish from zero-balance sweep accounts.",
    },
    {
        "name": "turnover_to_declared_ratio",
        "display_name": "Observed vs Declared Monthly Turnover",
        "dtype": "float64",
        "category": "baseline",
        "description": "Ratio of observed monthly transaction turnover to KYC declared monthly turnover.",
        "limitations": "Depends on accuracy of self-declared KYC onboarding figures.",
    },
    {
        "name": "burst_ratio_7d_vs_90d",
        "display_name": "7-Day Activity Burst Ratio",
        "dtype": "float64",
        "category": "temporal",
        "description": "Share of 90-day transaction volume concentrated in the most recent 7 days.",
        "limitations": "Can be elevated by legitimate seasonal or one-time personal events.",
    },
    {
        "name": "recent_vs_baseline_volume_ratio",
        "display_name": "Recent vs Historical Baseline Ratio",
        "dtype": "float64",
        "category": "baseline",
        "description": "Ratio of recent 14-day daily volume rate to prior historical daily volume rate.",
        "limitations": "Newly opened accounts have shorter historical baselines.",
    },
    {
        "name": "median_holding_time_hours",
        "display_name": "Approx. Holding Time (Hours)",
        "dtype": "float64",
        "category": "temporal",
        "description": "Estimated median elapsed hours between receiving funds and sending onward transfers.",
        "limitations": "Approximated from timestamp deltas between sequential inflows and outflows.",
    },
    {
        "name": "rapid_passthrough_ratio",
        "display_name": "Rapid Forwarding Ratio (<3h)",
        "dtype": "float64",
        "category": "temporal",
        "description": "Proportion of outgoing transfers executed within 3 hours of a preceding incoming transfer.",
        "limitations": "Active day-traders or instant wallet users may occasionally trigger rapid transfers.",
    },
    {
        "name": "account_age_days",
        "display_name": "Account Age (Days)",
        "dtype": "float64",
        "category": "profile",
        "description": "Age of the account in days at the analysis cutoff timestamp.",
        "limitations": "Compromised or dormant-takeover mule accounts may be several years old.",
    },
    {
        "name": "dormancy_gap_days",
        "display_name": "Max Inactivity Gap (Days)",
        "dtype": "float64",
        "category": "temporal",
        "description": "Longest period of inactivity before renewed transaction activity.",
        "limitations": "Seasonal accounts naturally have long inactivity gaps.",
    },
    {
        "name": "dormancy_burst_indicator",
        "display_name": "Dormancy-to-Burst Score",
        "dtype": "float64",
        "category": "temporal",
        "description": "Composite indicator of prolonged dormancy followed by high-velocity recent turnover.",
        "limitations": "Should be reviewed alongside account holder contact/device changes.",
    },
    {
        "name": "in_degree",
        "display_name": "Network In-Degree (Unique Senders)",
        "dtype": "float64",
        "category": "graph",
        "description": "Number of distinct accounts sending funds directly to this account.",
        "limitations": "Captures 1-hop incoming connectivity only.",
    },
    {
        "name": "out_degree",
        "display_name": "Network Out-Degree (Onward Destinations)",
        "dtype": "float64",
        "category": "graph",
        "description": "Number of distinct destination accounts receiving funds from this account.",
        "limitations": "Captures 1-hop outgoing connectivity only.",
    },
    {
        "name": "pagerank_score",
        "display_name": "Network PageRank Centrality (x1000)",
        "dtype": "float64",
        "category": "graph",
        "description": "Volume-weighted directed PageRank centrality scaled by 1,000.",
        "limitations": "Depends on the scope of transactions available in the monitored institution.",
    },
    {
        "name": "clustering_coefficient",
        "display_name": "Local Clustering Coefficient",
        "dtype": "float64",
        "category": "graph",
        "description": "Fraction of connected triangles among an account's immediate neighborhood.",
        "limitations": "Shared household circles and circular mule rings both increase local clustering.",
    },
    {
        "name": "cycle_participation_score",
        "display_name": "Circular Flow / Reciprocity Score",
        "dtype": "float64",
        "category": "graph",
        "description": "Indicator of participation in 2-hop bidirectional or short directed cycles (up to length 5).",
        "limitations": "Friends splitting bills back and forth can create 2-hop reciprocity.",
    },
    {
        "name": "high_risk_channel_ratio",
        "display_name": "High-Velocity Channel Share",
        "dtype": "float64",
        "category": "behavioral",
        "description": "Proportion of transfers using instant P2P, crypto ramps, or cross-border wires.",
        "limitations": "Modern digital banking users frequently prefer instant payment rails.",
    },
]

FEATURE_NAMES: List[str] = [f["name"] for f in FEATURE_DEFINITIONS]
FEATURE_DISPLAY_MAP: Dict[str, str] = {f["name"]: f["display_name"] for f in FEATURE_DEFINITIONS}
FEATURE_DESC_MAP: Dict[str, str] = {f["name"]: f["description"] for f in FEATURE_DEFINITIONS}


def compute_account_features(
    accounts_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    as_of_timestamp: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Computes the 26 behavioral, temporal, and graph features for each account using ONLY
    transactions up to `as_of_timestamp` (preventing temporal leakage) and strictly excluding
    any label or scenario generator columns.
    """
    if accounts_df.empty:
        return pd.DataFrame(columns=["account_id"] + FEATURE_NAMES)

    acc_df = accounts_df[["account_id", "created_at", "declared_monthly_turnover"]].copy()
    acc_df["created_at"] = pd.to_datetime(acc_df["created_at"])

    tx_df = transactions_df[
        [
            "transaction_id",
            "sender_account_id",
            "receiver_account_id",
            "timestamp",
            "amount",
            "channel",
        ]
    ].copy()
    tx_df["timestamp"] = pd.to_datetime(tx_df["timestamp"])

    if as_of_timestamp is None:
        if not tx_df.empty:
            as_of_timestamp = pd.to_datetime(tx_df["timestamp"].max()).to_pydatetime()
        else:
            as_of_timestamp = datetime.utcnow()
    else:
        as_of_timestamp = pd.to_datetime(as_of_timestamp).to_pydatetime()

    # Enforce strict temporal cutoff: exclude any future transactions after as_of_timestamp
    tx_df = tx_df[tx_df["timestamp"] <= as_of_timestamp].copy()

    # Base index on account_id
    feat_df = acc_df.set_index("account_id")
    feat_df["account_age_days"] = (
        (as_of_timestamp - feat_df["created_at"]).dt.total_seconds() / 86400.0
    ).clip(lower=1.0)

    if tx_df.empty:
        for col in FEATURE_NAMES:
            if col not in feat_df.columns:
                feat_df[col] = 0.0
        return feat_df.reset_index()[["account_id"] + FEATURE_NAMES]

    # 1. Incoming & Outgoing Aggregations
    in_grp = tx_df.groupby("receiver_account_id").agg(
        incoming_tx_count=("amount", "count"),
        incoming_volume=("amount", "sum"),
        avg_incoming_amount=("amount", "mean"),
        in_std=("amount", "std"),
        in_degree=("sender_account_id", "nunique"),
        first_in_ts=("timestamp", "min"),
        last_in_ts=("timestamp", "max"),
    )

    out_grp = tx_df.groupby("sender_account_id").agg(
        outgoing_tx_count=("amount", "count"),
        outgoing_volume=("amount", "sum"),
        avg_outgoing_amount=("amount", "mean"),
        out_std=("amount", "std"),
        out_degree=("receiver_account_id", "nunique"),
        first_out_ts=("timestamp", "min"),
        last_out_ts=("timestamp", "max"),
    )

    feat_df = feat_df.join(in_grp, how="left").join(out_grp, how="left")

    num_zero_cols = [
        "incoming_tx_count",
        "incoming_volume",
        "avg_incoming_amount",
        "in_std",
        "in_degree",
        "outgoing_tx_count",
        "outgoing_volume",
        "avg_outgoing_amount",
        "out_std",
        "out_degree",
    ]
    for c in num_zero_cols:
        feat_df[c] = feat_df[c].fillna(0.0)

    total_tx_count = feat_df["incoming_tx_count"] + feat_df["outgoing_tx_count"]
    total_volume = feat_df["incoming_volume"] + feat_df["outgoing_volume"]
    mean_amount = total_volume / np.maximum(total_tx_count, 1.0)

    feat_df["tx_amount_std"] = ((feat_df["in_std"] + feat_df["out_std"]) / 2.0).fillna(0.0)
    feat_df["tx_amount_cv"] = (feat_df["tx_amount_std"] / np.maximum(mean_amount, 1.0)).clip(0.0, 10.0)

    # Unique counterparties (union of senders and receivers)
    feat_df["unique_counterparties"] = feat_df["in_degree"] + feat_df["out_degree"]

    # Ratios
    feat_df["in_out_count_ratio"] = (
        feat_df["incoming_tx_count"] / np.maximum(feat_df["outgoing_tx_count"], 1.0)
    ).clip(0.0, 50.0)
    feat_df["out_in_volume_ratio"] = (
        feat_df["outgoing_volume"] / np.maximum(feat_df["incoming_volume"], 1.0)
    ).clip(0.0, 20.0)

    max_io = np.maximum(feat_df["incoming_volume"], feat_df["outgoing_volume"])
    has_both = (feat_df["incoming_tx_count"] >= 2) & (feat_df["outgoing_tx_count"] >= 2)
    feat_df["passthrough_symmetry_score"] = np.where(
        has_both & (max_io > 0),
        1.0 - (np.abs(feat_df["incoming_volume"] - feat_df["outgoing_volume"]) / max_io),
        0.0,
    ).clip(0.0, 1.0)

    # Monthly turnover vs declared
    monthly_observed = total_volume / 3.0
    feat_df["turnover_to_declared_ratio"] = (
        monthly_observed / np.maximum(feat_df["declared_monthly_turnover"], 100.0)
    ).clip(0.0, 100.0)

    # 2. Temporal Windows (Last 7d and Last 14d vs Baseline)
    cutoff_7d = as_of_timestamp - timedelta(days=7)
    cutoff_14d = as_of_timestamp - timedelta(days=14)

    tx_7d = tx_df[tx_df["timestamp"] >= cutoff_7d]
    vol_7d = (
        tx_7d.groupby("sender_account_id")["amount"]
        .sum()
        .add(tx_7d.groupby("receiver_account_id")["amount"].sum(), fill_value=0.0)
    )
    feat_df["vol_7d"] = vol_7d.reindex(feat_df.index).fillna(0.0)
    feat_df["burst_ratio_7d_vs_90d"] = (
        feat_df["vol_7d"] / np.maximum(total_volume, 1.0)
    ).clip(0.0, 1.0)

    tx_14d = tx_df[tx_df["timestamp"] >= cutoff_14d]
    vol_14d = (
        tx_14d.groupby("sender_account_id")["amount"]
        .sum()
        .add(tx_14d.groupby("receiver_account_id")["amount"].sum(), fill_value=0.0)
    )
    feat_df["vol_14d"] = vol_14d.reindex(feat_df.index).fillna(0.0)
    prior_vol = np.maximum(total_volume - feat_df["vol_14d"], 0.0)
    recent_daily = feat_df["vol_14d"] / 14.0
    prior_daily = prior_vol / 76.0
    feat_df["recent_vs_baseline_volume_ratio"] = (
        recent_daily / np.maximum(prior_daily, 10.0)
    ).clip(0.0, 100.0)

    # 3. Approximate Holding Time & Rapid Pass-Through (<3h)
    # Vectorized calculation using sorted events per account
    in_events = tx_df[["receiver_account_id", "timestamp"]].rename(
        columns={"receiver_account_id": "account_id", "timestamp": "in_ts"}
    )
    out_events = tx_df[["sender_account_id", "timestamp"]].rename(
        columns={"sender_account_id": "account_id", "timestamp": "out_ts"}
    )
    in_events = in_events.sort_values("in_ts")
    out_events = out_events.sort_values("out_ts")

    if not in_events.empty and not out_events.empty:
        merged_hold = pd.merge_asof(
            out_events,
            in_events,
            left_on="out_ts",
            right_on="in_ts",
            by="account_id",
            direction="backward",
        )
        merged_hold["hold_hours"] = (
            merged_hold["out_ts"] - merged_hold["in_ts"]
        ).dt.total_seconds() / 3600.0
        valid_holds = merged_hold.dropna(subset=["hold_hours"]).copy()
        valid_holds = valid_holds[valid_holds["hold_hours"] >= 0.0]
        valid_holds["is_rapid"] = (valid_holds["hold_hours"] <= 3.5).astype(np.float64)

        hold_stats = valid_holds.groupby("account_id").agg(
            median_hold=("hold_hours", "median"),
            rapid_ratio=("is_rapid", "mean"),
        )
        feat_df["median_holding_time_hours"] = (
            hold_stats["median_hold"].reindex(feat_df.index).fillna(72.0).clip(0.05, 720.0)
        )
        feat_df["rapid_passthrough_ratio"] = (
            hold_stats["rapid_ratio"].reindex(feat_df.index).fillna(0.0).clip(0.0, 1.0)
        )
    else:
        feat_df["median_holding_time_hours"] = 72.0
        feat_df["rapid_passthrough_ratio"] = 0.0

    # 4. Dormancy Gap & Dormancy-to-Burst Indicator
    first_tx_ts = feat_df[["first_in_ts", "first_out_ts"]].min(axis=1)
    last_tx_ts = feat_df[["last_in_ts", "last_out_ts"]].max(axis=1)
    feat_df["last_activity_at"] = last_tx_ts

    active_span_days = (
        (last_tx_ts - first_tx_ts).dt.total_seconds() / 86400.0
    ).fillna(0.0)
    window_90 = np.minimum(feat_df["account_age_days"], 90.0)
    feat_df["dormancy_gap_days"] = np.maximum(0.0, window_90 - active_span_days).clip(0.0, 90.0)
    feat_df["dormancy_burst_indicator"] = (
        (feat_df["dormancy_gap_days"] / 90.0)
        * feat_df["burst_ratio_7d_vs_90d"]
        * np.log1p(total_tx_count)
    ).clip(0.0, 25.0)

    # 5. High-Velocity Channel Share
    fast_channels = {"instant_p2p", "crypto_ramp", "wire", "swift"}
    tx_df["is_fast_ch"] = tx_df["channel"].isin(fast_channels).astype(float)
    ch_in = tx_df.groupby("receiver_account_id")["is_fast_ch"].mean()
    ch_out = tx_df.groupby("sender_account_id")["is_fast_ch"].mean()
    feat_df["high_risk_channel_ratio"] = (
        pd.concat([ch_in, ch_out], axis=1).mean(axis=1).reindex(feat_df.index).fillna(0.0)
    )

    # 6. NetworkX Graph Topology Features
    edge_agg = (
        tx_df.groupby(["sender_account_id", "receiver_account_id"], as_index=False)
        .agg(weight=("amount", "sum"), count=("amount", "count"))
    )
    G = nx.from_pandas_edgelist(
        edge_agg,
        source="sender_account_id",
        target="receiver_account_id",
        edge_attr=["weight", "count"],
        create_using=nx.DiGraph(),
    )

    try:
        pr = nx.pagerank(G, alpha=0.85, weight="weight", max_iter=50, tol=1e-4)
    except Exception:
        pr = {n: 1.0 / max(1, G.number_of_nodes()) for n in G.nodes()}

    feat_df["pagerank_score"] = (
        pd.Series(pr).reindex(feat_df.index).fillna(0.0) * 1000.0
    ).clip(0.0, 500.0)

    # Local clustering on undirected projection (computed for bounded-degree nodes)
    G_undir = G.to_undirected()
    cluster_candidates = [n for n, d in G_undir.degree() if 2 <= d <= 35]
    clustering_map = nx.clustering(G_undir, nodes=cluster_candidates)
    feat_df["clustering_coefficient"] = (
        pd.Series(clustering_map).reindex(feat_df.index).fillna(0.0).clip(0.0, 1.0)
    )

    # Cycle participation score: detect 2-hop reciprocity + short directed cycles (length 3-5) among high-activity subgraph
    cycle_scores: Dict[str, float] = {}
    edge_set = set(G.edges())
    for u, v in edge_set:
        if (v, u) in edge_set:
            cycle_scores[u] = cycle_scores.get(u, 0.0) + 0.4
            cycle_scores[v] = cycle_scores.get(v, 0.0) + 0.4

    # Check 3-5 hop cycles on nodes that have both in_degree >= 1 and out_degree >= 1 and rapid transfers
    candidate_nodes = [
        n
        for n in G.nodes()
        if G.in_degree(n) >= 1 and G.out_degree(n) >= 1 and G.degree(n) <= 40
    ]
    subG = G.subgraph(candidate_nodes)
    # Bounded BFS for short cycle detection (length <= 5)
    for node in subG.nodes():
        # Check if any successor can reach `node` within 4 hops in subG
        visited = {node}
        frontier = set(subG.successors(node))
        for hop in range(1, 5):
            if node in frontier:
                cycle_scores[node] = max(cycle_scores.get(node, 0.0), 1.0)
                break
            next_frontier = set()
            for curr in frontier:
                if curr not in visited:
                    visited.add(curr)
                    for nxt in subG.successors(curr):
                        next_frontier.add(nxt)
            frontier = next_frontier
            if not frontier:
                break

    feat_df["cycle_participation_score"] = (
        pd.Series(cycle_scores).reindex(feat_df.index).fillna(0.0).clip(0.0, 2.0)
    )

    # Ensure all 26 features exist, are finite float64, and contain zero leakage columns
    result_df = feat_df.reset_index()
    for col in FEATURE_NAMES:
        result_df[col] = (
            pd.to_numeric(result_df[col], errors="coerce")
            .replace([np.inf, -np.inf], 0.0)
            .fillna(0.0)
            .astype(np.float64)
        )

    keep_cols = ["account_id"] + FEATURE_NAMES + ["last_activity_at"]
    return result_df[keep_cols]
