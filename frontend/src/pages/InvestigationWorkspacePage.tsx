import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  FolderSearch,
  MessageSquarePlus,
  FilePlus2,
  Share2,
  CheckCircle2,
  Clock,
  ShieldAlert,
} from "lucide-react";
import { api } from "../services/api";
import { RiskBadge } from "../components/RiskBadge";

export const InvestigationWorkspacePage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const [investigations, setInvestigations] = useState<any[]>([]);
  const [selectedInvId, setSelectedInvId] = useState<string>(
    searchParams.get("id") || ""
  );
  const [detail, setDetail] = useState<any>(null);
  const [accountTxs, setAccountTxs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Forms
  const [noteContent, setNoteContent] = useState("");
  const [evidenceTitle, setEvidenceTitle] = useState("");
  const [evidenceType, setEvidenceType] = useState("transaction_chain");
  const [evidenceRef, setEvidenceRef] = useState("");
  const [evidenceDesc, setEvidenceDesc] = useState("");
  const [statusUpdate, setStatusUpdate] = useState("");
  const [findingsText, setFindingsText] = useState("");

  const loadList = async () => {
    setLoading(true);
    try {
      const res = await api.getInvestigations();
      const list = res.items || [];
      setInvestigations(list);
      const targetId = searchParams.get("id") || selectedInvId || list[0]?.investigation_id;
      if (targetId) {
        setSelectedInvId(targetId);
        await loadDetail(targetId);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadDetail = async (invId: string) => {
    try {
      const d = await api.getInvestigationDetail(invId);
      setDetail(d);
      setStatusUpdate(d.investigation.status);
      setFindingsText(d.investigation.findings_summary || "");
      const txRes = await api.getAccountTransactions(d.investigation.account_id, 1, "all");
      setAccountTxs(txRes.items || []);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadList();
  }, []);

  const handleSelectInv = async (invId: string) => {
    setSelectedInvId(invId);
    setSearchParams({ id: invId });
    await loadDetail(invId);
  };

  const handleSaveStatusAndFindings = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedInvId) return;
    const updated = await api.updateInvestigation(selectedInvId, {
      status: statusUpdate,
      findings_summary: findingsText,
      actor: "Sarah Chen (AML Lead)",
    });
    setDetail(updated);
    const listRes = await api.getInvestigations();
    setInvestigations(listRes.items || []);
  };

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!noteContent.trim() || !selectedInvId) return;
    const updated = await api.addInvestigationNote(selectedInvId, {
      author: "Sarah Chen (AML Lead)",
      note_type: "analyst_note",
      content: noteContent.trim(),
    });
    setDetail(updated);
    setNoteContent("");
  };

  const handleAddEvidence = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!evidenceTitle.trim() || !selectedInvId) return;
    const updated = await api.addInvestigationEvidence(selectedInvId, {
      evidence_type: evidenceType,
      title: evidenceTitle.trim(),
      description: evidenceDesc.trim() || "Corroborating transaction/network artifact.",
      reference_id: evidenceRef.trim() || detail?.investigation?.account_id,
      added_by: "Sarah Chen (AML Lead)",
    });
    setDetail(updated);
    setEvidenceTitle("");
    setEvidenceRef("");
    setEvidenceDesc("");
  };

  const inv = detail?.investigation;
  const accCtx = detail?.account_context;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <FolderSearch className="w-5 h-5 text-sky-400" />
            Account Investigation Workspace
          </h1>
          <p className="text-xs text-slate-400">
            End-to-end case management, analyst notes, corroborating evidence, and audit governance
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Queue of Investigations */}
        <div className="lg:col-span-3 rounded-xl bg-[#0b1324] border border-[#1c2a44] p-3 space-y-2.5 max-h-[780px] overflow-y-auto">
          <div className="text-xs font-semibold text-slate-300 uppercase tracking-wider px-1">
            Investigation Queue ({investigations.length})
          </div>
          {loading && investigations.length === 0 ? (
            <div className="text-xs text-slate-400 p-4">Loading cases...</div>
          ) : (
            investigations.map((item) => (
              <div
                key={item.investigation_id}
                onClick={() => handleSelectInv(item.investigation_id)}
                className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                  selectedInvId === item.investigation_id
                    ? "bg-blue-950/40 border-blue-500/50"
                    : "bg-[#060b16] border-[#16223b] hover:bg-[#101c35]"
                }`}
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-mono font-bold text-sky-300">
                    {item.investigation_id}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-slate-800 text-slate-300">
                    {item.status.replace("_", " ")}
                  </span>
                </div>
                <div className="font-mono text-xs font-semibold text-white mt-1">
                  Account: {item.account_id}
                </div>
                <div className="text-[11px] text-slate-400 line-clamp-1 mt-0.5">
                  {item.title}
                </div>
                <div className="flex items-center justify-between text-[10px] text-slate-500 mt-2">
                  <span>{item.assigned_to.split("(")[0]}</span>
                  <span>Score: {Math.round(item.risk_score_at_open)}/100</span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Active Investigation Workspace */}
        <div className="lg:col-span-9 space-y-4">
          {!inv || !accCtx ? (
            <div className="p-8 rounded-xl bg-[#0b1324] border border-[#1c2a44] text-center text-xs text-slate-400">
              Select an investigation from the left queue or open one from Flagged Accounts.
            </div>
          ) : (
            <>
              {/* Case Header & Account Overview */}
              <div className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[#1c2a44] pb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-sky-400">
                        {inv.investigation_id}
                      </span>
                      <span className="text-slate-500">•</span>
                      <span className="font-mono text-sm font-bold text-white">
                        Target Account: {inv.account_id}
                      </span>
                      <RiskBadge
                        category={accCtx.risk_profile.risk_category}
                        score={accCtx.risk_profile.normalized_risk_score}
                        size="md"
                      />
                    </div>
                    <h2 className="text-base font-bold text-white mt-1">{inv.title}</h2>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => navigate(`/network?account=${inv.account_id}`)}
                      className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium flex items-center gap-1.5"
                    >
                      <Share2 className="w-3.5 h-3.5" />
                      Open Relationship Graph
                    </button>
                  </div>
                </div>

                {/* Account Overview Metrics + Status Update Form */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 text-xs">
                  <div className="lg:col-span-7 grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                    <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b]">
                      <div className="text-[10px] text-slate-400">Account Segment</div>
                      <div className="font-semibold text-white mt-0.5">
                        {accCtx.account.account_type} ({accCtx.account.kyc_tier})
                      </div>
                    </div>
                    <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b]">
                      <div className="text-[10px] text-slate-400">Synthetic Region</div>
                      <div className="font-semibold text-white mt-0.5">
                        {accCtx.account.synthetic_region}
                      </div>
                    </div>
                    <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b]">
                      <div className="text-[10px] text-slate-400">Counterparties</div>
                      <div className="font-mono font-bold text-sky-300 mt-0.5">
                        {accCtx.activity_summary.unique_counterparties} distinct
                      </div>
                    </div>
                    <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b]">
                      <div className="text-[10px] text-slate-400">Incoming Flow</div>
                      <div className="font-mono font-bold text-emerald-400 mt-0.5">
                        ${Number(accCtx.activity_summary.incoming_volume).toLocaleString()} (
                        {accCtx.activity_summary.incoming_tx_count})
                      </div>
                    </div>
                    <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b]">
                      <div className="text-[10px] text-slate-400">Outgoing Flow</div>
                      <div className="font-mono font-bold text-amber-400 mt-0.5">
                        ${Number(accCtx.activity_summary.outgoing_volume).toLocaleString()} (
                        {accCtx.activity_summary.outgoing_tx_count})
                      </div>
                    </div>
                    <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b]">
                      <div className="text-[10px] text-slate-400">Declared Turnover</div>
                      <div className="font-mono font-bold text-slate-200 mt-0.5">
                        ${Number(accCtx.account.declared_monthly_turnover).toLocaleString()}/mo
                      </div>
                    </div>
                  </div>

                  {/* Case Status & Findings Form */}
                  <form
                    onSubmit={handleSaveStatusAndFindings}
                    className="lg:col-span-5 p-3 rounded-lg bg-[#060b16] border border-[#16223b] space-y-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <label className="text-[11px] font-semibold text-slate-300">
                        Case Disposition Status:
                      </label>
                      <select
                        value={statusUpdate}
                        onChange={(e) => setStatusUpdate(e.target.value)}
                        className="bg-[#0b1324] border border-[#1c2a44] rounded px-2.5 py-1 text-white text-xs"
                      >
                        <option value="open">Open</option>
                        <option value="in_progress">In Progress</option>
                        <option value="escalated_sar">Escalated (SAR Prep)</option>
                        <option value="closed_confirmed_mule">Closed — Confirmed Mule Lead</option>
                        <option value="closed_legitimate">Closed — Legitimate Activity (FP)</option>
                      </select>
                    </div>
                    <textarea
                      rows={2}
                      value={findingsText}
                      onChange={(e) => setFindingsText(e.target.value)}
                      placeholder="Executive findings summary..."
                      className="w-full bg-[#0b1324] border border-[#1c2a44] rounded p-2 text-xs text-slate-100"
                    />
                    <button
                      type="submit"
                      className="w-full py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs flex items-center justify-center gap-1.5"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" /> Save Case Status & Findings
                    </button>
                  </form>
                </div>
              </div>

              {/* Middle Row: Notes + Evidence + Model Explanation & Linked Alerts */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 text-xs">
                {/* Investigation Notes */}
                <div className="lg:col-span-4 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3">
                  <div className="font-semibold text-white flex items-center gap-1.5">
                    <MessageSquarePlus className="w-4 h-4 text-sky-400" />
                    Investigation Notes ({detail.notes?.length || 0})
                  </div>
                  <form onSubmit={handleAddNote} className="space-y-2">
                    <textarea
                      rows={2}
                      value={noteContent}
                      onChange={(e) => setNoteContent(e.target.value)}
                      placeholder="Log investigative observation, counterparty check, or KYC finding..."
                      className="w-full bg-[#060b16] border border-[#1c2a44] rounded p-2 text-slate-100"
                    />
                    <button
                      type="submit"
                      className="w-full py-1.5 rounded bg-sky-600 hover:bg-sky-500 text-white font-medium"
                    >
                      Add Analyst Note
                    </button>
                  </form>
                  <div className="space-y-2 max-h-56 overflow-y-auto">
                    {(detail.notes || []).map((n: any) => (
                      <div
                        key={n.id}
                        className="p-2.5 rounded bg-[#060b16] border border-[#16223b] space-y-1"
                      >
                        <div className="flex items-center justify-between text-[10px] text-slate-400">
                          <span className="font-semibold text-sky-300">{n.author}</span>
                          <span className="font-mono">{n.created_at.slice(0, 16).replace("T", " ")}</span>
                        </div>
                        <p className="text-slate-200 leading-relaxed">{n.content}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Evidence Items */}
                <div className="lg:col-span-4 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3">
                  <div className="font-semibold text-white flex items-center gap-1.5">
                    <FilePlus2 className="w-4 h-4 text-emerald-400" />
                    Evidence & Findings ({detail.evidence?.length || 0})
                  </div>
                  <form onSubmit={handleAddEvidence} className="space-y-2">
                    <div className="grid grid-cols-2 gap-2">
                      <select
                        value={evidenceType}
                        onChange={(e) => setEvidenceType(e.target.value)}
                        className="bg-[#060b16] border border-[#1c2a44] rounded px-2 py-1 text-slate-200"
                      >
                        <option value="transaction_chain">Transaction Chain</option>
                        <option value="counterparty_cluster">Counterparty Cluster</option>
                        <option value="velocity_anomaly">Velocity Anomaly</option>
                        <option value="shap_explanation">SHAP Attribution</option>
                      </select>
                      <input
                        type="text"
                        value={evidenceRef}
                        onChange={(e) => setEvidenceRef(e.target.value)}
                        placeholder="Ref TX/Acc ID..."
                        className="bg-[#060b16] border border-[#1c2a44] rounded px-2 py-1 font-mono text-white"
                      />
                    </div>
                    <input
                      type="text"
                      value={evidenceTitle}
                      onChange={(e) => setEvidenceTitle(e.target.value)}
                      placeholder="Evidence title (e.g. Rapid 45-min wire forwarding)..."
                      className="w-full bg-[#060b16] border border-[#1c2a44] rounded px-2.5 py-1.5 text-white"
                    />
                    <button
                      type="submit"
                      className="w-full py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium"
                    >
                      Attach Evidence Record
                    </button>
                  </form>
                  <div className="space-y-2 max-h-56 overflow-y-auto">
                    {(detail.evidence || []).map((ev: any) => (
                      <div
                        key={ev.id}
                        className="p-2.5 rounded bg-[#060b16] border border-[#16223b] space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-emerald-300">{ev.title}</span>
                          <span className="font-mono text-[10px] text-slate-400">
                            {ev.reference_id}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-300">{ev.description}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Model Risk Factors & Linked Alerts */}
                <div className="lg:col-span-4 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3">
                  <div className="font-semibold text-white flex items-center gap-1.5">
                    <ShieldAlert className="w-4 h-4 text-amber-400" />
                    Model Attribution & Linked Alerts
                  </div>
                  <div className="space-y-1.5">
                    {(accCtx.risk_profile.top_factors || []).slice(0, 5).map((f: any) => (
                      <div
                        key={f.feature}
                        className="p-2 rounded bg-[#060b16] border border-[#16223b] flex items-center justify-between"
                      >
                        <div>
                          <div className="text-slate-200 font-medium">{f.display_name}</div>
                          <div className="text-[10px] text-slate-400 font-mono">
                            Value: {f.feature_value}
                          </div>
                        </div>
                        <span className="font-mono text-red-300 font-semibold">
                          {f.shap_value >= 0 ? `+${f.shap_value.toFixed(2)}` : f.shap_value.toFixed(2)}
                        </span>
                      </div>
                    ))}
                  </div>

                  <div className="pt-2 border-t border-[#1c2a44] space-y-1.5">
                    <div className="text-[11px] font-semibold text-slate-300">
                      Linked Alerts ({accCtx.alerts?.length || 0})
                    </div>
                    {(accCtx.alerts || []).map((a: any) => (
                      <div
                        key={a.alert_id}
                        className="p-2 rounded bg-[#060b16] border border-[#16223b] flex items-center justify-between"
                      >
                        <span className="font-mono text-sky-300">{a.alert_id}</span>
                        <span className="text-[10px] uppercase font-mono text-amber-300">
                          {a.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Bottom Row: Account Transaction History & Case Audit History */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 text-xs">
                <div className="lg:col-span-7 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-2.5">
                  <div className="font-semibold text-white">
                    Recent Account Transactions ({accountTxs.length})
                  </div>
                  <div className="overflow-x-auto max-h-56">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="text-[10px] uppercase text-slate-400 border-b border-[#1c2a44]">
                          <th className="py-2">TX ID</th>
                          <th className="py-2">Sender → Receiver</th>
                          <th className="py-2">Amount</th>
                          <th className="py-2">Channel</th>
                          <th className="py-2">Timestamp</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#152036]">
                        {accountTxs.slice(0, 10).map((tx) => (
                          <tr key={tx.transaction_id}>
                            <td className="py-1.5 font-mono text-sky-300">{tx.transaction_id}</td>
                            <td className="py-1.5 font-mono text-slate-300">
                              {tx.sender_account_id} → {tx.receiver_account_id}
                            </td>
                            <td className="py-1.5 font-mono font-bold text-white">
                              ${Number(tx.amount).toLocaleString()}
                            </td>
                            <td className="py-1.5 font-mono text-slate-400">{tx.channel}</td>
                            <td className="py-1.5 font-mono text-slate-500">
                              {tx.timestamp.slice(0, 16).replace("T", " ")}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="lg:col-span-5 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-2.5">
                  <div className="font-semibold text-white flex items-center gap-1.5">
                    <Clock className="w-4 h-4 text-sky-400" />
                    Case Audit Trail ({detail.audit_trail?.length || 0})
                  </div>
                  <div className="space-y-1.5 max-h-56 overflow-y-auto">
                    {(detail.audit_trail || []).map((ev: any) => (
                      <div
                        key={ev.id}
                        className="p-2 rounded bg-[#060b16] border border-[#16223b] space-y-0.5"
                      >
                        <div className="flex items-center justify-between text-[10px] text-slate-400">
                          <span className="font-mono text-sky-300">{ev.event_type}</span>
                          <span className="font-mono">
                            {ev.timestamp.slice(0, 16).replace("T", " ")}
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-200">{ev.action_summary}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

