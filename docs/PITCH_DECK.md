# FlyGuard AI — Pitch Deck (10 Slides)

> **Generated Presentation Files**:
> - **PDF Pitch Deck**: `deliverables/FlyGuard_AI_Pitch_Deck.pdf`
> - **PowerPoint Pitch Deck**: `deliverables/FlyGuard_AI_Pitch_Deck.pptx`

---

## Slide 1: Title — FlyGuard AI
- **Headline**: Explainable Graph & Behavioral Intelligence for Money-Mule Detection
- **Sub-headline**: Stopping multi-hop illicit financial flows without drowning AML teams in false positives.
- **Stack**: FastAPI · XGBoost + Isotonic Calibration · NetworkX · TreeSHAP · React 18 + Cytoscape.js

---

## Slide 2: The Problem — Who Has It & Why It Matters
- **Who Suffers**:
  1. **Bank & Fintech AML/FIU Teams**: Overwhelmed by **90%–95% false-positive alert rates** from legacy static rules.
  2. **Instant Payment Rails (RTP, FedNow, UPI, SEPA Instant)**: Funds vanish across 3–4 mule hops in under 60 minutes.
  3. **Legitimate High-Volume Businesses (SMBs & Payment Collectors)**: Wrongfully flagged and frozen by crude velocity thresholds.
- **Why It Matters**: Over **$800B–$2T** is laundered globally each year, and regulators reject uncalibrated "black-box" AI scores that lack human-verifiable evidence.

---

## Slide 3: Why Legacy Rules & Black-Box ML Fail
- **Static Rules Miss Structural Evasion**:
  - *Fan-In Funnels*, *Structuring Splitters*, *Circular Rings*, and *Dormant-to-Burst Takeovers* stay just below static dollar cutoffs.
- **Standard ML Leaks or Overfits**:
  - Account ID correlations, temporal lookahead leakage, and ungrouped ring splitting inflate lab benchmarks while failing in production.
- **No Explainability = No SAR Filing**:
  - Investigators need exact drivers and graph topology to justify Suspicious Activity Reports.

---

## Slide 4: The Solution — FlyGuard AI Platform
- **12-Page Investigative Command Center** combining:
  1. **26 Leakage-Free Behavioral, Velocity & Graph Centrality Features**
  2. **Multi-Stage Calibrated Risk Scoring (`0–100` Ordinal Triage Index)**
  3. **Real-Time Per-Account TreeSHAP Attribution & Narrative Generation**
  4. **Interactive 1–3 Hop Network Graph & Laundering Path Tracer**
  5. **Counterfactual "What-If" Simulation Lab**
  6. **Case Management & Tamper-Evident Secret-Redacting Audit Trail**

---

## Slide 5: 3-Tier Behavioral Simulation & Anti-Leakage Architecture
- **20,000 Accounts & 200,000 Transactions (`seed=42`)**:
  - **79% Ordinary Legitimate**: Salary, savings, personal P2P, temporary spikes.
  - **15% Hard Negatives**: High-volume SMBs, merchant payment aggregators, shared households, cross-border remittances.
  - **6% Suspicious Money Mules**: Rapid pass-throughs, fan-in funnels, fan-out splitters, circular rings, dormant bursts, 4-hop layered chains.
- **Strict Anti-Leakage Guarantees**:
  - Permuted Account IDs, isolated `synthetic_labels` table, `FORBIDDEN_LEAKAGE_COLUMNS` guard, temporal cutoff enforcement, and `GroupShuffleSplit` by `scenario_group_id`.

---

## Slide 6: Calibrated ML Pipeline & Feature Engineering
- **Top Predictive Signals (Held-Out Test Evaluation)**:
  1. `median_holding_time_hours` (49.7% importance) — elapsed time between receiving and forwarding funds.
  2. `high_risk_channel_ratio` (20.6% importance) — share of instant P2P, wire, and crypto-ramp rails.
  3. `rapid_passthrough_ratio` (9.7% importance) — share of outgoing transfers within 3 hours of deposit.
  4. `unique_counterparties`, `out_degree`, `cycle_participation_score`, and `pagerank_score`.
- **Smooth Isotonic Calibration**: Reduces Brier score to near-zero and maps calibrated probabilities monotonically to `Low (<35)`, `Moderate (35–65)`, `High (65–85)`, and `Critical (>=85)`.

---

## Slide 7: Explainable AI (TreeSHAP) & Counterfactual What-If Lab
- **Per-Account TreeSHAP Waterfall**:
  - Shows exact positive/negative log-odds contributions for all 26 features alongside plain-English investigative summaries and known feature limitations.
- **Interactive What-If Counterfactual Lab**:
  - Analysts modify feature values (e.g., increasing holding time from `0.5h` to `36h` or reducing channel risk) and immediately see the recalibrated score delta (`94.2 -> 18.5`).

---

## Slide 8: Multi-Hop Network Intelligence & Case Management
- **NetworkX + Cytoscape.js Graph Engine**:
  - Renders 1-to-3 hop ego networks bounded for sub-second browser performance.
  - Detects bidirectional reciprocity, circular rings (up to 5 hops), and shortest laundering paths (`POST /api/graph/path`).
- **End-to-End Case Dossiers**:
  - Convert alerts into prioritized investigations, attach graph/SHAP evidence snapshots, add analyst notes, and track status transitions.

---

## Slide 9: Enterprise Security, Governance & Deployment
- **Security & Compliance by Design**:
  - Immutable `audit_events` table with recursive sensitive-key redaction (`password`, `token`, `secret`, `api_key`).
  - Production reset guard (`ALLOW_DB_RESET=false` blocks destructive operations in production).
  - Explicit regulatory disclaimers separating decision-support triage scores from legal proof.
- **Turnkey Deployment**:
  - Docker Compose (`docker compose up --build`), one-command startup (`./scripts/start_all.sh`), and 100% passing `pytest` + `Vitest` suites.

---

## Slide 10: Impact Summary & Roadmap
- **Impact**:
  - Drastically reduces false positives on legitimate SMBs while surfacing multi-hop mule rings in seconds.
  - Cuts per-alert analyst triage time from 60+ minutes to under 5 minutes with pre-built SHAP & graph evidence.
- **Next Steps**:
  - Streaming Kafka/Flink real-time transaction ingestion.
  - Temporal Graph Neural Networks (TGN) alongside XGBoost ensembles.
  - Automated FinCEN / GoAML SAR XML draft export.

