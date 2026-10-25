# FlyGuard AI — Short Demo Video Guide & Script (< 3 Minutes)

- **Target Duration**: 2 minutes 15 seconds (Maximum allowed: 3:00)
- **Generated Video File**: `deliverables/FlyGuard_AI_Demo_Video.mp4` (1920x1080 Full HD MP4)

---

## Timestamped Storyboard & Voiceover Script

### Scene 1: The Problem — Money-Mule Networks & False-Positive Overload (0:00 – 0:25)
- **Visual**: Title card & problem breakdown comparing legacy static AML rules (90%+ false positives, blind to multi-hop chains) against modern money-mule syndicates (rapid pass-through funnels, circular rings, fan-in collectors).
- **Narration**:
  > *"Every year, hundreds of billions in cyber-fraud proceeds are laundered through money-mule networks on instant payment rails. Legacy rule-based AML systems generate over 90% false positives—flagging legitimate small businesses while missing rapid pass-through mules and multi-hop laundering rings. Meet FlyGuard AI: an explainable financial intelligence platform built to detect money-mule networks with precision."*

---

### Scene 2: Executive Command Center & Global Threat Map (0:25 – 0:50)
- **Visual**: Navigate to `http://localhost:5173/` (**Overview Page** and **Global Activity Map**). Highlight the 20,000 monitored accounts, 200,000 transactions, calibrated risk distribution (`Low`, `Moderate`, `High`, `Critical`), and cross-border corridor anomalies.
- **Narration**:
  > *"From the Command Center Overview, analysts monitor 20,000 accounts and 200,000 transactions across 6 money-mule archetypes and 4 hard-negative legitimate business segments. Instead of uncalibrated raw model probabilities, FlyGuard AI uses Smooth Isotonic Calibration mapped to a 0-to-100 triage index."*

---

### Scene 3: Multi-Hop Network Intelligence & Path Tracing (0:50 – 1:20)
- **Visual**: Open **Network Intelligence (`/network`)**. Select a critical flagged account, expand its 2-hop Cytoscape.js ego-graph, highlight a circular transaction ring and a 4-hop layered path between two suspect accounts.
- **Narration**:
  > *"In the Network Intelligence workspace, investigators explore 1-to-3 hop ego networks in real time. Here, we isolate a multi-sender fan-in funnel connected to a circular laundering ring, and trace the exact shortest flow of funds between suspect accounts."*

---

### Scene 4: Per-Account TreeSHAP Explainability (1:20 – 1:50)
- **Visual**: Open **Explainable AI (`/explainable-ai`)**. Show the TreeSHAP feature attribution waterfall for a flagged mule account: `median_holding_time_hours` (< 0.8 hrs), `high_risk_channel_ratio`, `rapid_passthrough_ratio`, and `cycle_participation_score`.
- **Narration**:
  > *"Regulators require transparent reasoning, not black-box scores. FlyGuard AI computes real-time TreeSHAP attributions for every account across 26 leakage-free features—showing analysts that a 42-minute median holding time and 96% rapid forwarding ratio drove this critical alert."*

---

### Scene 5: Counterfactual "What-If" Lab & Audit Governance (1:50 – 2:15)
- **Visual**: Open **What-If Lab (`/what-if`)**, adjust `median_holding_time_hours` from `0.6h` to `48h`, and click **Run Simulation** to watch the risk score drop from `94.2 (Critical)` to `18.5 (Low)`. Conclude on **Investigation Workspace (`/investigations`)** and **Audit Trail (`/audit-trail`)**.
- **Narration**:
  > *"With the Counterfactual What-If Lab, analysts test how behavioral shifts impact risk in real time. Finally, investigators open a structured case dossier, attach graph and SHAP evidence, and rely on an immutable, secret-redacting audit log. FlyGuard AI: transparent, leakage-free financial intelligence."*

