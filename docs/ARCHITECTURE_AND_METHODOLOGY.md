# FlyGuard AI — Architecture, Feature Engineering & Risk Scoring Methodology

## 1. Decision-Support & Synthetic Data Disclaimer
FlyGuard AI is an investigative decision-support platform designed to detect potentially suspicious money-mule accounts and multi-hop transaction networks.
- **Triage Signal Only**: Model probabilities, normalized risk scores (0–100), and TreeSHAP attributions are investigative leads, **not** proof of criminal conduct.
- **Synthetic Data Scope**: All generated accounts, transactions, and regional tags are 100% synthetic. Performance metrics achieved on synthetic test splits do not guarantee equivalent performance on real-world banking records.

## 2. Anti-Leakage Architecture
1. **Identifier Randomization**: Account IDs (`AC-100000`..`AC-119999`) are randomly permuted across behavioral archetypes so ID ordering carries zero predictive signal. Transaction IDs (`TX-1000000`..) are assigned strictly in chronological order.
2. **Label Isolation**: Ground-truth synthetic labels (`is_suspicious_mule`), `archetype_category`, `scenario_group_id`, and `label_provenance` are stored exclusively in the `synthetic_labels` table and `data/generated/labels.csv`. They are blocked by `FORBIDDEN_LEAKAGE_COLUMNS` from entering feature construction.
3. **Temporal Cutoff Guard**: `compute_account_features(..., as_of_timestamp)` filters out all transactions occurring after `as_of_timestamp` prior to computing volume, velocity, holding-time, and network centrality metrics.
4. **Scenario-Group-Aware Splitting**: Connected mule rings and multi-hop chains share a `scenario_group_id` and are kept together within Train (70%), Validation (15%), or Test (15%) splits using `GroupShuffleSplit` so connected rings never leak across train and test sets.

## 3. Multi-Stage Risk Scoring Layer
FlyGuard AI separates raw model outputs from operational triage categories:
1. **Raw Model Probability (`raw_probability`)**: Unadjusted logistic output from the trained `XGBClassifier`.
2. **Calibrated Probability (`calibrated_probability`)**: Probability calibrated on the held-out validation split via `SmoothIsotonicCalibrator` and verified by Brier score reduction on the test set.
3. **Normalized Risk Score (`normalized_risk_score`)**: Monotonic piecewise-linear mapping of `calibrated_probability` onto a `0–100` triage index:
   - `[0.00, 0.15] -> [0, 35)`
   - `[0.15, 0.45] -> [35, 65)`
   - `[0.45, 0.78] -> [65, 85)`
   - `[0.78, 1.00] -> [85, 100]`
   *Note: A normalized score of 80 is an ordinal ranking index on a 0–100 scale, NOT an 80% probability of criminal guilt.*
4. **Risk Category (`risk_category`)**: Configurable thresholds (`Low < 35`, `Moderate 35–65`, `High 65–85`, `Critical >= 85`).
5. **Alert Priority (`alert_priority`)**: Operational queue priority (`None`, `Medium`, `High`, `Urgent`).

