#!/usr/bin/env python3
"""
FlyGuard AI — End-to-End Synthetic Data Generation, Feature Engineering, XGBoost Training,
Evaluation, and Account Risk Scoring Bootstrap Script.
"""
import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.database import SessionLocal, init_db
from backend.app.ml.model_pipeline import train_and_evaluate_model
from backend.app.ml.synthetic_generator import (
    generate_synthetic_dataset,
    persist_synthetic_dataset,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap FlyGuard AI synthetic dataset and XGBoost model.")
    parser.add_argument("--accounts", type=int, default=20000, help="Number of synthetic accounts (default: 20000)")
    parser.add_argument("--transactions", type=int, default=200000, help="Number of synthetic transactions (default: 200000)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--suspicious-rate", type=float, default=0.06, help="Suspicious mule rate (default: 0.06)")
    args = parser.parse_args()

    t0 = time.time()
    print(f"[FlyGuard AI] Initializing database and generating {args.accounts:,} accounts & {args.transactions:,} transactions (seed={args.seed})...")
    init_db()

    def progress_log(pct: float, msg: str) -> None:
        print(f"  [{pct:5.1f}%] {msg}")

    gen_bundle = generate_synthetic_dataset(
        num_accounts=args.accounts,
        num_transactions=args.transactions,
        random_seed=args.seed,
        suspicious_rate=args.suspicious_rate,
        progress_callback=progress_log,
    )

    db = SessionLocal()
    try:
        persist_res = persist_synthetic_dataset(
            db=db,
            gen_bundle=gen_bundle,
            reset_existing=True,
            actor="Bootstrap CLI",
        )
        print(f"[FlyGuard AI] Dataset persisted: {json.dumps(persist_res['summary'], indent=2)}")

        train_res = train_and_evaluate_model(
            db=db,
            dataset_id=gen_bundle["dataset_id"],
            random_seed=args.seed,
            activate_if_passed=True,
            score_all_accounts=True,
            actor="Bootstrap CLI",
            progress_callback=progress_log,
        )
        elapsed = time.time() - t0
        print(f"\n[FlyGuard AI] Pipeline completed in {elapsed:.1f}s!")
        print(f"  Active Model Version : {train_res['model_version']}")
        print(f"  Test ROC-AUC         : {train_res['metrics']['roc_auc']}")
        print(f"  Test PR-AUC          : {train_res['metrics']['pr_auc']}")
        print(f"  Test Precision       : {train_res['metrics']['precision']}")
        print(f"  Test Recall          : {train_res['metrics']['recall']}")
        print(f"  Test F1 Score        : {train_res['metrics']['f1_score']}")
        print(f"  Risk Distribution    : {train_res['scoring_summary']['risk_distribution']}")
        print(f"  Open Alerts Created  : {train_res['scoring_summary']['alerts_created']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

