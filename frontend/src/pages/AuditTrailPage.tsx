import React, { useEffect, useState } from "react";
import { FileCheck2, Search, Download } from "lucide-react";
import { api } from "../services/api";

export const AuditTrailPage: React.FC = () => {
  const [events, setEvents] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [eventType, setEventType] = useState("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchAudit = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (eventType !== "all") params.event_type = eventType;
      if (search.trim()) params.search = search.trim();
      const res = await api.getAuditTrail(params);
      setEvents(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAudit();
  }, [eventType]);

  const handleExportJson = () => {
    const blob = new Blob([JSON.stringify(events, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `flyguard_audit_trail_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <FileCheck2 className="w-5 h-5 text-sky-400" />
            Audit Trail & Model Governance Ledger
          </h1>
          <p className="text-xs text-slate-400">
            Immutable operational log of dataset generation, model training, threshold updates, and investigation actions
          </p>
        </div>

        <button
          onClick={handleExportJson}
          className="px-3 py-1.5 rounded-lg bg-[#0b1324] hover:bg-[#13203d] border border-[#1c2a44] text-xs font-medium text-sky-300 flex items-center gap-1.5"
        >
          <Download className="w-3.5 h-3.5" /> Export Audit JSON ({total})
        </button>
      </div>

      {/* Filter Bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          fetchAudit();
        }}
        className="p-3.5 rounded-xl bg-[#0b1324] border border-[#1c2a44] flex flex-wrap items-center justify-between gap-3 text-xs"
      >
        <div className="flex items-center gap-2 flex-1 max-w-md">
          <div className="relative flex-1">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search actor, target ID, or action summary..."
              className="w-full bg-[#060b16] border border-[#1c2a44] rounded-lg pl-8 pr-3 py-1.5 text-slate-100"
            />
          </div>
          <button
            type="submit"
            className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium"
          >
            Search
          </button>
        </div>

        <select
          value={eventType}
          onChange={(e) => setEventType(e.target.value)}
          className="bg-[#060b16] border border-[#1c2a44] rounded-lg px-3 py-1.5 text-slate-200"
        >
          <option value="all">All Event Types</option>
          <option value="dataset_generation">Dataset Generation</option>
          <option value="model_training">Model Training</option>
          <option value="model_activation">Model Activation</option>
          <option value="threshold_update">Threshold Update</option>
          <option value="investigation_created">Investigation Created</option>
          <option value="investigation_status_change">Investigation Status Change</option>
          <option value="investigation_note_added">Investigation Note Added</option>
          <option value="evidence_added">Evidence Added</option>
          <option value="alert_decision">Alert Decision</option>
          <option value="what_if_simulation">What-If Simulation</option>
        </select>
      </form>

      {/* Audit Table */}
      <div className="rounded-xl bg-[#0b1324] border border-[#1c2a44] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-[#080f1e] text-slate-400 border-b border-[#1c2a44] uppercase text-[10px] tracking-wider">
                <th className="py-3 px-4">Timestamp (UTC)</th>
                <th className="py-3 px-4">Event Type</th>
                <th className="py-3 px-4">Actor</th>
                <th className="py-3 px-4">Target</th>
                <th className="py-3 px-4">Action Summary</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#152036]">
              {loading ? (
                <tr>
                  <td colSpan={5} className="py-10 text-center text-slate-400">
                    Loading governance events...
                  </td>
                </tr>
              ) : events.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-10 text-center text-slate-400">
                    No audit records found.
                  </td>
                </tr>
              ) : (
                events.map((ev) => (
                  <tr key={ev.id} className="hover:bg-[#101c35]">
                    <td className="py-2.5 px-4 font-mono text-slate-400 whitespace-nowrap">
                      {ev.timestamp.replace("T", " ").slice(0, 19)}
                    </td>
                    <td className="py-2.5 px-4">
                      <span className="px-2 py-0.5 rounded bg-blue-500/15 text-sky-300 border border-blue-500/30 font-mono text-[11px]">
                        {ev.event_type}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 font-medium text-slate-200">{ev.actor}</td>
                    <td className="py-2.5 px-4 font-mono text-slate-300">
                      {ev.target_type}: {ev.target_id}
                    </td>
                    <td className="py-2.5 px-4 text-slate-200">{ev.action_summary}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

