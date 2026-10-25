import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Sliders, AlertTriangle, Play, RotateCcw, ArrowRight } from "lucide-react";
import { api } from "../services/api";
import { RiskBadge } from "../components/RiskBadge";

const KEY_SLIDER_FEATURES = [
  {
    name: "rapid_passthrough_ratio",
    label: "Rapid Forwarding Ratio (<3h)",
    min: 0,
    max: 1,
    step: 0.05,
  },
  {
    name: "passthrough_symmetry_score",
    label: "Pass-Through Volume Symmetry (0-1)",
    min: 0,
    max: 1,
    step: 0.05,
  },
  {
    name: "median_holding_time_hours",
    label: "Median Holding Time (Hours)",
    min: 0.2,
    max: 240,
    step: 1,
  },
  {
    name: "turnover_to_declared_ratio",
    label: "Observed vs Declared Monthly Turnover Ratio",
    min: 0.1,
    max: 25,
    step: 0.2,
  },
  {
    name: "in_degree",
    label: "Network In-Degree (Distinct Senders)",
    min: 0,
    max: 50,
    step: 1,
  },
  {
    name: "out_degree",
    label: "Network Out-Degree (Onward Destinations)",
    min: 0,
    max: 50,
    step: 1,
  },
  {
    name: "dormancy_burst_indicator",
    label: "Dormancy-to-Burst Composite Score",
    min: 0,
    max: 15,
    step: 0.5,
  },
  {
    name: "cycle_participation_score",
    label: "Circular Flow / Reciprocity Score",
    min: 0,
    max: 2,
    step: 0.1,
  },
];

export const WhatIfLabPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [accountId, setAccountId] = useState(searchParams.get("account") || "");
  const [flaggedList, setFlaggedList] = useState<any[]>([]);
  const [overrides, setOverrides] = useState<Record<string, number>>({});
  const [baselineValues, setBaselineValues] = useState<Record<string, number>>({});
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const init = async () => {
      try {
        const res = await api.getAccounts({
          flagged_only: true,
          page: 1,
          page_size: 25,
          sort_by: "risk_score",
          sort_dir: "desc",
        });
        const items = res.items || [];
        setFlaggedList(items);
        const target = accountId || items[0]?.account_id;
        if (target) {
          setAccountId(target);
          await loadBaseline(target);
        }
      } catch (err) {
        console.error(err);
      }
    };
    init();
  }, []);

  const loadBaseline = async (targetId: string) => {
    setLoading(true);
    try {
      const sim = await api.runWhatIf({
        account_id: targetId,
        feature_overrides: {},
        actor: "Investigator",
      });
      setResult(sim);
      const map: Record<string, number> = {};
      (sim.editable_features || []).forEach((f: any) => {
        map[f.name] = f.current_value;
      });
      setBaselineValues(map);
      setOverrides(map);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleRunSimulation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!accountId) return;
    setLoading(true);
    try {
      const sim = await api.runWhatIf({
        account_id: accountId,
        feature_overrides: overrides,
        actor: "Sarah Chen (AML Lead)",
      });
      setResult(sim);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Hypothetical Non-Destructive Banner */}
      <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/40 flex items-center justify-between gap-3 text-xs text-amber-200">
        <div className="flex items-center gap-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>
            <strong>HYPOTHETICAL COUNTERFACTUAL SIMULATION LAB:</strong> Results below are strictly
            hypothetical sensitivity tests. Historical transaction records and persisted account
            predictions are NEVER modified by What-If simulations.
          </span>
        </div>
        <span className="px-2 py-0.5 rounded bg-amber-500/20 font-mono text-[10px] shrink-0">
          NON-DESTRUCTIVE SANDBOX
        </span>
      </div>

      {/* Header & Account Selector */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Sliders className="w-5 h-5 text-sky-400" />
            What-If Counterfactual Analysis Lab
          </h1>
          <p className="text-xs text-slate-400">
            Test how hypothetical changes to holding time, pass-through symmetry, or network degree impact risk scores
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-400">Target Account:</span>
          <select
            value={accountId}
            onChange={(e) => {
              setAccountId(e.target.value);
              setSearchParams({ account: e.target.value });
              loadBaseline(e.target.value);
            }}
            className="bg-[#0b1324] border border-[#1c2a44] rounded-lg px-3 py-1.5 text-white font-mono"
          >
            {flaggedList.map((a) => (
              <option key={a.account_id} value={a.account_id}>
                {a.account_id} — {a.risk_category} ({Math.round(a.risk_score)})
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left: Interactive Feature Sliders */}
        <form
          onSubmit={handleRunSimulation}
          className="lg:col-span-6 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-4 text-xs"
        >
          <div className="flex items-center justify-between border-b border-[#1c2a44] pb-2.5">
            <h2 className="font-semibold text-white text-sm">
              Hypothetical Feature Controls ({accountId})
            </h2>
            <button
              type="button"
              onClick={() => setOverrides({ ...baselineValues })}
              className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center gap-1"
            >
              <RotateCcw className="w-3 h-3" /> Reset to Recorded Baseline
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            {KEY_SLIDER_FEATURES.map((feat) => {
              const curVal = overrides[feat.name] ?? 0;
              const baseVal = baselineValues[feat.name] ?? 0;
              const changed = Math.abs(curVal - baseVal) > 1e-4;
              return (
                <div
                  key={feat.name}
                  className={`p-3 rounded-lg border ${
                    changed
                      ? "bg-blue-950/30 border-blue-500/40"
                      : "bg-[#060b16] border-[#16223b]"
                  } space-y-1.5`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-slate-200">{feat.label}</span>
                    <span className="font-mono font-bold text-sky-300">{curVal}</span>
                  </div>
                  <input
                    type="range"
                    min={feat.min}
                    max={feat.max}
                    step={feat.step}
                    value={curVal}
                    onChange={(e) =>
                      setOverrides({
                        ...overrides,
                        [feat.name]: Number(e.target.value),
                      })
                    }
                    className="w-full accent-sky-400"
                  />
                  <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono">
                    <span>Recorded Baseline: {baseVal}</span>
                    {changed && (
                      <span className="text-amber-300">
                        Δ {(curVal - baseVal >= 0 ? "+" : "") + (curVal - baseVal).toFixed(2)}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold flex items-center justify-center gap-2"
          >
            <Play className="w-4 h-4" />
            {loading ? "Evaluating Counterfactual..." : "Run Hypothetical What-If Analysis"}
          </button>
        </form>

        {/* Right: Side-by-Side Comparison */}
        <div className="lg:col-span-6 space-y-4">
          {result && (
            <div className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-4">
              <div className="flex items-center justify-between border-b border-[#1c2a44] pb-2.5">
                <h2 className="text-sm font-semibold text-white">
                  Counterfactual Outcome Comparison
                </h2>
                <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono text-[10px]">
                  HYPOTHETICAL RESULT
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs">
                <div className="p-3.5 rounded-lg bg-[#060b16] border border-[#16223b] space-y-2">
                  <div className="text-slate-400 uppercase text-[10px] font-mono">
                    Original Recorded Score
                  </div>
                  <div className="text-3xl font-bold font-mono text-white">
                    {result.original.normalized_risk_score.toFixed(1)}
                    <span className="text-sm text-slate-500">/100</span>
                  </div>
                  <RiskBadge
                    category={result.original.risk_category}
                    score={result.original.normalized_risk_score}
                    size="md"
                  />
                  <div className="text-[11px] text-slate-400 font-mono">
                    Calibrated Prob: {(result.original.calibrated_probability * 100).toFixed(1)}%
                  </div>
                </div>

                <div className="p-3.5 rounded-lg bg-blue-950/30 border border-blue-500/40 space-y-2">
                  <div className="text-sky-300 uppercase text-[10px] font-mono">
                    Hypothetical Simulated Score
                  </div>
                  <div className="flex items-baseline gap-2">
                    <div className="text-3xl font-bold font-mono text-white">
                      {result.hypothetical.normalized_risk_score.toFixed(1)}
                      <span className="text-sm text-slate-500">/100</span>
                    </div>
                    <span
                      className={`font-mono text-xs font-bold ${
                        result.score_delta >= 0 ? "text-red-400" : "text-emerald-400"
                      }`}
                    >
                      ({result.score_delta >= 0 ? `+${result.score_delta}` : result.score_delta})
                    </span>
                  </div>
                  <RiskBadge
                    category={result.hypothetical.risk_category}
                    score={result.hypothetical.normalized_risk_score}
                    size="md"
                  />
                  <div className="text-[11px] text-sky-300 font-mono">
                    Calibrated Prob: {(result.hypothetical.calibrated_probability * 100).toFixed(1)}%
                  </div>
                </div>
              </div>

              {/* Applied Overrides */}
              {result.applied_changes?.length > 0 && (
                <div className="space-y-1.5 text-xs">
                  <div className="font-semibold text-slate-300">
                    Modified Feature Inputs ({result.applied_changes.length})
                  </div>
                  {result.applied_changes.map((ch: any) => (
                    <div
                      key={ch.feature}
                      className="p-2 rounded bg-[#060b16] border border-[#16223b] flex items-center justify-between font-mono text-[11px]"
                    >
                      <span className="text-slate-200">{ch.display_name}</span>
                      <span className="flex items-center gap-1.5 text-sky-300">
                        {ch.original_value} <ArrowRight className="w-3 h-3" />{" "}
                        <strong>{ch.hypothetical_value}</strong>
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Hypothetical Top SHAP Factors */}
              <div className="space-y-1.5 text-xs">
                <div className="font-semibold text-white">
                  Hypothetical Top SHAP Attributions
                </div>
                {(result.hypothetical.top_factors || []).slice(0, 5).map((f: any) => (
                  <div
                    key={f.feature}
                    className="p-2 rounded bg-[#060b16] border border-[#16223b] flex items-center justify-between"
                  >
                    <span className="text-slate-200">{f.display_name}</span>
                    <span
                      className={`font-mono font-bold ${
                        f.shap_value >= 0 ? "text-red-400" : "text-emerald-400"
                      }`}
                    >
                      {f.shap_value >= 0 ? `+${f.shap_value.toFixed(3)}` : f.shap_value.toFixed(3)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

