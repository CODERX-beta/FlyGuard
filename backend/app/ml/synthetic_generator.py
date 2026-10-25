import json
import math
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from backend.app.config import DATA_DIR
from backend.app.database import engine, reset_db, init_db
from backend.app.models.entities import (
    Account,
    Transaction,
    SyntheticLabel,
    DatasetTrainingMetadata,
    utcnow,
)
from backend.app.security.audit import record_audit_event

SYNTHETIC_REGIONS = [
    {"region": "US-East (New York)", "country": "US", "lat": 40.7128, "lng": -74.0060},
    {"region": "US-West (San Francisco)", "country": "US", "lat": 37.7749, "lng": -122.4194},
    {"region": "UK-London", "country": "GB", "lat": 51.5074, "lng": -0.1278},
    {"region": "EU-Frankfurt", "country": "DE", "lat": 50.1109, "lng": 8.6821},
    {"region": "SG-Central", "country": "SG", "lat": 1.3521, "lng": 103.8198},
    {"region": "AE-Dubai", "country": "AE", "lat": 25.2048, "lng": 55.2708},
    {"region": "IN-West (Mumbai)", "country": "IN", "lat": 19.0760, "lng": 72.8777},
    {"region": "JP-Tokyo", "country": "JP", "lat": 35.6762, "lng": 139.6503},
    {"region": "BR-SaoPaulo", "country": "BR", "lat": -23.5505, "lng": -46.6333},
    {"region": "NG-Lagos", "country": "NG", "lat": 6.5244, "lng": 3.3792},
    {"region": "AU-Sydney", "country": "AU", "lat": -33.8688, "lng": 151.2093},
    {"region": "CH-Zurich", "country": "CH", "lat": 47.3769, "lng": 8.5417},
]

CHANNELS = [
    "instant_p2p",
    "wire",
    "ach",
    "swift",
    "mobile_wallet",
    "card_transfer",
    "crypto_ramp",
]


def generate_synthetic_dataset(
    num_accounts: int = 20000,
    num_transactions: int = 200000,
    random_seed: int = 42,
    suspicious_rate: float = 0.06,
    dataset_id: Optional[str] = None,
    reference_end_date: Optional[datetime] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> Dict[str, Any]:
    """
    Generates a reproducible, leakage-free synthetic financial dataset with:
      1. Ordinary account behaviors (personal, salary/bills, low-frequency, temporary spikes)
      2. Difficult negative examples (SMBs, payment collectors, shared households, remittances)
      3. Suspicious money-mule patterns (rapid pass-through, fan-in funnels, fan-out splitters,
         circular rings, dormant-to-burst accounts, and layered multi-hop chains)

    Account IDs and Transaction IDs are randomized/time-ordered so identifiers never leak scenario labels.
    """
    rng = np.random.default_rng(random_seed)
    if dataset_id is None:
        dataset_id = f"syn-seed{random_seed}-{num_accounts // 1000}k"

    if reference_end_date is None:
        reference_end_date = datetime(2025, 4, 15, 18, 0, 0)
    window_start = reference_end_date - timedelta(days=90)

    if progress_callback:
        progress_callback(5.0, "Allocating synthetic account archetypes and shuffled identifiers")

    # Shuffle account IDs so ID order carries zero information about archetype/label
    raw_ids = [f"AC-{100000 + i}" for i in range(num_accounts)]
    shuffled_indices = rng.permutation(num_accounts)
    account_ids = [raw_ids[idx] for idx in shuffled_indices]

    num_mules = max(20, int(round(num_accounts * suspicious_rate)))
    num_hard_neg = max(30, int(round(num_accounts * 0.15)))
    num_ordinary = num_accounts - num_mules - num_hard_neg

    # Assign archetypes
    ordinary_types = rng.choice(
        [
            "ordinary_personal",
            "ordinary_salary_bills",
            "ordinary_low_frequency",
            "ordinary_temp_spike",
        ],
        size=num_ordinary,
        p=[0.42, 0.30, 0.18, 0.10],
    )
    hard_neg_types = rng.choice(
        [
            "hard_negative_smb",
            "hard_negative_collector",
            "hard_negative_household",
            "hard_negative_remittance",
        ],
        size=num_hard_neg,
        p=[0.35, 0.25, 0.20, 0.20],
    )
    mule_types = rng.choice(
        [
            "mule_rapid_passthrough",
            "mule_fan_in_funnel",
            "mule_fan_out_splitter",
            "mule_circular_ring",
            "mule_dormant_burst",
            "mule_layered_chain",
        ],
        size=num_mules,
        p=[0.24, 0.18, 0.18, 0.14, 0.14, 0.12],
    )

    all_archetypes = np.concatenate([ordinary_types, hard_neg_types, mule_types])
    all_labels = np.concatenate(
        [
            np.zeros(num_ordinary + num_hard_neg, dtype=np.int32),
            np.ones(num_mules, dtype=np.int32),
        ]
    )

    # Shuffle the archetype + label assignment again across account_ids
    perm = rng.permutation(num_accounts)
    all_archetypes = all_archetypes[perm]
    all_labels = all_labels[perm]

    accounts_records: List[Dict[str, Any]] = []
    labels_records: List[Dict[str, Any]] = []

    region_weights = [0.22, 0.12, 0.13, 0.09, 0.09, 0.08, 0.08, 0.05, 0.04, 0.04, 0.03, 0.03]

    for i in range(num_accounts):
        acc_id = account_ids[i]
        arch = str(all_archetypes[i])
        is_mule = int(all_labels[i])

        reg_info = SYNTHETIC_REGIONS[rng.choice(len(SYNTHETIC_REGIONS), p=region_weights)]
        # Add slight jitter to synthetic coordinates (clearly marked synthetic)
        lat_jitter = float(rng.normal(0, 0.35))
        lng_jitter = float(rng.normal(0, 0.35))

        # Account age distribution: overlapping across classes, though mules have slightly more younger accounts
        if arch in ("mule_dormant_burst", "ordinary_salary_bills", "hard_negative_smb"):
            age_days = int(rng.integers(180, 1400))
        elif is_mule:
            age_days = int(rng.choice([rng.integers(14, 150), rng.integers(150, 900)], p=[0.62, 0.38]))
        else:
            age_days = int(rng.choice([rng.integers(20, 150), rng.integers(150, 1500)], p=[0.22, 0.78]))

        created_at = reference_end_date - timedelta(days=age_days, hours=int(rng.integers(0, 23)))

        if arch == "hard_negative_smb":
            acc_type = rng.choice(["small_business", "individual"], p=[0.75, 0.25])
            segment = "commercial" if acc_type == "small_business" else "retail"
            declared_turnover = float(np.round(rng.uniform(18000, 95000), 2))
            kyc_tier = rng.choice(["tier_2", "tier_3"], p=[0.4, 0.6])
        elif arch == "hard_negative_collector":
            acc_type = rng.choice(["payment_collection", "small_business", "individual"], p=[0.5, 0.3, 0.2])
            segment = "merchant"
            declared_turnover = float(np.round(rng.uniform(25000, 120000), 2))
            kyc_tier = rng.choice(["tier_2", "tier_3"], p=[0.5, 0.5])
        elif arch == "hard_negative_remittance":
            acc_type = rng.choice(["remittance", "individual"], p=[0.45, 0.55])
            segment = "retail"
            declared_turnover = float(np.round(rng.uniform(6000, 30000), 2))
            kyc_tier = rng.choice(["tier_1", "tier_2"], p=[0.35, 0.65])
        else:
            acc_type = rng.choice(
                ["individual", "small_business", "household"],
                p=[0.82, 0.10, 0.08],
            )
            segment = "retail" if acc_type != "small_business" else "commercial"
            declared_turnover = float(np.round(rng.lognormal(mean=8.2, sigma=0.65), 2))
            kyc_tier = rng.choice(["tier_1", "tier_2", "tier_3"], p=[0.30, 0.55, 0.15])

        accounts_records.append(
            {
                "account_id": acc_id,
                "account_type": str(acc_type),
                "customer_segment": segment,
                "created_at": created_at,
                "status": "active",
                "synthetic_region": reg_info["region"],
                "synthetic_country_code": reg_info["country"],
                "synthetic_lat": round(reg_info["lat"] + lat_jitter, 4),
                "synthetic_lng": round(reg_info["lng"] + lng_jitter, 4),
                "kyc_tier": str(kyc_tier),
                "declared_monthly_turnover": declared_turnover,
                "primary_currency": "USD",
                "is_synthetic": True,
                "dataset_id": dataset_id,
                "metadata_json": {
                    "synthetic_notice": "SIMULATED_SYNTHETIC_RECORD",
                    "onboarding_channel": str(rng.choice(["mobile_app", "web_portal", "branch"])),
                },
            }
        )

        labels_records.append(
            {
                "account_id": acc_id,
                "is_suspicious_mule": is_mule,
                "archetype_category": arch,
                "scenario_group_id": f"grp-{acc_id}",
                "label_source": "synthetic_generator",
                "label_provenance": {
                    "generator_seed": random_seed,
                    "archetype": arch,
                    "note": "Synthetic ground-truth label isolated from feature pipeline.",
                },
                "dataset_id": dataset_id,
                "created_at": reference_end_date,
            }
        )

    if progress_callback:
        progress_callback(20.0, "Constructing suspicious mule networks, rings, funnels, and layered chains")

    # Organize indices by archetype for structured transaction generation
    arch_to_ids: Dict[str, List[str]] = {}
    label_idx_by_acc: Dict[str, int] = {}
    for idx, rec in enumerate(labels_records):
        arch = rec["archetype_category"]
        arch_to_ids.setdefault(arch, []).append(rec["account_id"])
        label_idx_by_acc[rec["account_id"]] = idx

    ordinary_pool = (
        arch_to_ids.get("ordinary_personal", [])
        + arch_to_ids.get("ordinary_salary_bills", [])
        + arch_to_ids.get("ordinary_low_frequency", [])
        + arch_to_ids.get("ordinary_temp_spike", [])
    )
    if not ordinary_pool:
        ordinary_pool = account_ids

    tx_list: List[Tuple[str, str, datetime, float, str, str]] = []
    # Tuple format: (sender_id, receiver_id, timestamp, amount, channel, status)

    # 1. Generate Mule Pattern Transactions (with realistic behavioral variance & noise)
    # 1A. Rapid Pass-Through Mules: Receive funds and forward 75-99% within 15 mins to 36 hours (some subtle mules hold longer)
    for mule_id in arch_to_ids.get("mule_rapid_passthrough", []):
        is_subtle = rng.random() < 0.25
        n_cycles = int(rng.integers(3, 8)) if is_subtle else int(rng.integers(5, 14))
        for _ in range(n_cycles):
            sender = ordinary_pool[int(rng.integers(0, len(ordinary_pool)))]
            receiver = ordinary_pool[int(rng.integers(0, len(ordinary_pool)))]
            if sender == mule_id or receiver == mule_id or sender == receiver:
                continue
            in_time = window_start + timedelta(
                seconds=int(rng.integers(0, int((reference_end_date - window_start).total_seconds() - 86400)))
            )
            amt = float(np.round(rng.uniform(450.0, 6800.0), 2))
            ch_in = str(rng.choice(["instant_p2p", "wire", "ach", "mobile_wallet"], p=[0.40, 0.25, 0.20, 0.15]))
            tx_list.append((sender, mule_id, in_time, amt, ch_in, "completed"))

            hold_mins = int(rng.integers(180, 2400)) if is_subtle else int(rng.integers(15, 240))
            out_time = in_time + timedelta(minutes=hold_mins)
            out_amt = float(np.round(amt * rng.uniform(0.78, 0.99), 2))
            ch_out = str(rng.choice(["instant_p2p", "crypto_ramp", "wire", "ach"], p=[0.35, 0.25, 0.20, 0.20]))
            tx_list.append((mule_id, receiver, out_time, out_amt, ch_out, "completed"))

    # 1B. Fan-In Funnel Mules: 4-14 senders funnel funds in, followed by 1-3 exits
    for mule_id in arch_to_ids.get("mule_fan_in_funnel", []):
        is_subtle = rng.random() < 0.25
        n_bursts = 1 if is_subtle else int(rng.integers(2, 4))
        for _ in range(n_bursts):
            burst_start = window_start + timedelta(days=int(rng.integers(5, 82)), hours=int(rng.integers(0, 20)))
            n_senders = int(rng.integers(3, 7)) if is_subtle else int(rng.integers(6, 13))
            total_in = 0.0
            for _s_idx in range(n_senders):
                sender = ordinary_pool[int(rng.integers(0, len(ordinary_pool)))]
                if sender == mule_id:
                    continue
                tx_t = burst_start + timedelta(minutes=int(rng.integers(10, 720)))
                amt = float(np.round(rng.uniform(350.0, 2800.0), 2))
                total_in += amt
                ch_in = str(rng.choice(["instant_p2p", "ach", "mobile_wallet"], p=[0.5, 0.3, 0.2]))
                tx_list.append((sender, mule_id, tx_t, amt, ch_in, "completed"))
            if total_in > 0:
                out_dest = ordinary_pool[int(rng.integers(0, len(ordinary_pool)))]
                out_t = burst_start + timedelta(hours=int(rng.integers(3, 36)))
                tx_list.append((mule_id, out_dest, out_t, round(total_in * float(rng.uniform(0.80, 0.98)), 2), "wire", "completed"))

    # 1C. Fan-Out Splitter Mules (Structuring): Receive 1-3 large deposits, split into 4-10 outbound transfers
    for mule_id in arch_to_ids.get("mule_fan_out_splitter", []):
        is_subtle = rng.random() < 0.22
        n_events = 1 if is_subtle else int(rng.integers(2, 4))
        for _ in range(n_events):
            ev_time = window_start + timedelta(days=int(rng.integers(3, 84)), hours=int(rng.integers(0, 18)))
            funder = ordinary_pool[int(rng.integers(0, len(ordinary_pool)))]
            in_amt = float(np.round(rng.uniform(4500.0, 22000.0), 2))
            tx_list.append((funder, mule_id, ev_time, in_amt, "wire", "completed"))

            n_splits = int(rng.integers(3, 6)) if is_subtle else int(rng.integers(5, 10))
            split_total = in_amt * float(rng.uniform(0.82, 0.98))
            weights = rng.dirichlet(np.ones(n_splits))
            for w in weights:
                dest = ordinary_pool[int(rng.integers(0, len(ordinary_pool)))]
                if dest == mule_id:
                    continue
                out_t = ev_time + timedelta(minutes=int(rng.integers(20, 600)))
                ch_o = str(rng.choice(["instant_p2p", "ach", "wire"], p=[0.55, 0.25, 0.20]))
                tx_list.append((mule_id, dest, out_t, max(50.0, round(float(split_total * w), 2)), ch_o, "completed"))

    # 1D. Circular Rings: Group into rings of 4-5 accounts and pass funds around the loop
    ring_mules = arch_to_ids.get("mule_circular_ring", [])
    ring_size = 5
    for r_start in range(0, len(ring_mules), ring_size):
        ring = ring_mules[r_start : r_start + ring_size]
        if len(ring) < 3:
            continue
        grp_id = f"grp-ring-{r_start // ring_size}"
        for acc_m in ring:
            labels_records[label_idx_by_acc[acc_m]]["scenario_group_id"] = grp_id

        n_rounds = int(rng.integers(2, 5))
        for _ in range(n_rounds):
            t_cursor = window_start + timedelta(days=int(rng.integers(4, 84)), hours=int(rng.integers(0, 12)))
            amt_cursor = float(np.round(rng.uniform(1400.0, 7200.0), 2))
            for hop in range(len(ring)):
                u = ring[hop]
                v = ring[(hop + 1) % len(ring)]
                t_cursor = t_cursor + timedelta(minutes=int(rng.integers(20, 240)))
                amt_cursor = max(100.0, round(amt_cursor * float(rng.uniform(0.90, 0.99)), 2))
                tx_list.append((u, v, t_cursor, amt_cursor, "instant_p2p", "completed"))

    # 1E. Dormant-to-Burst Mules: Silent for 60-75 days, then sudden burst of incoming & outgoing transfers
    for mule_id in arch_to_ids.get("mule_dormant_burst", []):
        is_subtle = rng.random() < 0.28
        burst_day = int(rng.integers(65, 86))
        burst_base = window_start + timedelta(days=burst_day)
        n_tx = int(rng.integers(3, 7)) if is_subtle else int(rng.integers(7, 16))
        for _ in range(n_tx):
            sender = ordinary_pool[int(rng.integers(0, len(ordinary_pool)))]
            receiver = ordinary_pool[int(rng.integers(0, len(ordinary_pool)))]
            t_in = burst_base + timedelta(minutes=int(rng.integers(0, 4320)))
            amt = float(np.round(rng.uniform(900.0, 6200.0), 2))
            tx_list.append((sender, mule_id, t_in, amt, "instant_p2p", "completed"))
            t_out = t_in + timedelta(minutes=int(rng.integers(25, 480)))
            ch_o = str(rng.choice(["crypto_ramp", "instant_p2p", "wire"], p=[0.45, 0.35, 0.20]))
            tx_list.append((mule_id, receiver, t_out, round(amt * float(rng.uniform(0.84, 0.98)), 2), ch_o, "completed"))

    # 1F. Layered Chains: Chains of 4 mule accounts (M1 -> M2 -> M3 -> M4) moving funds across hops
    chain_mules = arch_to_ids.get("mule_layered_chain", [])
    chain_len = 4
    for c_start in range(0, len(chain_mules), chain_len):
        chain = chain_mules[c_start : c_start + chain_len]
        if len(chain) < 3:
            continue
        grp_id = f"grp-chain-{c_start // chain_len}"
        for acc_m in chain:
            labels_records[label_idx_by_acc[acc_m]]["scenario_group_id"] = grp_id

        n_waves = int(rng.integers(2, 6))
        for _ in range(n_waves):
            t_cursor = window_start + timedelta(days=int(rng.integers(2, 85)), hours=int(rng.integers(0, 18)))
            amt = float(np.round(rng.uniform(1800.0, 9500.0), 2))
            ext_source = ordinary_pool[int(rng.integers(0, len(ordinary_pool)))]
            ext_sink = ordinary_pool[int(rng.integers(0, len(ordinary_pool)))]
            tx_list.append((ext_source, chain[0], t_cursor, amt, "wire", "completed"))
            for idx_hop in range(len(chain) - 1):
                t_cursor = t_cursor + timedelta(minutes=int(rng.integers(20, 240)))
                amt = round(amt * float(rng.uniform(0.90, 0.99)), 2)
                tx_list.append((chain[idx_hop], chain[idx_hop + 1], t_cursor, amt, "instant_p2p", "completed"))
            t_cursor = t_cursor + timedelta(minutes=int(rng.integers(30, 300)))
            tx_list.append((chain[-1], ext_sink, t_cursor, round(amt * 0.94, 2), "swift", "completed"))

    if progress_callback:
        progress_callback(45.0, "Generating difficult negative behaviors (SMBs, collectors, households, remittances)")

    # 2. Difficult Negative Examples (Legitimate accounts that closely resemble suspicious velocity/fan-in/passthrough)
    # 2A. Small Businesses: High volume, many counterparties; ~15% have rapid supplier payouts that mimic pass-through
    for smb_id in arch_to_ids.get("hard_negative_smb", []):
        mimic_fast = rng.random() < 0.14
        n_in = int(rng.integers(10, 24))
        for _ in range(n_in):
            cust = ordinary_pool[int(rng.integers(0, len(ordinary_pool)))]
            t_in = window_start + timedelta(days=int(rng.integers(0, 88)), hours=int(rng.integers(8, 20)))
            amt = float(np.round(rng.uniform(180.0, 2600.0), 2))
            ch = "instant_p2p" if mimic_fast else str(rng.choice(["card_transfer", "ach", "instant_p2p"], p=[0.45, 0.35, 0.20]))
            tx_list.append((cust, smb_id, t_in, amt, ch, "completed"))
            if mimic_fast and rng.random() < 0.65:
                vendor = ordinary_pool[int(rng.integers(0, len(ordinary_pool)))]
                t_out = t_in + timedelta(minutes=int(rng.integers(35, 220)))
                tx_list.append((smb_id, vendor, t_out, round(amt * float(rng.uniform(0.85, 0.97)), 2), "wire", "completed"))
        if not mimic_fast:
            n_out = int(rng.integers(4, 10))
            for _ in range(n_out):
                vendor = ordinary_pool[int(rng.integers(0, len(ordinary_pool)))]
                t_out = window_start + timedelta(days=int(rng.integers(5, 89)), hours=int(rng.integers(9, 17)))
                amt = float(np.round(rng.uniform(1100.0, 5200.0), 2))
                tx_list.append((smb_id, vendor, t_out, amt, "ach", "completed"))

    # 2B. Payment Collectors: High fan-in, batch settlement; ~12% settle same-day via wire/instant rails
    for col_id in arch_to_ids.get("hard_negative_collector", []):
        same_day_settle = rng.random() < 0.12
        settlement_partner = ordinary_pool[int(rng.integers(0, len(ordinary_pool)))]
        n_in = int(rng.integers(12, 24))
        for _ in range(n_in):
            payer = ordinary_pool[int(rng.integers(0, len(ordinary_pool)))]
            t_in = window_start + timedelta(days=int(rng.integers(0, 88)), hours=int(rng.integers(7, 21)))
            amt = float(np.round(rng.uniform(120.0, 1400.0), 2))
            tx_list.append((payer, col_id, t_in, amt, "instant_p2p" if same_day_settle else "mobile_wallet", "completed"))
            if same_day_settle and rng.random() < 0.5:
                tx_list.append((col_id, settlement_partner, t_in + timedelta(minutes=int(rng.integers(40, 180))), round(amt * 0.95, 2), "wire", "completed"))
        for wk in range(1, 7):
            t_settle = window_start + timedelta(days=wk * 12, hours=16)
            tx_list.append((col_id, settlement_partner, t_settle, float(np.round(rng.uniform(900.0, 3800.0), 2)), "ach", "completed"))

    # 2C. Shared Households & Remittances (some remittance corridors forward funds rapidly cross-border)
    for hh_id in arch_to_ids.get("hard_negative_household", []) + arch_to_ids.get("hard_negative_remittance", []):
        fast_remit = rng.random() < 0.15
        trusted_circle = [ordinary_pool[int(rng.integers(0, len(ordinary_pool)))] for _ in range(4)]
        n_tx = int(rng.integers(8, 18))
        for _ in range(n_tx):
            partner = trusted_circle[int(rng.integers(0, len(trusted_circle)))]
            if partner == hh_id:
                continue
            t_tx = window_start + timedelta(days=int(rng.integers(0, 88)), hours=int(rng.integers(8, 22)))
            amt = float(np.round(rng.uniform(180.0, 2400.0), 2))
            if fast_remit:
                tx_list.append((partner, hh_id, t_tx, amt, "instant_p2p", "completed"))
                dest = trusted_circle[int(rng.integers(0, len(trusted_circle)))]
                if dest != hh_id:
                    tx_list.append((hh_id, dest, t_tx + timedelta(minutes=int(rng.integers(30, 190))), round(amt * 0.94, 2), "swift", "completed"))
            elif rng.random() < 0.55:
                tx_list.append((partner, hh_id, t_tx, amt, "ach", "completed"))
            else:
                tx_list.append((hh_id, partner, t_tx, amt, "instant_p2p", "completed"))

    if progress_callback:
        progress_callback(65.0, "Vectorizing ordinary baseline transactions to reach target volume")

    # 3. Fill remaining transactions with vectorized ordinary account activity
    remaining_tx = max(100, num_transactions - len(tx_list))
    non_mule_ids = np.array(
        [rec["account_id"] for rec in labels_records if rec["is_suspicious_mule"] == 0]
    )
    if len(non_mule_ids) < 2:
        non_mule_ids = np.array(account_ids)

    sender_idx = rng.integers(0, len(non_mule_ids), size=remaining_tx)
    receiver_idx = (sender_idx + rng.integers(1, len(non_mule_ids), size=remaining_tx)) % len(non_mule_ids)

    senders_arr = non_mule_ids[sender_idx]
    receivers_arr = non_mule_ids[receiver_idx]

    total_window_secs = int((reference_end_date - window_start).total_seconds())
    offset_secs = rng.integers(0, total_window_secs, size=remaining_tx)
    amounts_arr = np.round(rng.lognormal(mean=5.4, sigma=1.05, size=remaining_tx), 2)
    amounts_arr = np.clip(amounts_arr, 12.0, 18500.0)
    channels_arr = rng.choice(
        ["ach", "instant_p2p", "card_transfer", "mobile_wallet", "wire"],
        size=remaining_tx,
        p=[0.32, 0.28, 0.20, 0.12, 0.08],
    )

    for s_id, r_id, sec, amt, ch in zip(
        senders_arr, receivers_arr, offset_secs, amounts_arr, channels_arr
    ):
        tx_list.append(
            (
                str(s_id),
                str(r_id),
                window_start + timedelta(seconds=int(sec)),
                float(amt),
                str(ch),
                "completed",
            )
        )

    # Trim or keep exact requested count and sort chronologically so TX IDs are strictly chronological
    if len(tx_list) > num_transactions:
        # Keep all structured pattern transactions and sample ordinary tail if needed
        tx_list = tx_list[:num_transactions]

    tx_list.sort(key=lambda x: x[2])

    if progress_callback:
        progress_callback(80.0, "Finalizing chronological transaction records and persisting to database")

    transactions_records: List[Dict[str, Any]] = []
    for idx, (s_id, r_id, ts, amt, ch, st) in enumerate(tx_list):
        transactions_records.append(
            {
                "transaction_id": f"TX-{1000000 + idx}",
                "sender_account_id": s_id,
                "receiver_account_id": r_id,
                "timestamp": ts,
                "amount": amt,
                "currency": "USD",
                "channel": ch,
                "status": st,
                "is_synthetic": True,
                "dataset_id": dataset_id,
                "metadata_json": {"synthetic": True},
            }
        )

    # Save CSV snapshots in data/generated for reproducibility & external inspection
    gen_dir = DATA_DIR / "generated"
    gen_dir.mkdir(parents=True, exist_ok=True)

    accounts_df = pd.DataFrame(accounts_records)
    transactions_df = pd.DataFrame(transactions_records)
    labels_df = pd.DataFrame(labels_records)

    return {
        "dataset_id": dataset_id,
        "random_seed": random_seed,
        "reference_end_date": reference_end_date,
        "accounts_df": accounts_df,
        "transactions_df": transactions_df,
        "labels_df": labels_df,
        "summary": {
            "dataset_id": dataset_id,
            "random_seed": random_seed,
            "total_accounts": len(accounts_df),
            "total_transactions": len(transactions_df),
            "suspicious_mule_accounts": int(labels_df["is_suspicious_mule"].sum()),
            "legitimate_accounts": int((labels_df["is_suspicious_mule"] == 0).sum()),
            "suspicious_rate": round(float(labels_df["is_suspicious_mule"].mean()), 4),
            "archetype_breakdown": labels_df["archetype_category"].value_counts().to_dict(),
        },
    }


def validate_dataset_frames(
    accounts_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    labels_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    Validates schema, referential integrity, positive transaction amounts, and anti-leakage constraints.
    """
    errors: List[str] = []
    warnings: List[str] = []

    required_acc_cols = {"account_id", "account_type", "created_at", "status"}
    missing_acc = required_acc_cols - set(accounts_df.columns)
    if missing_acc:
        errors.append(f"Accounts missing required columns: {sorted(missing_acc)}")

    required_tx_cols = {
        "transaction_id",
        "sender_account_id",
        "receiver_account_id",
        "timestamp",
        "amount",
        "currency",
        "channel",
        "status",
    }
    missing_tx = required_tx_cols - set(transactions_df.columns)
    if missing_tx:
        errors.append(f"Transactions missing required columns: {sorted(missing_tx)}")

    if not errors:
        if accounts_df["account_id"].duplicated().any():
            errors.append("Duplicate account_id values found in accounts dataset.")
        if transactions_df["transaction_id"].duplicated().any():
            errors.append("Duplicate transaction_id values found in transactions dataset.")
        if (transactions_df["amount"] <= 0).any():
            errors.append("Transactions contain non-positive amounts.")

        acc_set = set(accounts_df["account_id"])
        orphan_senders = set(transactions_df["sender_account_id"]) - acc_set
        orphan_receivers = set(transactions_df["receiver_account_id"]) - acc_set
        if orphan_senders or orphan_receivers:
            errors.append(
                f"Referential integrity violation: {len(orphan_senders)} unknown senders, {len(orphan_receivers)} unknown receivers."
            )

        # Ensure forbidden label columns are not present in accounts_df or transactions_df
        forbidden = {"is_suspicious_mule", "archetype_category", "scenario_group_id", "label_provenance"}
        leaked_acc = forbidden.intersection(set(accounts_df.columns))
        leaked_tx = forbidden.intersection(set(transactions_df.columns))
        if leaked_acc or leaked_tx:
            errors.append(f"Label leakage detected in entity tables: {leaked_acc | leaked_tx}")

    if labels_df is not None:
        if "account_id" not in labels_df.columns or "is_suspicious_mule" not in labels_df.columns:
            errors.append("Labels dataset missing account_id or is_suspicious_mule.")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "accounts_count": len(accounts_df),
        "transactions_count": len(transactions_df),
        "labels_count": len(labels_df) if labels_df is not None else 0,
    }


def persist_synthetic_dataset(
    db: Session,
    gen_bundle: Dict[str, Any],
    reset_existing: bool = True,
    actor: str = "System",
) -> Dict[str, Any]:
    """
    Validates and bulk-persists generated accounts, transactions, and isolated labels into the database,
    plus writes CSV artifacts to data/generated/.
    """
    accounts_df: pd.DataFrame = gen_bundle["accounts_df"]
    transactions_df: pd.DataFrame = gen_bundle["transactions_df"]
    labels_df: pd.DataFrame = gen_bundle["labels_df"]
    dataset_id: str = gen_bundle["dataset_id"]

    validation = validate_dataset_frames(accounts_df, transactions_df, labels_df)
    if not validation["valid"]:
        raise ValueError(f"Dataset validation failed: {validation['errors']}")

    if reset_existing:
        reset_db(force=True)
    else:
        init_db()

    run_id = f"run-gen-{uuid.uuid4().hex[:8]}"
    meta_run = DatasetTrainingMetadata(
        run_id=run_id,
        run_type="synthetic_generation",
        status="running",
        dataset_id=dataset_id,
        random_seed=gen_bundle["random_seed"],
        account_count=len(accounts_df),
        transaction_count=len(transactions_df),
        parameters_json={
            "num_accounts": len(accounts_df),
            "num_transactions": len(transactions_df),
            "random_seed": gen_bundle["random_seed"],
        },
        started_at=utcnow(),
    )
    db.add(meta_run)
    db.commit()

    # Prepare JSON columns for SQLite / SQLAlchemy bulk insert
    acc_rows = accounts_df.to_dict(orient="records")
    tx_rows = transactions_df.to_dict(orient="records")
    lbl_rows = labels_df.to_dict(orient="records")

    db.bulk_insert_mappings(Account, acc_rows)
    db.bulk_insert_mappings(SyntheticLabel, lbl_rows)
    # Insert transactions in chunks of 50,000 for low memory overhead
    chunk_size = 50000
    for start in range(0, len(tx_rows), chunk_size):
        db.bulk_insert_mappings(Transaction, tx_rows[start : start + chunk_size])
    db.commit()

    # Save sample / latest CSVs to data/generated
    gen_dir = DATA_DIR / "generated"
    accounts_df.drop(columns=["metadata_json"], errors="ignore").to_csv(
        gen_dir / "accounts.csv", index=False
    )
    transactions_df.drop(columns=["metadata_json"], errors="ignore").to_csv(
        gen_dir / "transactions.csv", index=False
    )
    labels_df.drop(columns=["label_provenance"], errors="ignore").to_csv(
        gen_dir / "labels.csv", index=False
    )

    meta_run.status = "completed"
    meta_run.summary_json = gen_bundle["summary"]
    meta_run.completed_at = utcnow()
    db.commit()

    record_audit_event(
        db=db,
        event_type="dataset_generation",
        actor=actor,
        target_type="dataset",
        target_id=dataset_id,
        action_summary=f"Generated & validated synthetic dataset '{dataset_id}' ({len(accounts_df):,} accounts, {len(transactions_df):,} transactions).",
        details=gen_bundle["summary"],
    )

    return {
        "run_id": run_id,
        "validation": validation,
        "summary": gen_bundle["summary"],
    }
