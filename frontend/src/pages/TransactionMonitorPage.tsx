import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowLeftRight,
  Search,
  ChevronLeft,
  ChevronRight,
  Share2,
  Eye,
  X,
} from "lucide-react";
import { api } from "../services/api";
import { RiskBadge } from "../components/RiskBadge";

export const TransactionMonitorPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState(searchParams.get("search") || "");
  const [channel, setChannel] = useState("all");
  const [riskCategory, setRiskCategory] = useState("all");
  const [minAmount, setMinAmount] = useState("");
  const [loading, setLoading] = useState(true);
  const [selectedTx, setSelectedTx] = useState<any>(null);
  const navigate = useNavigate();

  const fetchTransactions = async () => {
    setLoading(true);
    try {
      const res = await api.getTransactions({
        page,
        page_size: 20,
        search: search || undefined,
        channel: channel !== "all" ? channel : undefined,
        risk_category: riskCategory !== "all" ? riskCategory : undefined,
        min_amount: minAmount ? Number(minAmount) : undefined,
      });
      setItems(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTransactions();
  }, [page, channel, riskCategory]);

  const handleInspectTx = async (txId: string) => {
    try {
      const detail = await api.getTransactionDetail(txId);
      setSelectedTx(detail);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <ArrowLeftRight className="w-5 h-5 text-sky-400" />
            Transaction Monitor & Corridor Ledger
          </h1>
          <p className="text-xs text-slate-400">
            Search, filter, and trace individual transfers across all monitored synthetic accounts
          </p>
        </div>
        <div className="text-xs text-slate-400 font-mono">
          Matching Records: <strong className="text-white">{total.toLocaleString()}</strong>
        </div>
      </div>

      {/* Filters */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setPage(1);
          fetchTransactions();
        }}
        className="p-3.5 rounded-xl bg-[#0b1324] border border-[#1c2a44] grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 text-xs"
      >
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="TX ID or Account ID..."
            className="w-full bg-[#060b16] border border-[#1c2a44] rounded-lg pl-8 pr-3 py-1.5 text-slate-100"
          />
        </div>

        <select
          value={channel}
          onChange={(e) => {
            setChannel(e.target.value);
            setPage(1);
          }}
          className="bg-[#060b16] border border-[#1c2a44] rounded-lg px-3 py-1.5 text-slate-200"
        >
          <option value="all">All Payment Channels</option>
          <option value="instant_p2p">Instant P2P</option>
          <option value="wire">Wire Transfer</option>
          <option value="crypto_ramp">Crypto Ramp</option>
          <option value="ach">ACH</option>
          <option value="swift">SWIFT Cross-Border</option>
          <option value="card_transfer">Card Transfer</option>
          <option value="mobile_wallet">Mobile Wallet</option>
        </select>

        <select
          value={riskCategory}
          onChange={(e) => {
            setRiskCategory(e.target.value);
            setPage(1);
          }}
          className="bg-[#060b16] border border-[#1c2a44] rounded-lg px-3 py-1.5 text-slate-200"
        >
          <option value="all">All Endpoint Risk Levels</option>
          <option value="Critical">Critical Endpoint</option>
          <option value="High">High Risk Endpoint</option>
          <option value="Moderate">Moderate Risk Endpoint</option>
          <option value="Low">Low Risk Endpoint</option>
        </select>

        <input
          type="number"
          value={minAmount}
          onChange={(e) => setMinAmount(e.target.value)}
          placeholder="Min Amount (USD)..."
          className="bg-[#060b16] border border-[#1c2a44] rounded-lg px-3 py-1.5 text-slate-100"
        />

        <button
          type="submit"
          className="bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg px-4 py-1.5"
        >
          Apply Filters
        </button>
      </form>

      {/* Main Table + Detail Drawer */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div
          className={`${
            selectedTx ? "lg:col-span-8" : "lg:col-span-12"
          } rounded-xl bg-[#0b1324] border border-[#1c2a44] overflow-hidden`}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#080f1e] text-slate-400 border-b border-[#1c2a44] uppercase text-[10px] tracking-wider">
                  <th className="py-3 px-4">Transaction ID</th>
                  <th className="py-3 px-4">Sender Account</th>
                  <th className="py-3 px-4">Receiver Account</th>
                  <th className="py-3 px-4">Amount (USD)</th>
                  <th className="py-3 px-4">Channel</th>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#152036]">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="py-10 text-center text-slate-400">
                      Loading transactions...
                    </td>
                  </tr>
                ) : items.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-10 text-center text-slate-400">
                      No transactions match the current filter criteria.
                    </td>
                  </tr>
                ) : (
                  items.map((tx) => (
                    <tr
                      key={tx.transaction_id}
                      onClick={() => handleInspectTx(tx.transaction_id)}
                      className="hover:bg-[#101c35] cursor-pointer transition-colors"
                    >
                      <td className="py-2.5 px-4 font-mono font-semibold text-sky-300">
                        {tx.transaction_id}
                      </td>
                      <td className="py-2.5 px-4">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-slate-200">{tx.sender_account_id}</span>
                          <RiskBadge
                            category={tx.sender_risk_category || "Low"}
                            score={tx.sender_risk_score}
                          />
                        </div>
                      </td>
                      <td className="py-2.5 px-4">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-slate-200">{tx.receiver_account_id}</span>
                          <RiskBadge
                            category={tx.receiver_risk_category || "Low"}
                            score={tx.receiver_risk_score}
                          />
                        </div>
                      </td>
                      <td className="py-2.5 px-4 font-mono font-bold text-white">
                        ${Number(tx.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-2.5 px-4">
                        <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[11px]">
                          {tx.channel}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 font-mono text-slate-400">
                        {tx.timestamp.replace("T", " ").slice(0, 16)}
                      </td>
                      <td className="py-2.5 px-4 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleInspectTx(tx.transaction_id);
                          }}
                          className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-sky-300 inline-flex items-center gap-1"
                        >
                          <Eye className="w-3 h-3" /> Inspect
                        </button>
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
              Page <strong className="text-white">{page}</strong> of{" "}
              <strong className="text-white">{Math.max(1, Math.ceil(total / 20))}</strong>
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

        {/* Transaction Detail Side Panel */}
        {selectedTx && (
          <div className="lg:col-span-4 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-4">
            <div className="flex items-center justify-between border-b border-[#1c2a44] pb-3">
              <div>
                <div className="text-[10px] text-sky-400 uppercase font-mono">
                  Transaction Record Inspector
                </div>
                <h2 className="text-base font-bold text-white font-mono">
                  {selectedTx.transaction.transaction_id}
                </h2>
              </div>
              <button
                onClick={() => setSelectedTx(null)}
                className="p-1 rounded hover:bg-slate-800 text-slate-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 rounded-lg bg-[#060b16] border border-[#16223b] flex items-center justify-between">
              <div>
                <div className="text-[11px] text-slate-400">Transfer Amount</div>
                <div className="text-xl font-bold font-mono text-white">
                  ${Number(selectedTx.transaction.amount).toLocaleString()} USD
                </div>
              </div>
              <div className="text-right">
                <div className="text-[11px] text-slate-400">Channel</div>
                <div className="font-mono text-xs text-sky-300">
                  {selectedTx.transaction.channel}
                </div>
              </div>
            </div>

            {/* Sender & Receiver Risk Cards */}
            <div className="space-y-2.5 text-xs">
              <div className="p-3 rounded-lg bg-[#070d19] border border-[#16223b] space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Originator (Sender)</span>
                  <RiskBadge
                    category={selectedTx.sender.risk_category}
                    score={selectedTx.sender.risk_score}
                  />
                </div>
                <div className="font-mono font-bold text-white">
                  {selectedTx.sender.account_id} ({selectedTx.sender.account_type})
                </div>
                <div className="text-[11px] text-slate-400">
                  Region: {selectedTx.sender.synthetic_region || "N/A"}
                </div>
                <button
                  onClick={() => navigate(`/network?account=${selectedTx.sender.account_id}`)}
                  className="mt-1 text-sky-400 hover:underline flex items-center gap-1 text-[11px]"
                >
                  <Share2 className="w-3 h-3" /> Open Sender in Network Graph
                </button>
              </div>

              <div className="p-3 rounded-lg bg-[#070d19] border border-[#16223b] space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Beneficiary (Receiver)</span>
                  <RiskBadge
                    category={selectedTx.receiver.risk_category}
                    score={selectedTx.receiver.risk_score}
                  />
                </div>
                <div className="font-mono font-bold text-white">
                  {selectedTx.receiver.account_id} ({selectedTx.receiver.account_type})
                </div>
                <div className="text-[11px] text-slate-400">
                  Region: {selectedTx.receiver.synthetic_region || "N/A"}
                </div>
                <button
                  onClick={() => navigate(`/network?account=${selectedTx.receiver.account_id}`)}
                  className="mt-1 text-sky-400 hover:underline flex items-center gap-1 text-[11px]"
                >
                  <Share2 className="w-3 h-3" /> Open Receiver in Network Graph
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <div className="text-xs font-semibold text-slate-300">
                Direct Corridor History ({selectedTx.corridor_history?.length || 0})
              </div>
              <div className="space-y-1.5 max-h-44 overflow-y-auto">
                {(selectedTx.corridor_history || []).map((pt: any) => (
                  <div
                    key={pt.transaction_id}
                    className="p-2 rounded bg-[#060b16] border border-[#16223b] flex items-center justify-between text-[11px]"
                  >
                    <span className="font-mono text-slate-300">{pt.transaction_id}</span>
                    <span className="font-mono text-white font-semibold">
                      ${Number(pt.amount).toLocaleString()}
                    </span>
                    <span className="text-slate-500 font-mono">{pt.timestamp.slice(0, 10)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

