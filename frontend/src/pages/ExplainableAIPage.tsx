import React, { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from "recharts";
import { BrainCircuit, ShieldAlert, Sliders, Share2 } from "lucide-react";
import { api } from "../services/api";
import { RiskBadge } from "../components/RiskBadge";

export const ExplainableAIPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const [accountId, setAccountId] = useState(searchParams.get("account") || "");
  const [inputAccount, setInputAccount] = useState(searchParams.get("account") || "");
  const [flaggedList, setFlaggedList] = useState<any[]>([]);
  const [explanation, setExplanation] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadInitial = async () => {
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
          setInputAccount(target);
        }
      } catch (err) {
        console.error(err);
      }
    };
    loadInitial();
  }, []);

  useEffect(() => {
    if (!accountId) return;
    const fetchExplanation = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.explainAccount(accountId);
        setExplanation(res);
      } catch (err: any) {
        setError(err.message || "Explanation unavailable for this account");
        setExplanation(null);
      } finally {
        setLoading(false);
      }
    };
    fetchExplanation();
  }, [accountId]);

  const topChartFeatures = (explanation?.all_features || []).slice(0, 12).map((f: any) => ({
    name: f.display_name,
    shap: f.shap_value,
    value: f.feature_value,
  }));

  return (
    <div className="space-y-4">
      {/* Header & Account Selector */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <BrainCircuit className="w-5 h-5 text-sky-400" />
            Explainable AI (TreeSHAP Attribution Inspector)
          </h1>
          <p className="text-xs text-slate-400">
            Exact feature-level log-odds contributions explaining why the XGBoost model flagged an account
          </p>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (inputAccount.trim()) {
              setAccountId(inputAccount.trim());
              setSearchParams({ account: inputAccount.trim() });
            }
          }}
          className="flex items-center gap-2 text-xs"
        >
          <select
            value={accountId}
            onChange={(e) => {
              setAccountId(e.target.value);
              setInputAccount(e.target.value);
              setSearchParams({ account: e.target.value });
            }}
            className="bg-[#0b1324] border border-[#1c2a44] rounded-lg px-3 py-1.5 text-slate-200 font-mono"
          >
            {flaggedList.map((a) => (
              <option key={a.account_id} value={a.account_id}>
                {a.account_id} — {a.risk_category} ({Math.round(a.risk_score)})
              </option>
            ))}
          </select>
          <input
            type="text"
            value={inputAccount}
            onChange={(e) => setInputAccount(e.target.value)}
            placeholder="Account ID..."
            className="bg-[#0b1324] border border-[#1c2a44] rounded-lg px-3 py-1.5 text-white font-mono w-36"
          />
          <button
            type="submit"
            className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium"
          >
            Explain
          </button>
        </form>
      </div>

      {/* Evidentiary Distinction Banner */}
      <div className="p-3 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center justify-between gap-3 text-xs text-sky-200">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-sky-400 shrink-0" />
          <span>
            <strong>MODEL ATTRIBUTION vs CONFIRMED EVIDENCE:</strong>{" "}
            {explanation?.disclaimer ||
              "SHAP values quantify how each engineered feature shifted the model output relative to the baseline. They are mathematical explanations of a statistical prediction, NOT proof of illicit intent."}
          </span>
        </div>
      </div>

      {loading ? (
        <div className="p-10 text-center text-xs text-slate-400">
          Computing exact TreeSHAP feature attributions...
        </div>
      ) : error ? (
        <div className="p-6 rounded-xl bg-red-950/30 border border-red-500/40 text-xs text-red-200">
          <div className="font-bold mb-1">Explanation Error Handled Gracefully</div>
          <div>{error}</div>
        </div>
      ) : explanation ? (
        <>
          {/* Summary Strip */}
          <div className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] grid grid-cols-1 md:grid-cols-5 gap-3 text-xs">
            <div className="md:col-span-2 flex flex-col justify-between">
              <div className="flex items-center gap-2">
                <span className="font-mono text-base font-bold text-white">
                  {explanation.account_id}
                </span>
                <RiskBadge
                  category={explanation.risk_category}
                  score={explanation.normalized_risk_score}
                  size="md"
                />
              </div>
              <p className="text-slate-300 mt-1">{explanation.explanation_summary}</p>
            </div>
            <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b]">
              <div className="text-[10px] text-slate-400">Normalized Triage Score</div>
              <div className="text-lg font-bold font-mono text-white">
                {explanation.normalized_risk_score.toFixed(1)} / 100
              </div>
              <div className="text-[10px] text-slate-500">0-100 ranking scale</div>
            </div>
            <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b]">
              <div className="text-[10px] text-slate-400">Calibrated Probability</div>
              <div className="text-lg font-bold font-mono text-sky-300">
                {(explanation.calibrated_probability * 100).toFixed(2)}%
              </div>
              <div className="text-[10px] text-slate-500">
                Raw: {(explanation.raw_probability * 100).toFixed(2)}%
              </div>
            </div>
            <div className="flex flex-col justify-center gap-2">
              <button
                onClick={() => navigate(`/what-if?account=${explanation.account_id}`)}
                className="py-1.5 px-3 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium flex items-center justify-center gap-1.5"
              >
                <Sliders className="w-3.5 h-3.5" /> Open in What-If Lab
              </button>
              <button
                onClick={() => navigate(`/network?account=${explanation.account_id}`)}
                className="py-1.5 px-3 rounded bg-[#101c35] hover:bg-[#162647] border border-[#1c2a44] text-sky-300 font-medium flex items-center justify-center gap-1.5"
              >
                <Share2 className="w-3.5 h-3.5" /> View Network Graph
              </button>
            </div>
          </div>

          {/* SHAP Bar Chart + Positive & Negative Contributor Lists */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            <div className="lg:col-span-7 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44]">
              <h2 className="text-sm font-semibold text-white mb-1">
                Top 12 Feature Contributions (TreeSHAP Log-Odds Shift)
              </h2>
              <p className="text-[11px] text-slate-400 mb-3">
                Red bars (+SHAP) push risk score higher; Emerald bars (-SHAP) reduce predicted risk
              </p>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={topChartFeatures}
                    layout="vertical"
                    margin={{ top: 5, right: 20, left: 110, bottom: 5 }}
                  >
                    <XAxis type="number" stroke="#64748b" fontSize={10} />
                    <YAxis
                      type="category"
                      dataKey="name"
                      stroke="#cbd5e1"
                      fontSize={11}
                      width={145}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#091122",
                        borderColor: "#1c2a44",
                        fontSize: "12px",
                      }}
                    />
                    <ReferenceLine x={0} stroke="#475569" />
                    <Bar dataKey="shap" name="SHAP Log-Odds Contribution">
                      {topChartFeatures.map((entry: any, index: number) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={entry.shap >= 0 ? "#ef4444" : "#10b981"}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="lg:col-span-5 space-y-4 text-xs">
              <div className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-2.5">
                <h3 className="font-semibold text-red-300 uppercase tracking-wider text-[11px]">
                  Risk-Increasing Factors (+SHAP)
                </h3>
                {(explanation.positive_contributors || []).map((f: any) => (
                  <div
                    key={f.feature}
                    className="p-2.5 rounded bg-[#060b16] border border-red-500/20 space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-white">{f.display_name}</span>
                      <span className="font-mono text-red-400 font-bold">
                        +{f.shap_value.toFixed(3)}
                      </span>
                    </div>
                    <div className="text-[11px] font-mono text-sky-300">
                      Observed Value: {f.feature_value}
                    </div>
                    <p className="text-[10px] text-slate-400">{f.description}</p>
                  </div>
                ))}
              </div>

              <div className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-2.5">
                <h3 className="font-semibold text-emerald-300 uppercase tracking-wider text-[11px]">
                  Risk-Mitigating Factors (-SHAP)
                </h3>
                {(explanation.negative_contributors || []).map((f: any) => (
                  <div
                    key={f.feature}
                    className="p-2.5 rounded bg-[#060b16] border border-emerald-500/20 space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-white">{f.display_name}</span>
                      <span className="font-mono text-emerald-400 font-bold">
                        {f.shap_value.toFixed(3)}
                      </span>
                    </div>
                    <div className="text-[11px] font-mono text-sky-300">
                      Observed Value: {f.feature_value}
                    </div>
                    <p className="text-[10px] text-slate-400">{f.description}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
};

