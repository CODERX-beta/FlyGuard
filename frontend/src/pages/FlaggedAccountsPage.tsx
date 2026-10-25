import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  AlertOctagon,
  Search,
  Share2,
  FolderPlus,
  BrainCircuit,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { api } from "../services/api";
import { AccountSummary } from "../types/api";
import { RiskBadge } from "../components/RiskBadge";

export const FlaggedAccountsPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [items, setItems] = useState<AccountSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState(searchParams.get("search") || "");
  const [categoryTab, setCategoryTab] = useState<string>("all_flagged");
  const [sortBy, setSortBy] = useState("risk_score");
  const [selectedAccount, setSelectedAccount] = useState<AccountSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const fetchAccounts = async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {
        page,
        page_size: 20,
        search: search || undefined,
        sort_by: sortBy,
        sort_dir: "desc",
      };
      if (categoryTab === "all_flagged") {
        params.flagged_only = true;
      } else if (categoryTab !== "all") {
        params.risk_category = categoryTab;
      }
      const res = await api.getAccounts(params);
      setItems(res.items || []);
      setTotal(res.total || 0);
      if (res.items?.length > 0 && !selectedAccount) {
        setSelectedAccount(res.items[0]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
  }, [page, categoryTab, sortBy]);

  const handleOpenInvestigation = async (accId: string) => {
    try {
      const res = await api.createInvestigation({
        account_id: accId,
        priority: "critical",
        assigned_to: "Sarah Chen (AML Lead)",
      });
      navigate(`/investigations?id=${res.investigation.investigation_id}`);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <AlertOctagon className="w-5 h-5 text-red-400" />
            Flagged Accounts & Mule Triage Queue
          </h1>
          <p className="text-xs text-slate-400">
            Accounts prioritized by calibrated XGBoost risk score and TreeSHAP behavioral attributions
          </p>
        </div>

        {/* Category Filter Tabs */}
        <div className="flex items-center gap-1.5 bg-[#0b1324] p-1 rounded-lg border border-[#1c2a44] text-xs">
          {[
            { id: "all_flagged", label: "All Flagged (35+)" },
            { id: "Critical", label: "Critical (85+)" },
            { id: "High", label: "High (65-85)" },
            { id: "Moderate", label: "Moderate (35-65)" },
            { id: "Low", label: "Low (<35)" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setCategoryTab(tab.id);
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded-md font-medium transition-colors ${
                categoryTab === tab.id
                  ? "bg-blue-600 text-white"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Search & Sort Bar */}
      <div className="p-3.5 rounded-xl bg-[#0b1324] border border-[#1c2a44] flex flex-wrap items-center justify-between gap-3 text-xs">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            fetchAccounts();
          }}
          className="flex items-center gap-2 flex-1 max-w-md"
        >
          <div className="relative flex-1">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search account ID, region, or segment..."
              className="w-full bg-[#060b16] border border-[#1c2a44] rounded-lg pl-8 pr-3 py-1.5 text-slate-100"
            />
          </div>
          <button
            type="submit"
            className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium"
          >
            Search
          </button>
        </form>

        <div className="flex items-center gap-2">
          <span className="text-slate-400">Sort By:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-[#060b16] border border-[#1c2a44] rounded-lg px-2.5 py-1.5 text-slate-200"
          >
            <option value="risk_score">Risk Score (Highest)</option>
            <option value="incoming_volume">Incoming Volume</option>
            <option value="outgoing_volume">Outgoing Volume</option>
            <option value="unique_counterparties">Distinct Counterparties</option>
            <option value="last_activity_at">Most Recent Activity</option>
          </select>
        </div>
      </div>

      {/* Main Split View: Table + Selected Account Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-8 rounded-xl bg-[#0b1324] border border-[#1c2a44] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#080f1e] text-slate-400 border-b border-[#1c2a44] uppercase text-[10px] tracking-wider">
                  <th className="py-3 px-3.5">Account ID</th>
                  <th className="py-3 px-3.5">Risk Level & Score</th>
                  <th className="py-3 px-3.5">Primary Model Attribution</th>
                  <th className="py-3 px-3.5">In / Out TX</th>
                  <th className="py-3 px-3.5">Counterparties</th>
                  <th className="py-3 px-3.5">Case Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#152036]">
                {loading ? (
                  <tr>
                    <td colSpan={6} className="py-10 text-center text-slate-400">
                      Loading flagged accounts...
                    </td>
                  </tr>
                ) : items.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-10 text-center text-slate-400">
                      No accounts match the selected filter criteria.
                    </td>
                  </tr>
                ) : (
                  items.map((acc) => (
                    <tr
                      key={acc.account_id}
                      onClick={() => setSelectedAccount(acc)}
                      className={`cursor-pointer transition-colors ${
                        selectedAccount?.account_id === acc.account_id
                          ? "bg-blue-950/35"
                          : "hover:bg-[#101c35]"
                      }`}
                    >
                      <td className="py-2.5 px-3.5">
                        <div className="font-mono font-bold text-white">{acc.account_id}</div>
                        <div className="text-[10px] text-slate-400">
                          {acc.account_type} • {acc.synthetic_region || "Global"}
                        </div>
                      </td>
                      <td className="py-2.5 px-3.5">
                        <RiskBadge category={acc.risk_category} score={acc.risk_score} size="md" />
                      </td>
                      <td className="py-2.5 px-3.5 max-w-xs">
                        <div className="text-slate-200 line-clamp-1">
                          {acc.explanation_summary || "Baseline activity"}
                        </div>
                      </td>
                      <td className="py-2.5 px-3.5 font-mono text-slate-300">
                        {acc.incoming_tx_count} in / {acc.outgoing_tx_count} out
                      </td>
                      <td className="py-2.5 px-3.5 font-mono text-slate-300">
                        {acc.unique_counterparties}
                      </td>
                      <td className="py-2.5 px-3.5">
                        {acc.investigation_status ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-purple-500/20 text-purple-300 border border-purple-500/40">
                            {acc.investigation_status.replace("_", " ")}
                          </span>
                        ) : (
                          <span className="text-[11px] text-slate-500">Unassigned</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="px-4 py-3 bg-[#080f1e] border-t border-[#1c2a44] flex items-center justify-between text-xs text-slate-400">
            <span>
              Showing page <strong className="text-white">{page}</strong> of{" "}
              <strong className="text-white">{Math.max(1, Math.ceil(total / 20))}</strong> (
              {total.toLocaleString()} accounts)
            </span>
            <div className="flex items-center gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="p-1.5 rounded bg-[#0b1324] border border-[#1c2a44] disabled:opacity-40"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                disabled={page * 20 >= total}
                onClick={() => setPage((p) => p + 1)}
                className="p-1.5 rounded bg-[#0b1324] border border-[#1c2a44] disabled:opacity-40"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Account Summary Side Panel */}
        <div className="lg:col-span-4">
          {selectedAccount ? (
            <div className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-4 sticky top-20">
              <div className="flex items-start justify-between border-b border-[#1c2a44] pb-3">
                <div>
                  <span className="text-[10px] font-mono uppercase text-sky-400">
                    Selected Account Lead
                  </span>
                  <h2 className="text-lg font-bold font-mono text-white">
                    {selectedAccount.account_id}
                  </h2>
                  <div className="text-xs text-slate-400">
                    {selectedAccount.account_type} • {selectedAccount.synthetic_region}
                  </div>
                </div>
                <RiskBadge
                  category={selectedAccount.risk_category}
                  score={selectedAccount.risk_score}
                  size="lg"
                />
              </div>

              {/* Probability vs Normalized Score Transparency Box */}
              <div className="grid grid-cols-3 gap-2 text-center text-xs">
                <div className="p-2 rounded bg-[#060b16] border border-[#16223b]">
                  <div className="text-[10px] text-slate-400">Triage Score</div>
                  <div className="font-mono font-bold text-white text-sm">
                    {selectedAccount.risk_score.toFixed(1)}/100
                  </div>
                </div>
                <div className="p-2 rounded bg-[#060b16] border border-[#16223b]">
                  <div className="text-[10px] text-slate-400">Calibrated Prob</div>
                  <div className="font-mono font-bold text-sky-300 text-sm">
                    {(selectedAccount.calibrated_probability * 100).toFixed(1)}%
                  </div>
                </div>
                <div className="p-2 rounded bg-[#060b16] border border-[#16223b]">
                  <div className="text-[10px] text-slate-400">Raw Model Prob</div>
                  <div className="font-mono font-bold text-slate-300 text-sm">
                    {(selectedAccount.raw_probability * 100).toFixed(1)}%
                  </div>
                </div>
              </div>

              {/* Volume & Counterparty Metrics */}
              <div className="grid grid-cols-2 gap-2.5 text-xs">
                <div className="p-2.5 rounded bg-[#070d19] border border-[#16223b]">
                  <div className="text-slate-400 text-[10px]">Incoming Volume</div>
                  <div className="font-mono font-semibold text-emerald-400">
                    ${selectedAccount.incoming_volume.toLocaleString()} (
                    {selectedAccount.incoming_tx_count} tx)
                  </div>
                </div>
                <div className="p-2.5 rounded bg-[#070d19] border border-[#16223b]">
                  <div className="text-slate-400 text-[10px]">Outgoing Volume</div>
                  <div className="font-mono font-semibold text-amber-400">
                    ${selectedAccount.outgoing_volume.toLocaleString()} (
                    {selectedAccount.outgoing_tx_count} tx)
                  </div>
                </div>
              </div>

              {/* Top SHAP Drivers */}
              <div className="space-y-2">
                <div className="text-xs font-semibold text-white">
                  Top Model Attribution Signals (TreeSHAP)
                </div>
                <p className="text-[11px] text-slate-300 bg-[#060b16] p-2.5 rounded border border-[#16223b]">
                  {selectedAccount.explanation_summary}
                </p>
                <div className="space-y-1.5">
                  {(selectedAccount.top_factors || []).slice(0, 4).map((f) => (
                    <div
                      key={f.feature}
                      className="p-2 rounded bg-[#070d19] border border-[#16223b] flex items-center justify-between text-xs"
                    >
                      <div>
                        <div className="text-slate-200 font-medium">{f.display_name}</div>
                        <div className="text-[10px] text-slate-400 font-mono">
                          Observed Value: {f.feature_value}
                        </div>
                      </div>
                      <span
                        className={`font-mono text-xs font-semibold px-2 py-0.5 rounded ${
                          f.shap_value >= 0
                            ? "bg-red-500/15 text-red-300"
                            : "bg-emerald-500/15 text-emerald-300"
                        }`}
                      >
                        {f.shap_value >= 0 ? `+${f.shap_value.toFixed(2)}` : f.shap_value.toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="space-y-2 pt-2">
                <button
                  onClick={() => navigate(`/network?account=${selectedAccount.account_id}`)}
                  className="w-full py-2 px-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center justify-center gap-2"
                >
                  <Share2 className="w-4 h-4" />
                  Explore Account Network Graph
                </button>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => handleOpenInvestigation(selectedAccount.account_id)}
                    className="py-2 px-3 rounded-lg bg-[#101c35] hover:bg-[#162647] border border-blue-500/30 text-sky-300 text-xs font-medium flex items-center justify-center gap-1.5"
                  >
                    <FolderPlus className="w-3.5 h-3.5" />
                    Investigate
                  </button>
                  <button
                    onClick={() =>
                      navigate(`/explainable-ai?account=${selectedAccount.account_id}`)
                    }
                    className="py-2 px-3 rounded-lg bg-[#101c35] hover:bg-[#162647] border border-[#1c2a44] text-slate-200 text-xs font-medium flex items-center justify-center gap-1.5"
                  >
                    <BrainCircuit className="w-3.5 h-3.5" />
                    Full SHAP XAI
                  </button>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
};

