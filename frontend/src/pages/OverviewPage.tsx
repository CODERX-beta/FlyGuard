import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import {
  Users,
  ArrowLeftRight,
  AlertTriangle,
  Bell,
  FolderKanban,
  DollarSign,
  Share2,
  ExternalLink,
  RefreshCw,
} from "lucide-react";
import { api } from "../services/api";
import { RiskBadge } from "../components/RiskBadge";

const RISK_COLORS: Record<string, string> = {
  Critical: "#ef4444",
  High: "#f97316",
  Moderate: "#f59e0b",
  Low: "#10b981",
};

export const OverviewPage: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getOverview();
      setData(res);
    } catch (err: any) {
      setError(err.message || "Failed to load overview intelligence");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="p-12 text-center text-slate-400 text-sm flex flex-col items-center gap-3">
        <RefreshCw className="w-6 h-6 animate-spin text-sky-400" />
        <span>Loading Global Financial Intelligence Overview...</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-8 rounded-xl bg-red-950/30 border border-red-500/40 text-red-200 space-y-3">
        <div className="font-semibold text-sm">Failed to load overview telemetry</div>
        <div className="text-xs text-red-300">{error}</div>
        <button
          onClick={loadData}
          className="px-3 py-1.5 rounded bg-red-600 hover:bg-red-500 text-white text-xs font-medium"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  const kpis = data.kpis || {};
  const riskDist = data.risk_distribution || { Critical: 0, High: 0, Moderate: 0, Low: 0 };
  const pieData = [
    { name: "Critical", value: riskDist.Critical || 0 },
    { name: "High", value: riskDist.High || 0 },
    { name: "Moderate", value: riskDist.Moderate || 0 },
    { name: "Low", value: riskDist.Low || 0 },
  ];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">
            Global Financial Intelligence Overview
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time synthetic AML telemetry, mule network triage, and transaction velocity monitoring
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate("/map")}
            className="px-3 py-1.5 rounded-lg bg-[#0d182e] hover:bg-[#162647] border border-[#1c2a44] text-xs font-medium text-sky-300"
          >
            Open Activity Map
          </button>
          <button
            onClick={loadData}
            className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-medium text-white flex items-center gap-1.5"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {/* 6 KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3.5">
        <div className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44]">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Monitored Accounts</span>
            <Users className="w-4 h-4 text-sky-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2 font-mono">
            {(kpis.total_accounts || 0).toLocaleString()}
          </div>
          <div className="text-[11px] text-emerald-400 mt-1">100% synthetic entities</div>
        </div>

        <div className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44]">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Total Transactions</span>
            <ArrowLeftRight className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2 font-mono">
            {(kpis.total_transactions || 0).toLocaleString()}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">90-day analysis window</div>
        </div>

        <div className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44]">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Total Monitored Volume</span>
            <DollarSign className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2 font-mono">
            ${((kpis.total_volume || 0) / 1_000_000).toFixed(1)}M
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Aggregate USD flow</div>
        </div>

        <div
          onClick={() => navigate("/flagged-accounts?flagged_only=true")}
          className="p-4 rounded-xl bg-[#0b1324] border border-red-500/30 hover:border-red-500/60 cursor-pointer transition-colors"
        >
          <div className="flex items-center justify-between text-xs text-red-300">
            <span>High / Critical Accounts</span>
            <AlertTriangle className="w-4 h-4 text-red-400" />
          </div>
          <div className="text-2xl font-bold text-red-400 mt-2 font-mono">
            {(kpis.high_risk_accounts || 0).toLocaleString()}
          </div>
          <div className="text-[11px] text-red-300/80 mt-1">
            {kpis.critical_accounts || 0} Critical priority leads
          </div>
        </div>

        <div
          onClick={() => navigate("/flagged-accounts")}
          className="p-4 rounded-xl bg-[#0b1324] border border-amber-500/30 hover:border-amber-500/60 cursor-pointer transition-colors"
        >
          <div className="flex items-center justify-between text-xs text-amber-300">
            <span>Open Triage Alerts</span>
            <Bell className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400 mt-2 font-mono">
            {(kpis.open_alerts || 0).toLocaleString()}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Awaiting analyst review</div>
        </div>

        <div
          onClick={() => navigate("/investigations")}
          className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] hover:border-sky-500/50 cursor-pointer transition-colors"
        >
          <div className="flex items-center justify-between text-xs text-sky-300">
            <span>Active Investigations</span>
            <FolderKanban className="w-4 h-4 text-sky-400" />
          </div>
          <div className="text-2xl font-bold text-sky-400 mt-2 font-mono">
            {(kpis.active_investigations || 0).toLocaleString()}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Case workspaces open</div>
        </div>
      </div>

      {/* Middle Row: Volume Trends + Risk Distribution + Regional Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-6 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44]">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-sm font-semibold text-white">
                Transaction Volume Trend (14-Day Window)
              </h2>
              <p className="text-[11px] text-slate-400">
                Total daily USD flow vs volume involving High/Critical accounts
              </p>
            </div>
          </div>
          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.volume_trends || []}>
                <defs>
                  <linearGradient id="totVol" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#38bdf8" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="suspVol" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.45} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" stroke="#64748b" fontSize={10} tickFormatter={(v) => v.slice(5)} />
                <YAxis
                  stroke="#64748b"
                  fontSize={10}
                  tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#091122",
                    borderColor: "#1c2a44",
                    fontSize: "12px",
                  }}
                  formatter={(value: any) => [`$${Number(value).toLocaleString()}`, ""]}
                />
                <Area
                  type="monotone"
                  dataKey="total_volume"
                  name="Total Volume"
                  stroke="#38bdf8"
                  fillOpacity={1}
                  fill="url(#totVol)"
                />
                <Area
                  type="monotone"
                  dataKey="suspicious_volume"
                  name="High-Risk Corridor Volume"
                  stroke="#ef4444"
                  fillOpacity={1}
                  fill="url(#suspVol)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="lg:col-span-3 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] flex flex-col justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white">Account Risk Distribution</h2>
            <p className="text-[11px] text-slate-400">Calibrated XGBoost triage bands</p>
          </div>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={42}
                  outerRadius={68}
                  paddingAngle={2}
                >
                  {pieData.map((entry) => (
                    <Cell key={entry.name} fill={RISK_COLORS[entry.name] || "#38bdf8"} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#091122",
                    borderColor: "#1c2a44",
                    fontSize: "12px",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {pieData.map((item) => (
              <div
                key={item.name}
                className="flex items-center justify-between px-2 py-1 rounded bg-[#070d19] border border-[#152036]"
              >
                <span className="flex items-center gap-1.5">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: RISK_COLORS[item.name] }}
                  />
                  <span className="text-slate-300">{item.name}</span>
                </span>
                <span className="font-mono font-semibold text-white">
                  {item.value.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="lg:col-span-3 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] flex flex-col justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white">Top Synthetic Risk Regions</h2>
            <p className="text-[11px] text-slate-400">Simulated regional concentration</p>
          </div>
          <div className="space-y-2.5 my-2">
            {(data.regional_breakdown || []).map((reg: any) => (
              <div key={reg.region} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-200 font-medium truncate">{reg.region}</span>
                  <span className="font-mono text-slate-400">
                    {reg.flagged_count} ({reg.share_pct}%)
                  </span>
                </div>
                <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-blue-500 to-red-500"
                    style={{ width: `${Math.min(100, reg.share_pct * 2.5)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="text-[10px] text-slate-500 font-mono">
            * Simulated region tags from synthetic generator
          </div>
        </div>
      </div>

      {/* Bottom Row: Recent Alerts, High-Risk Network Hubs, Recent Investigations */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Recent Alerts */}
        <div className="lg:col-span-4 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white">Recent High-Priority Alerts</h2>
            <button
              onClick={() => navigate("/flagged-accounts")}
              className="text-xs text-sky-400 hover:underline"
            >
              View All
            </button>
          </div>
          <div className="space-y-2">
            {(data.recent_alerts || []).slice(0, 6).map((alt: any) => (
              <div
                key={alt.alert_id}
                onClick={() => navigate(`/network?account=${alt.account_id}`)}
                className="p-2.5 rounded-lg bg-[#070d19] hover:bg-[#0f1a30] border border-[#16223b] cursor-pointer transition-colors"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-sky-300">
                      {alt.account_id}
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono">{alt.alert_id}</span>
                  </div>
                  <RiskBadge category={alt.risk_category} score={alt.risk_score} />
                </div>
                <p className="text-[11px] text-slate-300 mt-1 line-clamp-1">
                  {alt.reason_summary}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* High-Risk Network Summaries */}
        <div className="lg:col-span-4 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white">High-Risk Network Hubs</h2>
            <button
              onClick={() => navigate("/network")}
              className="text-xs text-sky-400 hover:underline flex items-center gap-1"
            >
              <Share2 className="w-3 h-3" /> Graph Explorer
            </button>
          </div>
          <div className="space-y-2">
            {(data.high_risk_networks || []).map((hub: any) => (
              <div
                key={hub.hub_account_id}
                onClick={() => navigate(`/network?account=${hub.hub_account_id}`)}
                className="p-2.5 rounded-lg bg-[#070d19] hover:bg-[#0f1a30] border border-[#16223b] cursor-pointer transition-colors"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-white flex items-center gap-1.5">
                    {hub.hub_account_id}
                    <ExternalLink className="w-3 h-3 text-slate-400" />
                  </span>
                  <RiskBadge category={hub.risk_category} score={hub.risk_score} />
                </div>
                <div className="flex items-center justify-between text-[11px] text-slate-400 mt-1">
                  <span>{hub.unique_counterparties} counterparties</span>
                  <span className="font-mono text-slate-200">
                    ${Number(hub.total_turnover).toLocaleString()} turnover
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recently Investigated Accounts */}
        <div className="lg:col-span-4 p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white">Active Investigations</h2>
            <button
              onClick={() => navigate("/investigations")}
              className="text-xs text-sky-400 hover:underline"
            >
              Open Workspace
            </button>
          </div>
          <div className="space-y-2">
            {(data.recent_investigations || []).map((inv: any) => (
              <div
                key={inv.investigation_id}
                onClick={() => navigate(`/investigations?id=${inv.investigation_id}`)}
                className="p-2.5 rounded-lg bg-[#070d19] hover:bg-[#0f1a30] border border-[#16223b] cursor-pointer transition-colors"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-sky-300">
                    {inv.investigation_id} ({inv.account_id})
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-blue-500/15 text-blue-300 border border-blue-500/30">
                    {inv.status.replace("_", " ")}
                  </span>
                </div>
                <div className="text-[11px] text-slate-300 mt-1 truncate">{inv.title}</div>
                <div className="flex items-center justify-between text-[10px] text-slate-500 mt-1">
                  <span>Lead: {inv.assigned_to}</span>
                  <span>Score at open: {Math.round(inv.risk_score_at_open)}/100</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

