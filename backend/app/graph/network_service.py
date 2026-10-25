from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.models.entities import (
    Account,
    FeatureSnapshot,
    Investigation,
    ModelPrediction,
    Transaction,
)


def _load_account_metadata_map(
    db: Session,
    account_ids: Set[str],
) -> Dict[str, Dict[str, Any]]:
    if not account_ids:
        return {}
    id_list = list(account_ids)

    accounts = db.query(Account).filter(Account.account_id.in_(id_list)).all()
    preds = db.query(ModelPrediction).filter(ModelPrediction.account_id.in_(id_list)).all()
    snaps = db.query(FeatureSnapshot).filter(FeatureSnapshot.account_id.in_(id_list)).all()
    invs = db.query(Investigation).filter(Investigation.account_id.in_(id_list)).all()

    pred_map = {p.account_id: p for p in preds}
    snap_map = {s.account_id: s for s in snaps}
    inv_map = {inv.account_id: inv for inv in invs}

    meta: Dict[str, Dict[str, Any]] = {}
    for acc in accounts:
        p = pred_map.get(acc.account_id)
        s = snap_map.get(acc.account_id)
        inv = inv_map.get(acc.account_id)
        meta[acc.account_id] = {
            "account_id": acc.account_id,
            "account_type": acc.account_type,
            "customer_segment": acc.customer_segment,
            "status": acc.status,
            "synthetic_region": acc.synthetic_region,
            "synthetic_country_code": acc.synthetic_country_code,
            "created_at": acc.created_at.isoformat() if acc.created_at else None,
            "risk_score": round(float(p.normalized_risk_score), 2) if p else 0.0,
            "raw_probability": round(float(p.raw_probability), 4) if p else 0.0,
            "calibrated_probability": round(float(p.calibrated_probability), 4) if p else 0.0,
            "risk_category": p.risk_category if p else "Low",
            "explanation_summary": p.explanation_summary if p else None,
            "top_factors": (p.top_factors_json or []) if p else [],
            "incoming_tx_count": int(s.incoming_tx_count) if s else 0,
            "outgoing_tx_count": int(s.outgoing_tx_count) if s else 0,
            "incoming_volume": round(float(s.incoming_volume), 2) if s else 0.0,
            "outgoing_volume": round(float(s.outgoing_volume), 2) if s else 0.0,
            "unique_counterparties": int(s.unique_counterparties) if s else 0,
            "last_activity_at": s.last_activity_at.isoformat() if (s and s.last_activity_at) else None,
            "investigation_id": inv.investigation_id if inv else None,
            "investigation_status": inv.status if inv else None,
        }
    return meta


def get_account_ego_network(
    db: Session,
    center_account_id: str,
    hops: int = 1,
    direction: str = "all",
    min_amount: float = 0.0,
    min_risk_score: float = 0.0,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    max_nodes: int = 85,
) -> Dict[str, Any]:
    """
    Constructs a multi-hop directed transaction graph centered on `center_account_id`
    from actual database Transaction records, computing NetworkX connected components,
    shared counterparties, and suspicious flow paths.
    """
    center_acc = db.query(Account).filter(Account.account_id == center_account_id).first()
    if not center_acc:
        raise ValueError(f"Account '{center_account_id}' not found.")

    hops = max(1, min(int(hops), 3))
    discovered_nodes: Set[str] = {center_account_id}
    frontier: Set[str] = {center_account_id}
    node_hop_distance: Dict[str, int] = {center_account_id: 0}
    collected_txs: Dict[str, Transaction] = {}

    for current_hop in range(1, hops + 1):
        if not frontier or len(discovered_nodes) >= max_nodes:
            break

        frontier_list = list(frontier)
        q = db.query(Transaction)

        if direction == "incoming":
            q = q.filter(Transaction.receiver_account_id.in_(frontier_list))
        elif direction == "outgoing":
            q = q.filter(Transaction.sender_account_id.in_(frontier_list))
        else:
            q = q.filter(
                or_(
                    Transaction.sender_account_id.in_(frontier_list),
                    Transaction.receiver_account_id.in_(frontier_list),
                )
            )

        if min_amount > 0:
            q = q.filter(Transaction.amount >= min_amount)
        if start_date:
            q = q.filter(Transaction.timestamp >= start_date)
        if end_date:
            q = q.filter(Transaction.timestamp <= end_date)

        hop_txs = q.order_by(Transaction.amount.desc()).limit(450).all()

        next_frontier: Set[str] = set()
        for tx in hop_txs:
            s_id = tx.sender_account_id
            r_id = tx.receiver_account_id
            if len(discovered_nodes) < max_nodes or (s_id in discovered_nodes and r_id in discovered_nodes):
                collected_txs[tx.transaction_id] = tx
                for nid in (s_id, r_id):
                    if nid not in discovered_nodes and len(discovered_nodes) < max_nodes:
                        discovered_nodes.add(nid)
                        node_hop_distance[nid] = current_hop
                        next_frontier.add(nid)
        frontier = next_frontier

    meta_map = _load_account_metadata_map(db, discovered_nodes)

    # Filter nodes by min_risk_score if requested (always keeping center_account_id)
    if min_risk_score > 0:
        allowed_nodes = {
            nid
            for nid, m in meta_map.items()
            if nid == center_account_id or m.get("risk_score", 0.0) >= min_risk_score
        }
    else:
        allowed_nodes = set(meta_map.keys())

    # Aggregate directed edges with NetworkX
    G = nx.DiGraph()
    for nid in allowed_nodes:
        G.add_node(nid, **(meta_map.get(nid, {"account_id": nid})))

    edge_buckets: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for tx in collected_txs.values():
        u = tx.sender_account_id
        v = tx.receiver_account_id
        if u not in allowed_nodes or v not in allowed_nodes:
            continue
        key = (u, v)
        if key not in edge_buckets:
            edge_buckets[key] = {
                "edge_id": f"{u}->{v}",
                "source": u,
                "target": v,
                "transaction_count": 0,
                "total_amount": 0.0,
                "channels": set(),
                "transaction_ids": [],
                "first_timestamp": tx.timestamp,
                "last_timestamp": tx.timestamp,
            }
        b = edge_buckets[key]
        b["transaction_count"] += 1
        b["total_amount"] += float(tx.amount)
        b["channels"].add(tx.channel)
        if len(b["transaction_ids"]) < 25:
            b["transaction_ids"].append(tx.transaction_id)
        if tx.timestamp < b["first_timestamp"]:
            b["first_timestamp"] = tx.timestamp
        if tx.timestamp > b["last_timestamp"]:
            b["last_timestamp"] = tx.timestamp

    edges_out: List[Dict[str, Any]] = []
    for (u, v), b in edge_buckets.items():
        u_risk = meta_map.get(u, {}).get("risk_score", 0.0)
        v_risk = meta_map.get(v, {}).get("risk_score", 0.0)
        is_suspicious_edge = bool(
            (u_risk >= 65.0 and v_risk >= 50.0)
            or (b["total_amount"] >= 8500.0 and max(u_risk, v_risk) >= 65.0)
            or ((v, u) in edge_buckets)
        )
        G.add_edge(
            u,
            v,
            weight=round(b["total_amount"], 2),
            count=b["transaction_count"],
            is_suspicious=is_suspicious_edge,
        )
        edges_out.append(
            {
                "edge_id": b["edge_id"],
                "source": u,
                "target": v,
                "transaction_count": b["transaction_count"],
                "total_amount": round(b["total_amount"], 2),
                "channels": sorted(list(b["channels"])),
                "transaction_ids": b["transaction_ids"],
                "first_timestamp": b["first_timestamp"].isoformat(),
                "last_timestamp": b["last_timestamp"].isoformat(),
                "is_suspicious": is_suspicious_edge,
            }
        )

    # Connected components & clusters
    undir_G = G.to_undirected()
    clusters: List[Dict[str, Any]] = []
    node_cluster_map: Dict[str, int] = {}
    for comp_idx, comp_nodes in enumerate(nx.connected_components(undir_G)):
        comp_list = sorted(list(comp_nodes))
        for cn in comp_list:
            node_cluster_map[cn] = comp_idx + 1
        avg_risk = float(
            sum(meta_map.get(cn, {}).get("risk_score", 0.0) for cn in comp_list)
            / max(1, len(comp_list))
        )
        clusters.append(
            {
                "cluster_id": comp_idx + 1,
                "node_count": len(comp_list),
                "average_risk_score": round(avg_risk, 2),
                "sample_accounts": comp_list[:6],
            }
        )

    # Identify shared counterparties (intermediaries connected to >= 2 nodes in the ego network)
    shared_counterparties: List[Dict[str, Any]] = []
    for nid in G.nodes():
        if nid == center_account_id:
            continue
        neighbors = set(G.predecessors(nid)) | set(G.successors(nid))
        if len(neighbors) >= 2:
            shared_counterparties.append(
                {
                    "account_id": nid,
                    "connected_count": len(neighbors),
                    "connected_accounts": sorted(list(neighbors))[:6],
                    "risk_score": meta_map.get(nid, {}).get("risk_score", 0.0),
                    "risk_category": meta_map.get(nid, {}).get("risk_category", "Low"),
                }
            )
    shared_counterparties.sort(key=lambda x: (x["connected_count"], x["risk_score"]), reverse=True)

    # Identify suspicious paths / circular loops involving the center node
    suspicious_paths: List[Dict[str, Any]] = []
    # 1. Check short directed cycles passing through center_account_id
    for succ in G.successors(center_account_id):
        try:
            if nx.has_path(G, succ, center_account_id):
                cycle_path = [center_account_id] + nx.shortest_path(G, succ, center_account_id)
                if len(cycle_path) <= 6:
                    path_vol = sum(
                        G[cycle_path[i]][cycle_path[i + 1]]["weight"]
                        for i in range(len(cycle_path) - 1)
                    )
                    suspicious_paths.append(
                        {
                            "pattern_type": "Circular Transaction Loop",
                            "nodes": cycle_path,
                            "total_amount": round(float(path_vol), 2),
                            "explanation": (
                                f"Directed cycle of length {len(cycle_path) - 1} returning funds to {center_account_id}. "
                                "Investigative indicator of circular layering or round-tripping."
                            ),
                        }
                    )
        except Exception:
            pass

    # 2. Check rapid pass-through corridors (Predecessor -> Center -> Successor)
    for pred in list(G.predecessors(center_account_id))[:6]:
        for succ in list(G.successors(center_account_id))[:6]:
            if pred == succ:
                continue
            in_w = G[pred][center_account_id]["weight"]
            out_w = G[center_account_id][succ]["weight"]
            ratio = out_w / max(in_w, 1.0)
            if 0.70 <= ratio <= 1.25 and (in_w + out_w) >= 1500.0:
                suspicious_paths.append(
                    {
                        "pattern_type": "Pass-Through Funnel Corridor",
                        "nodes": [pred, center_account_id, succ],
                        "total_amount": round(float(in_w + out_w), 2),
                        "explanation": (
                            f"Inflow of ${in_w:,.2f} from {pred} followed by onward outflow of ${out_w:,.2f} to {succ} "
                            f"(value retention ratio {ratio:.2f})."
                        ),
                    }
                )
    suspicious_paths = suspicious_paths[:8]

    suspicious_node_set: Set[str] = set()
    for sp in suspicious_paths:
        suspicious_node_set.update(sp["nodes"])

    nodes_out: List[Dict[str, Any]] = []
    for nid in allowed_nodes:
        info = dict(meta_map.get(nid, {"account_id": nid}))
        info["is_center"] = nid == center_account_id
        info["hop_distance"] = node_hop_distance.get(nid, 1)
        info["cluster_id"] = node_cluster_map.get(nid, 1)
        info["in_suspicious_path"] = nid in suspicious_node_set
        info["subgraph_in_degree"] = G.in_degree(nid)
        info["subgraph_out_degree"] = G.out_degree(nid)
        nodes_out.append(info)

    nodes_out.sort(key=lambda x: (not x["is_center"], -x.get("risk_score", 0.0)))

    return {
        "center_account_id": center_account_id,
        "hops": hops,
        "direction": direction,
        "nodes": nodes_out,
        "edges": edges_out,
        "clusters": clusters,
        "shared_counterparties": shared_counterparties[:10],
        "suspicious_paths": suspicious_paths,
        "stats": {
            "node_count": len(nodes_out),
            "edge_count": len(edges_out),
            "total_subgraph_volume": round(sum(e["total_amount"] for e in edges_out), 2),
            "high_risk_nodes": sum(1 for n in nodes_out if n.get("risk_score", 0.0) >= 65.0),
            "suspicious_edges": sum(1 for e in edges_out if e["is_suspicious"]),
        },
        "disclaimer": (
            "Graph indicators highlight structural patterns (pass-through corridors, shared counterparties, cycles) "
            "from recorded transfers. They are investigative leads, not proof of wrongdoing."
        ),
    }


def trace_transaction_path(
    db: Session,
    source_account_id: str,
    target_account_id: str,
    max_hops: int = 4,
) -> Dict[str, Any]:
    """
    Traces directed or undirected transaction paths between `source_account_id` and `target_account_id`
    up to `max_hops`, returning exact underlying transactions, timestamps, and total flow amount.
    """
    max_hops = max(1, min(int(max_hops), 6))
    # Build bounded neighborhood around source and target
    frontier: Set[str] = {source_account_id, target_account_id}
    visited: Set[str] = set(frontier)
    collected_txs: Dict[str, Transaction] = {}

    for _ in range(max_hops):
        f_list = list(frontier)
        txs = (
            db.query(Transaction)
            .filter(
                or_(
                    Transaction.sender_account_id.in_(f_list),
                    Transaction.receiver_account_id.in_(f_list),
                )
            )
            .order_by(Transaction.amount.desc())
            .limit(800)
            .all()
        )
        next_f: Set[str] = set()
        for tx in txs:
            collected_txs[tx.transaction_id] = tx
            for nid in (tx.sender_account_id, tx.receiver_account_id):
                if nid not in visited and len(visited) < 400:
                    visited.add(nid)
                    next_f.add(nid)
        frontier = next_f
        if not frontier:
            break

    G_dir = nx.DiGraph()
    edge_tx_map: Dict[Tuple[str, str], List[Transaction]] = {}
    for tx in collected_txs.values():
        u, v = tx.sender_account_id, tx.receiver_account_id
        edge_tx_map.setdefault((u, v), []).append(tx)
        if G_dir.has_edge(u, v):
            G_dir[u][v]["weight"] += float(tx.amount)
            G_dir[u][v]["count"] += 1
        else:
            G_dir.add_edge(u, v, weight=float(tx.amount), count=1)

    path_nodes: Optional[List[str]] = None
    path_mode = "directed"

    if source_account_id in G_dir and target_account_id in G_dir:
        try:
            path_nodes = nx.shortest_path(G_dir, source=source_account_id, target=target_account_id)
        except nx.NetworkXNoPath:
            G_undir = G_dir.to_undirected()
            try:
                path_nodes = nx.shortest_path(G_undir, source=source_account_id, target=target_account_id)
                path_mode = "undirected_corridor"
            except nx.NetworkXNoPath:
                path_nodes = None

    if not path_nodes:
        return {
            "found": False,
            "source_account_id": source_account_id,
            "target_account_id": target_account_id,
            "path_mode": None,
            "nodes": [],
            "hops": [],
            "total_amount": 0.0,
            "total_transactions": 0,
            "time_span_hours": 0.0,
        }

    meta_map = _load_account_metadata_map(db, set(path_nodes))
    hops_detail: List[Dict[str, Any]] = []
    total_amt = 0.0
    total_tx_count = 0
    all_ts: List[datetime] = []

    for i in range(len(path_nodes) - 1):
        u = path_nodes[i]
        v = path_nodes[i + 1]
        txs_uv = edge_tx_map.get((u, v), []) or edge_tx_map.get((v, u), [])
        actual_sender = u if (u, v) in edge_tx_map else v
        actual_receiver = v if (u, v) in edge_tx_map else u
        hop_amt = sum(float(t.amount) for t in txs_uv)
        total_amt += hop_amt
        total_tx_count += len(txs_uv)
        for t in txs_uv:
            all_ts.append(t.timestamp)

        latest_tx = max(txs_uv, key=lambda x: x.timestamp) if txs_uv else None
        hops_detail.append(
            {
                "hop_index": i + 1,
                "sender_account_id": actual_sender,
                "receiver_account_id": actual_receiver,
                "transaction_count": len(txs_uv),
                "total_amount": round(hop_amt, 2),
                "latest_timestamp": latest_tx.timestamp.isoformat() if latest_tx else None,
                "sample_transaction_ids": [t.transaction_id for t in txs_uv[:8]],
                "channel": latest_tx.channel if latest_tx else "wire",
            }
        )

    time_span_hours = 0.0
    if len(all_ts) >= 2:
        time_span_hours = round((max(all_ts) - min(all_ts)).total_seconds() / 3600.0, 2)

    return {
        "found": True,
        "source_account_id": source_account_id,
        "target_account_id": target_account_id,
        "path_mode": path_mode,
        "nodes": [meta_map.get(n, {"account_id": n}) for n in path_nodes],
        "node_ids": path_nodes,
        "hops": hops_detail,
        "total_amount": round(total_amt, 2),
        "total_transactions": total_tx_count,
        "time_span_hours": time_span_hours,
    }

