import React, { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { BarChart3, Award, AlertCircle } from "lucide-react";
import { api } from "../services/api";

export const RiskAnalyticsPage: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [riskCategory, setRiskCategory] = useState("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await api.getRiskAnalytics(riskCategory);
        setData(res);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [riskCategory]);

  if (loading || !data) {
    return (
      <div className="p-10 text-center text-xs text-slate-400">
        Loading Risk Analytics & Held-Out Test Set Evaluation Metrics...
      </div>
    );
  }

  const metrics = data.model_metrics || {};
  const cm = metrics.confusion_matrix || {};

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-sky-400" />
            Risk Analytics & Model Evaluation Telemetry
          </h1>
          <p className="text-xs text-slate-400">
            Held-out test set evaluation metrics, score calibration, false-positive/negative archetype analysis
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-400">Filter Histogram:</span>
          <select
            value={riskCategory}
            onChange={(e) => setRiskCategory(e.target.value)}
            className="bg-[#0b1324] border border-[#1c2a44] rounded-lg px-3 py-1.5 text-slate-200"
          >
            <option value="all">All Categories</option>
            <option value="Critical">Critical Only</option>
            <option value="High">High Only</option>
            <option value="Moderate">Moderate Only</option>
            <option value="Low">Low Only</option>
          </select>
        </div>
      </div>

      {/* Held-Out Test Set Performance Strip */}
      <div className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Award className="w-4 h-4 text-emerald-400" />
            <h2 className="text-sm font-semibold text-white">
              Held-Out Test Set Performance ({data.active_model_version})
            </h2>
          </div>
          <span className="text-[11px] text-amber-300 font-mono">
            * Evaluated strictly on unseen scenario-isolated test split
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2.5 text-xs">
          <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b]">
            <div className="text-[10px] text-slate-400">Test ROC-AUC</div>
            <div className="text-base font-bold font-mono text-emerald-400">
              {metrics.roc_auc ?? "—"}
            </div>
          </div>
          <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b]">
            <div className="text-[10px] text-slate-400">Test PR-AUC</div>
            <div className="text-base font-bold font-mono text-sky-400">
              {metrics.pr_auc ?? "—"}
            </div>
          </div>
          <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b]">
            <div className="text-[10px] text-slate-400">Precision</div>
            <div className="text-base font-bold font-mono text-white">
              {metrics.precision !== undefined ? `${(metrics.precision * 100).toFixed(1)}%` : "—"}
            </div>
          </div>
          <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b]">
            <div className="text-[10px] text-slate-400">Recall</div>
            <div className="text-base font-bold font-mono text-white">
              {metrics.recall !== undefined ? `${(metrics.recall * 100).toFixed(1)}%` : "—"}
            </div>
          </div>
          <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b]">
            <div className="text-[10px] text-slate-400">F1 Score</div>
            <div className="text-base font-bold font-mono text-white">
              {metrics.f1_score !== undefined ? `${(metrics.f1_score * 100).toFixed(1)}%` : "—"}
            </div>
          </div>
          <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b]">
            <div className="text-[10px] text-slate-400">Brier (Calibrated)</div>
            <div className="text-base font-bold font-mono text-sky-300">
              {metrics.brier_score_calibrated ?? "—"}
            </div>
          </div>
          <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b]">
            <div className="text-[10px] text-slate-400">False Positive Rate</div>
            <div className="text-base font-bold font-mono text-amber-300">
              {metrics.false_positive_rate !== undefined
                ? `${(metrics.false_positive_rate * 100).toFixed(2)}%`
                : "—"}
            </div>
          </div>
          <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b]">
            <div className="text-[10px] text-slate-400">False Negative Rate</div>
            <div className="text-base font-bold font-mono text-rose-300">
              {metrics.false_negative_rate !== undefined
                ? `${(metrics.false_negative_rate * 100).toFixed(2)}%`
                : "—"}
            </div>
          </div>
        </div>
      </div>

      {/* Charts Row: Score Histogram + Channel Volume + Feature Importance */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-6 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44]">
          <h3 className="text-sm font-semibold text-white mb-1">
            Normalized Risk Score Distribution (10-Point Buckets)
          </h3>
          <p className="text-[11px] text-slate-400 mb-3">
            Distribution of monitored accounts across the 0–100 triage index
          </p>
          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.score_histogram || []}>
                <XAxis dataKey="range" stroke="#64748b" fontSize={10} />
                <YAxis stroke="#64748b" fontSize={10} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#091122",
                    borderColor: "#1c2a44",
                    fontSize: "12px",
                  }}
                />
                <Bar dataKey="count" name="Accounts" fill="#38bdf8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="lg:col-span-6 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44]">
          <h3 className="text-sm font-semibold text-white mb-1">
            Transaction Volume by Payment Channel
          </h3>
          <p className="text-[11px] text-slate-400 mb-3">
            Aggregate transfer volume across payment rails
          </p>
          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.channel_patterns || []}>
                <XAxis dataKey="channel" stroke="#64748b" fontSize={10} />
                <YAxis
                  stroke="#64748b"
                  fontSize={10}
                  tickFormatter={(v) => `$${(v / 1_000_000).toFixed(0)}M`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#091122",
                    borderColor: "#1c2a44",
                    fontSize: "12px",
                  }}
                  formatter={(v: any) => [`$${Number(v).toLocaleString()}`, "Total Volume"]}
                />
                <Bar dataKey="total_volume" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Bottom Row: Confusion Matrix + Threshold Sensitivity Table + Archetype Risk & FP/FN Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 text-xs">
        {/* Confusion Matrix & FP/FN Breakdown */}
        <div className="lg:col-span-4 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3">
          <h3 className="font-semibold text-white text-sm">
            Test Split Confusion Matrix & Error Analysis
          </h3>
          <div className="grid grid-cols-2 gap-2.5 text-center">
            <div className="p-3 rounded bg-emerald-950/30 border border-emerald-500/30">
              <div className="text-[10px] text-emerald-300">True Positives (Mules Caught)</div>
              <div className="text-lg font-bold font-mono text-white">
                {cm.true_positives ?? 0}
              </div>
            </div>
            <div className="p-3 rounded bg-amber-950/30 border border-amber-500/30">
              <div className="text-[10px] text-amber-300">False Positives (Legit Flagged)</div>
              <div className="text-lg font-bold font-mono text-white">
                {cm.false_positives ?? 0}
              </div>
            </div>
            <div className="p-3 rounded bg-rose-950/30 border border-rose-500/30">
              <div className="text-[10px] text-rose-300">False Negatives (Mules Missed)</div>
              <div className="text-lg font-bold font-mono text-white">
                {cm.false_negatives ?? 0}
              </div>
            </div>
            <div className="p-3 rounded bg-slate-900 border border-slate-700">
              <div className="text-[10px] text-slate-400">True Negatives (Legit Cleared)</div>
              <div className="text-lg font-bold font-mono text-white">
                {cm.true_negatives ?? 0}
              </div>
            </div>
          </div>

          <div className="p-3 rounded bg-[#060b16] border border-[#16223b] space-y-1.5">
            <div className="font-semibold text-slate-200 flex items-center gap-1.5">
              <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
              False-Positive & False-Negative Archetype Notes
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Difficult negative archetypes (such as high-velocity SMBs, same-day settlement collectors,
              and rapid remittance corridors) intentionally share behavioral overlap with subtle pass-through mules.
            </p>
          </div>
        </div>

        {/* Performance Across Configurable Thresholds */}
        <div className="lg:col-span-4 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3">
          <h3 className="font-semibold text-white text-sm">
            Performance Across Triage Thresholds
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="text-[10px] uppercase text-slate-400 border-b border-[#1c2a44]">
                  <th className="py-2">Score Cutoff</th>
                  <th className="py-2">Precision</th>
                  <th className="py-2">Recall</th>
                  <th className="py-2">F1</th>
                  <th className="py-2">Flagged</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#152036] font-mono">
                {(metrics.threshold_performance || []).map((row: any) => (
                  <tr key={row.threshold_score}>
                    <td className="py-2 font-bold text-sky-300">&ge; {row.threshold_score}</td>
                    <td className="py-2 text-slate-200">{(row.precision * 100).toFixed(1)}%</td>
                    <td className="py-2 text-slate-200">{(row.recall * 100).toFixed(1)}%</td>
                    <td className="py-2 text-white font-bold">{(row.f1_score * 100).toFixed(1)}%</td>
                    <td className="py-2 text-slate-400">{row.flagged_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Archetype Average Risk Scores */}
        <div className="lg:col-span-4 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3">
          <h3 className="font-semibold text-white text-sm">
            Average Risk Score by Behavioral Archetype
          </h3>
          <div className="space-y-1.5 max-h-60 overflow-y-auto">
            {(data.archetype_analytics || []).map((a: any) => (
              <div
                key={a.archetype}
                className="p-2 rounded bg-[#060b16] border border-[#16223b] flex items-center justify-between"
              >
                <div>
                  <div className="font-mono text-slate-200 font-medium">{a.archetype}</div>
                  <div className="text-[10px] text-slate-500">
                    {a.account_count} accounts •{" "}
                    {a.ground_truth_is_mule ? "Synthetic Mule" : "Synthetic Legitimate"}
                  </div>
                </div>
                <span
                  className={`font-mono font-bold px-2 py-0.5 rounded ${
                    a.avg_predicted_risk_score >= 65
                      ? "bg-red-500/20 text-red-300"
                      : a.avg_predicted_risk_score >= 25
                      ? "bg-amber-500/20 text-amber-300"
                      : "bg-emerald-500/20 text-emerald-300"
                  }`}
                >
                  {a.avg_predicted_risk_score.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

