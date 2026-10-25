import React, { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  Shield,
  LayoutDashboard,
  Globe2,
  ArrowLeftRight,
  AlertOctagon,
  Share2,
  FolderSearch,
  BrainCircuit,
  BarChart3,
  Sliders,
  Newspaper,
  FileCheck2,
  Settings,
  Search,
  ChevronLeft,
  ChevronRight,
  Database,
  Cpu,
  CheckCircle2,
} from "lucide-react";
import { api } from "../services/api";

const NAV_ITEMS = [
  { to: "/", label: "Overview", icon: LayoutDashboard, badge: null },
  { to: "/map", label: "Global Activity Map", icon: Globe2, badge: "SYN" },
  { to: "/transactions", label: "Transaction Monitor", icon: ArrowLeftRight, badge: null },
  { to: "/flagged-accounts", label: "Flagged Accounts", icon: AlertOctagon, badge: null },
  { to: "/network", label: "Network Intelligence", icon: Share2, badge: "GRAPH" },
  { to: "/investigations", label: "Investigation Workspace", icon: FolderSearch, badge: null },
  { to: "/explainable-ai", label: "Explainable AI (SHAP)", icon: BrainCircuit, badge: "XAI" },
  { to: "/risk-analytics", label: "Risk Analytics", icon: BarChart3, badge: null },
  { to: "/what-if", label: "What-If Analysis Lab", icon: Sliders, badge: "LAB" },
  { to: "/context", label: "Financial & Event Context", icon: Newspaper, badge: null },
  { to: "/audit-trail", label: "Audit Trail & Governance", icon: FileCheck2, badge: null },
  { to: "/settings", label: "Settings & Model Ops", icon: Settings, badge: null },
];

export const CommandCenterLayout: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [collapsed, setCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [dbHealth, setDbHealth] = useState<any>(null);
  const [appHealth, setAppHealth] = useState<any>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const [h, db] = await Promise.all([api.getHealth(), api.getDbHealth()]);
        setAppHealth(h);
        setDbHealth(db);
      } catch {
        // ignore transient error
      }
    };
    fetchStatus();
    const timer = setInterval(fetchStatus, 15000);
    return () => clearInterval(timer);
  }, []);

  const handleGlobalSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const q = searchQuery.trim();
    if (!q) return;
    if (q.toUpperCase().startsWith("TX-")) {
      navigate(`/transactions?search=${encodeURIComponent(q)}`);
    } else if (q.toUpperCase().startsWith("INV-")) {
      navigate(`/investigations?id=${encodeURIComponent(q)}`);
    } else {
      navigate(`/flagged-accounts?search=${encodeURIComponent(q)}`);
    }
  };

  return (
    <div className="min-h-screen flex bg-[#060b16] text-slate-100">
      {/* Collapsible Sidebar */}
      <aside
        className={`${
          collapsed ? "w-16" : "w-64"
        } transition-all duration-200 flex flex-col bg-[#091122] border-r border-[#1c2a44] shrink-0 select-none`}
      >
        <div className="h-14 px-4 flex items-center justify-between border-b border-[#1c2a44]">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/20 shrink-0">
              <Shield className="w-5 h-5 text-slate-950 stroke-[2.4]" />
            </div>
            {!collapsed && (
              <div>
                <div className="font-bold text-sm tracking-tight text-white flex items-center gap-1.5">
                  FlyGuard <span className="text-sky-400">AI</span>
                </div>
                <div className="text-[10px] text-slate-400 uppercase tracking-wider">
                  FIU Command Center
                </div>
              </div>
            )}
          </div>
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white"
            title={collapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        <nav className="flex-1 py-3 px-2 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium transition-colors ${
                    isActive
                      ? "bg-blue-600/20 text-sky-300 border border-blue-500/40 shadow-sm"
                      : "text-slate-400 hover:bg-[#101c35] hover:text-slate-200 border border-transparent"
                  }`
                }
                title={item.label}
              >
                <div className="flex items-center gap-2.5 truncate">
                  <Icon className="w-4 h-4 shrink-0" />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </div>
                {!collapsed && item.badge && (
                  <span className="px-1.5 py-0.2 text-[9px] font-mono rounded bg-slate-800 text-sky-400 border border-slate-700">
                    {item.badge}
                  </span>
                )}
              </NavLink>
            );
          })}
        </nav>

        {!collapsed && (
          <div className="p-3 m-2 rounded-lg bg-[#0d172e] border border-[#1c2a44] text-[11px] text-slate-400 space-y-1">
            <div className="text-slate-200 font-semibold flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              Decision-Support Notice
            </div>
            <p className="leading-relaxed text-[10px] text-slate-400">
              All data is synthetic. Model risk scores are investigative triage leads, not proof of criminal conduct.
            </p>
          </div>
        )}
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Bar */}
        <header className="h-14 px-6 bg-[#091122]/90 backdrop-blur border-b border-[#1c2a44] flex items-center justify-between gap-4 sticky top-0 z-30">
          <form onSubmit={handleGlobalSearch} className="flex-1 max-w-md relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search account ID (e.g. AC-100120), transaction (TX-...), or region..."
              className="w-full bg-[#060b16] border border-[#1c2a44] focus:border-sky-500 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 outline-none"
            />
          </form>

          <div className="flex items-center gap-4 text-xs">
            <div className="hidden md:flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="font-medium">System Online</span>
            </div>

            {appHealth?.active_model_version && (
              <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-blue-500/10 border border-blue-500/30 text-sky-300 font-mono text-[11px]">
                <Cpu className="w-3.5 h-3.5" />
                <span>Model: {appHealth.active_model_version}</span>
              </div>
            )}

            <div className="flex items-center gap-2 pl-2 border-l border-[#1c2a44]">
              <div className="w-7 h-7 rounded-full bg-blue-600/30 border border-blue-500/50 flex items-center justify-center text-xs font-bold text-sky-300">
                SC
              </div>
              <div className="hidden sm:block leading-tight">
                <div className="text-xs font-medium text-slate-200">Sarah Chen</div>
                <div className="text-[10px] text-slate-400">Lead FIU Analyst</div>
              </div>
            </div>
          </div>
        </header>

        {/* Page Body */}
        <main className="flex-1 p-5 overflow-y-auto">{children}</main>

        {/* Bottom Telemetry Status Bar */}
        <footer className="h-9 px-6 bg-[#080f1e] border-t border-[#1c2a44] flex items-center justify-between text-[11px] text-slate-400">
          <div className="flex items-center gap-5 overflow-x-auto">
            <span className="flex items-center gap-1.5 text-slate-300 font-medium">
              <Database className="w-3.5 h-3.5 text-sky-400" />
              DB: {dbHealth?.engine || "SQLite"}
            </span>
            <span>
              Monitored Accounts:{" "}
              <strong className="text-slate-200 font-mono">
                {dbHealth ? dbHealth.accounts_count.toLocaleString() : "—"}
              </strong>
            </span>
            <span>
              Transactions Processed:{" "}
              <strong className="text-slate-200 font-mono">
                {dbHealth ? dbHealth.transactions_count.toLocaleString() : "—"}
              </strong>
            </span>
            <span>
              High/Critical Accounts:{" "}
              <strong className="text-red-400 font-mono">
                {dbHealth ? dbHealth.flagged_accounts_count.toLocaleString() : "—"}
              </strong>
            </span>
            <span>
              Open Alerts:{" "}
              <strong className="text-amber-400 font-mono">
                {dbHealth ? dbHealth.open_alerts_count.toLocaleString() : "—"}
              </strong>
            </span>
          </div>
          <div className="hidden md:flex items-center gap-2 font-mono text-[10px] text-slate-500">
            <span>SYNTHETIC FINANCIAL INTELLIGENCE ENVIRONMENT</span>
          </div>
        </footer>
      </div>
    </div>
  );
};

