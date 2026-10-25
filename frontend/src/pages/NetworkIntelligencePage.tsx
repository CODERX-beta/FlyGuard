import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import cytoscape, { Core } from "cytoscape";
import {
  Share2,
  ZoomIn,
  ZoomOut,
  Maximize2,
  RotateCcw,
  Route,
  FolderPlus,
  Layers,
  AlertTriangle,
  ArrowRight,
  GitBranch,
  Users,
} from "lucide-react";
import { api } from "../services/api";
import { EgoNetworkResponse, GraphNodeData, TracePathResponse } from "../types/api";
import { RiskBadge } from "../components/RiskBadge";

export const NetworkIntelligencePage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const cyContainerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);

  const [centerAccountId, setCenterAccountId] = useState<string>(
    searchParams.get("account") || ""
  );
  const [accountInput, setAccountInput] = useState<string>(
    searchParams.get("account") || ""
  );
  const [flaggedOptions, setFlaggedOptions] = useState<any[]>([]);
  const [hops, setHops] = useState<number>(1);
  const [direction, setDirection] = useState<string>("all");
  const [minAmount, setMinAmount] = useState<number>(0);
  const [minRiskScore, setMinRiskScore] = useState<number>(0);
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [highlightSuspicious, setHighlightSuspicious] = useState<boolean>(true);

  const [networkData, setNetworkData] = useState<EgoNetworkResponse | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNodeData | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Path tracer state
  const [traceSource, setTraceSource] = useState<string>("");
  const [traceTarget, setTraceTarget] = useState<string>("");
  const [traceResult, setTraceResult] = useState<TracePathResponse | null>(null);
  const [tracing, setTracing] = useState<boolean>(false);

  // Load top flagged accounts for quick switching if no account query param provided
  useEffect(() => {
    const initDefaultAccount = async () => {
      try {
        const res = await api.getAccounts({
          flagged_only: true,
          page: 1,
          page_size: 25,
          sort_by: "risk_score",
          sort_dir: "desc",
        });
        const list = res.items || [];
        setFlaggedOptions(list);
        if (!centerAccountId && list.length > 0) {
          const firstId = list[0].account_id;
          setCenterAccountId(firstId);
          setAccountInput(firstId);
          setTraceSource(firstId);
        }
      } catch (err) {
        console.error(err);
      }
    };
    initDefaultAccount();
  }, []);

  const loadGraph = async (targetAccId: string) => {
    if (!targetAccId) return;
    setLoading(true);
    setError(null);
    try {
      const res: EgoNetworkResponse = await api.getAccountGraph(targetAccId, {
        hops,
        direction,
        min_amount: minAmount > 0 ? minAmount : undefined,
        min_risk_score: minRiskScore > 0 ? minRiskScore : undefined,
        start_date: startDate ? `${startDate}T00:00:00` : undefined,
        end_date: endDate ? `${endDate}T23:59:59` : undefined,
      });
      setNetworkData(res);
      const centerNode =
        res.nodes.find((n) => n.account_id === targetAccId) || res.nodes[0] || null;
      setSelectedNode(centerNode);
      setSelectedEdge(null);
      setTraceSource(targetAccId);
      if (res.nodes.length > 1 && !traceTarget) {
        const second = res.nodes.find((n) => n.account_id !== targetAccId);
        if (second) setTraceTarget(second.account_id);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load account relationship network");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (centerAccountId) {
      loadGraph(centerAccountId);
    }
  }, [centerAccountId, hops, direction, minAmount, minRiskScore, startDate, endDate]);

  // Render Cytoscape graph whenever networkData or highlightSuspicious changes
  useEffect(() => {
    if (!cyContainerRef.current || !networkData) return;

    const elements: any[] = [];

    networkData.nodes.forEach((n) => {
      const color =
        n.risk_category === "Critical"
          ? "#ef4444"
          : n.risk_category === "High"
          ? "#f97316"
          : n.risk_category === "Moderate"
          ? "#f59e0b"
          : "#10b981";

      const size = n.is_center
        ? 48
        : Math.min(40, Math.max(24, 20 + Math.sqrt(n.risk_score || 10) * 1.6));

      elements.push({
        group: "nodes",
        data: {
          id: n.account_id,
          label: `${n.account_id}\n(${Math.round(n.risk_score)})`,
          color,
          size,
          borderColor: n.is_center
            ? "#38bdf8"
            : highlightSuspicious && n.in_suspicious_path
            ? "#f43f5e"
            : "#1e293b",
          borderWidth: n.is_center ? 4 : highlightSuspicious && n.in_suspicious_path ? 3 : 1.5,
          raw: n,
        },
      });
    });

    networkData.edges.forEach((e) => {
      const isSusp = highlightSuspicious && e.is_suspicious;
      elements.push({
        group: "edges",
        data: {
          id: e.edge_id,
          source: e.source,
          target: e.target,
          label: `$${Math.round(e.total_amount).toLocaleString()} (${e.transaction_count}x)`,
          lineColor: isSusp ? "#f43f5e" : "#334155",
          width: Math.min(5, Math.max(1.4, Math.log10(e.total_amount + 10))),
          raw: e,
        },
      });
    });

    if (cyRef.current) {
      cyRef.current.destroy();
    }

    const cy = cytoscape({
      container: cyContainerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            width: "data(size)",
            height: "data(size)",
            label: "data(label)",
            color: "#f8fafc",
            "font-size": 9,
            "text-wrap": "wrap",
            "text-valign": "bottom",
            "text-margin-y": 5,
            "border-width": "data(borderWidth)",
            "border-color": "data(borderColor)",
            "font-family": "monospace",
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 4,
            "border-color": "#38bdf8",
            "overlay-color": "#38bdf8",
            "overlay-opacity": 0.15,
          },
        },
        {
          selector: "edge",
          style: {
            width: "data(width)",
            "line-color": "data(lineColor)",
            "target-arrow-color": "data(lineColor)",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": 8,
            color: "#94a3b8",
            "text-background-color": "#060b16",
            "text-background-opacity": 0.85,
            "text-background-padding": "2px",
          },
        },
        {
          selector: "edge.traced-hop",
          style: {
            width: 4,
            "line-color": "#38bdf8",
            "target-arrow-color": "#38bdf8",
          },
        },
      ],
      layout: {
        name: networkData.nodes.length <= 28 ? "concentric" : "cose",
        animate: false,
        padding: 36,
        concentric: (node: any) => (node.data("raw")?.is_center ? 10 : 1),
        levelWidth: () => 2,
      } as any,
    });

    cy.on("tap", "node", (evt) => {
      const nodeData = evt.target.data("raw") as GraphNodeData;
      setSelectedNode(nodeData);
      setSelectedEdge(null);
      setTraceTarget(nodeData.account_id);
    });

    cy.on("tap", "edge", (evt) => {
      const edgeData = evt.target.data("raw");
      setSelectedEdge(edgeData);
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [networkData, highlightSuspicious]);

  const handleTracePath = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!traceSource || !traceTarget) return;
    setTracing(true);
    try {
      const res = await api.traceGraphPath({
        source_account_id: traceSource,
        target_account_id: traceTarget,
        max_hops: 4,
      });
      setTraceResult(res);
      if (res.found && cyRef.current && res.node_ids) {
        cyRef.current.edges().removeClass("traced-hop");
        for (let i = 0; i < res.node_ids.length - 1; i++) {
          const u = res.node_ids[i];
          const v = res.node_ids[i + 1];
          cyRef.current
            .edges(`[source = "${u}"][target = "${v}"], [source = "${v}"][target = "${u}"]`)
            .addClass("traced-hop");
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setTracing(false);
    }
  };

  const handleStartInvestigation = async (accId: string) => {
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
      {/* Header & Account Selector */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Share2 className="w-5 h-5 text-sky-400" />
            Account Network Intelligence —{" "}
            <span className="font-mono text-sky-300">{centerAccountId || "Select Account"}</span>
          </h1>
          <p className="text-xs text-slate-400">
            Interactive Cytoscape.js directed transaction topology, multi-hop neighbor expansion, and path tracing
          </p>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (accountInput.trim()) {
              setCenterAccountId(accountInput.trim());
              setSearchParams({ account: accountInput.trim() });
            }
          }}
          className="flex flex-wrap items-center gap-2 text-xs"
        >
          <select
            value={centerAccountId}
            onChange={(e) => {
              setCenterAccountId(e.target.value);
              setAccountInput(e.target.value);
              setSearchParams({ account: e.target.value });
            }}
            className="bg-[#0b1324] border border-[#1c2a44] rounded-lg px-2.5 py-1.5 text-slate-200 font-mono"
          >
            {flaggedOptions.map((opt) => (
              <option key={opt.account_id} value={opt.account_id}>
                {opt.account_id} — {opt.risk_category} ({Math.round(opt.risk_score)})
              </option>
            ))}
          </select>

          <input
            type="text"
            value={accountInput}
            onChange={(e) => setAccountInput(e.target.value)}
            placeholder="Jump to Account ID..."
            className="bg-[#0b1324] border border-[#1c2a44] rounded-lg px-3 py-1.5 text-slate-100 font-mono w-40"
          />
          <button
            type="submit"
            className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium"
          >
            Load Graph
          </button>
        </form>
      </div>

      {/* Interactive Graph Filter & Hop Expansion Toolbar */}
      <div className="p-3 rounded-xl bg-[#0b1324] border border-[#1c2a44] flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-3">
          {/* Expand / Collapse Hops */}
          <div className="flex items-center gap-1 bg-[#060b16] p-1 rounded-lg border border-[#1c2a44]">
            <span className="px-2 text-slate-400 flex items-center gap-1">
              <Layers className="w-3.5 h-3.5 text-sky-400" /> Depth:
            </span>
            {[1, 2, 3].map((h) => (
              <button
                key={h}
                onClick={() => setHops(h)}
                className={`px-2.5 py-1 rounded font-medium ${
                  hops === h
                    ? "bg-blue-600 text-white"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {h} {h === 1 ? "Hop (Direct)" : "Hops"}
              </button>
            ))}
          </div>

          {/* Direction Filter */}
          <select
            value={direction}
            onChange={(e) => setDirection(e.target.value)}
            className="bg-[#060b16] border border-[#1c2a44] rounded-lg px-2.5 py-1.5 text-slate-200"
          >
            <option value="all">Direction: All Transfers</option>
            <option value="incoming">Incoming Only (Senders)</option>
            <option value="outgoing">Outgoing Only (Destinations)</option>
          </select>

          {/* Min Edge Amount */}
          <select
            value={minAmount}
            onChange={(e) => setMinAmount(Number(e.target.value))}
            className="bg-[#060b16] border border-[#1c2a44] rounded-lg px-2.5 py-1.5 text-slate-200"
          >
            <option value={0}>Min Edge Amount: All</option>
            <option value={500}>Min $500+</option>
            <option value={2000}>Min $2,000+</option>
            <option value={5000}>Min $5,000+</option>
          </select>

          {/* Min Node Risk */}
          <select
            value={minRiskScore}
            onChange={(e) => setMinRiskScore(Number(e.target.value))}
            className="bg-[#060b16] border border-[#1c2a44] rounded-lg px-2.5 py-1.5 text-slate-200"
          >
            <option value={0}>Node Risk: All</option>
            <option value={35}>Moderate+ (35+)</option>
            <option value={65}>High+ (65+)</option>
          </select>

          {/* Date Range Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400">From:</span>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="bg-[#060b16] border border-[#1c2a44] rounded px-2 py-1 text-slate-200"
            />
            <span className="text-slate-400">To:</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="bg-[#060b16] border border-[#1c2a44] rounded px-2 py-1 text-slate-200"
            />
          </div>

          <label className="flex items-center gap-1.5 cursor-pointer text-slate-300">
            <input
              type="checkbox"
              checked={highlightSuspicious}
              onChange={(e) => setHighlightSuspicious(e.target.checked)}
              className="rounded border-slate-600"
            />
            <span>Highlight Suspicious Corridors</span>
          </label>
        </div>

        {/* Zoom / Fit / Reset Controls */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 1.25)}
            className="p-1.5 rounded bg-[#060b16] hover:bg-slate-800 border border-[#1c2a44] text-slate-300"
            title="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 0.8)}
            className="p-1.5 rounded bg-[#060b16] hover:bg-slate-800 border border-[#1c2a44] text-slate-300"
            title="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={() => cyRef.current?.fit(undefined, 36)}
            className="p-1.5 rounded bg-[#060b16] hover:bg-slate-800 border border-[#1c2a44] text-slate-300"
            title="Fit to Screen"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => {
              setHops(1);
              setDirection("all");
              setMinAmount(0);
              setMinRiskScore(0);
              setStartDate("");
              setEndDate("");
              setTraceResult(null);
            }}
            className="px-2.5 py-1.5 rounded bg-[#060b16] hover:bg-slate-800 border border-[#1c2a44] text-slate-300 flex items-center gap-1"
            title="Collapse Expanded Branches & Reset Filters"
          >
            <RotateCcw className="w-3.5 h-3.5" /> Reset 1-Hop
          </button>
        </div>
      </div>

      {/* Main Graph Canvas + Right Inspector Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-8 flex flex-col gap-4">
          <div className="rounded-xl bg-[#070d19] border border-[#1c2a44] relative h-[540px] overflow-hidden">
            <div ref={cyContainerRef} className="w-full h-full" />

            {loading && (
              <div className="absolute inset-0 bg-slate-950/70 flex items-center justify-center text-xs text-sky-300 z-20">
                Constructing directed Cytoscape.js relationship graph...
              </div>
            )}
            {error && (
              <div className="absolute inset-4 p-4 rounded-lg bg-red-950/80 border border-red-500/40 text-xs text-red-200 z-20">
                {error}
              </div>
            )}

            {/* Legend Overlay */}
            <div className="absolute bottom-3 left-3 px-3 py-2 rounded-lg bg-[#091122]/90 backdrop-blur border border-[#1c2a44] flex flex-wrap items-center gap-4 text-[11px] text-slate-300">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500" /> Critical (85+)
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-orange-500" /> High (65-85)
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500" /> Moderate (35-65)
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" /> Low (&lt;35)
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 bg-rose-500" /> Suspicious Flow
              </span>
            </div>

            {/* Subgraph Stats Overlay */}
            {networkData && (
              <div className="absolute top-3 left-3 px-3 py-1.5 rounded-lg bg-[#091122]/90 border border-[#1c2a44] flex items-center gap-4 text-[11px] text-slate-300 font-mono">
                <span>Nodes: {networkData.stats.node_count}</span>
                <span>Edges: {networkData.stats.edge_count}</span>
                <span>
                  Subgraph Flow: ${networkData.stats.total_subgraph_volume.toLocaleString()}
                </span>
                <span className="text-red-400">
                  High-Risk Nodes: {networkData.stats.high_risk_nodes}
                </span>
              </div>
            )}
          </div>

          {/* Bottom Panels under Graph: Suspicious Paths, Shared Counterparties, Clusters */}
          {networkData && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5 text-xs">
              {/* Suspicious Paths */}
              <div className="p-3.5 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-2">
                <div className="font-semibold text-white flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4 text-rose-400" />
                  Detected Suspicious Corridors ({networkData.suspicious_paths.length})
                </div>
                <div className="space-y-2 max-h-44 overflow-y-auto">
                  {networkData.suspicious_paths.length === 0 ? (
                    <div className="text-slate-500 text-[11px]">
                      No circular loops or high-symmetry pass-through corridors in current hop view.
                    </div>
                  ) : (
                    networkData.suspicious_paths.map((sp, i) => (
                      <div
                        key={i}
                        className="p-2 rounded bg-[#060b16] border border-rose-500/30 space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-rose-300 font-semibold text-[11px]">
                            {sp.pattern_type}
                          </span>
                          <span className="font-mono text-white">
                            ${sp.total_amount.toLocaleString()}
                          </span>
                        </div>
                        <div className="font-mono text-[10px] text-sky-300">
                          {sp.nodes.join(" → ")}
                        </div>
                        <p className="text-[10px] text-slate-400">{sp.explanation}</p>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Shared Counterparties */}
              <div className="p-3.5 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-2">
                <div className="font-semibold text-white flex items-center gap-1.5">
                  <Users className="w-4 h-4 text-sky-400" />
                  Shared Counterparties ({networkData.shared_counterparties.length})
                </div>
                <div className="space-y-1.5 max-h-44 overflow-y-auto">
                  {networkData.shared_counterparties.length === 0 ? (
                    <div className="text-slate-500 text-[11px]">
                      Expand to 2 hops to reveal shared intermediaries between neighbors.
                    </div>
                  ) : (
                    networkData.shared_counterparties.map((sc) => (
                      <div
                        key={sc.account_id}
                        onClick={() => {
                          setCenterAccountId(sc.account_id);
                          setAccountInput(sc.account_id);
                        }}
                        className="p-2 rounded bg-[#060b16] hover:bg-[#101c35] border border-[#16223b] cursor-pointer flex items-center justify-between"
                      >
                        <div>
                          <div className="font-mono font-bold text-slate-200">{sc.account_id}</div>
                          <div className="text-[10px] text-slate-400">
                            Links {sc.connected_count} subgraph accounts
                          </div>
                        </div>
                        <RiskBadge category={sc.risk_category} score={sc.risk_score} />
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Connected Component Clusters */}
              <div className="p-3.5 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-2">
                <div className="font-semibold text-white flex items-center gap-1.5">
                  <GitBranch className="w-4 h-4 text-emerald-400" />
                  Connected Components & Clusters ({networkData.clusters.length})
                </div>
                <div className="space-y-1.5 max-h-44 overflow-y-auto">
                  {networkData.clusters.map((cl) => (
                    <div
                      key={cl.cluster_id}
                      className="p-2 rounded bg-[#060b16] border border-[#16223b] space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-200">
                          Cluster #{cl.cluster_id} ({cl.node_count} nodes)
                        </span>
                        <span className="font-mono text-sky-400">
                          Avg Score: {cl.average_risk_score}
                        </span>
                      </div>
                      <div className="text-[10px] font-mono text-slate-400 truncate">
                        Members: {cl.sample_accounts.join(", ")}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Side Panel: Selected Node Details + Selected Edge + Path Tracer */}
        <div className="lg:col-span-4 space-y-4">
          {selectedNode && (
            <div className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3.5">
              <div className="flex items-start justify-between border-b border-[#1c2a44] pb-2.5">
                <div>
                  <span className="text-[10px] font-mono uppercase text-sky-400">
                    {selectedNode.is_center ? "Central Target Node" : `Hop ${selectedNode.hop_distance} Neighbor Node`}
                  </span>
                  <h2 className="text-lg font-bold font-mono text-white">
                    {selectedNode.account_id}
                  </h2>
                  <div className="text-xs text-slate-400">
                    {selectedNode.account_type || "individual"} •{" "}
                    {selectedNode.synthetic_region || "Global"}
                  </div>
                </div>
                <RiskBadge
                  category={selectedNode.risk_category}
                  score={selectedNode.risk_score}
                  size="lg"
                />
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b]">
                  <div className="text-[10px] text-slate-400">Total Incoming</div>
                  <div className="font-mono font-bold text-emerald-400">
                    ${selectedNode.incoming_volume.toLocaleString()} (
                    {selectedNode.incoming_tx_count})
                  </div>
                </div>
                <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b]">
                  <div className="text-[10px] text-slate-400">Total Outgoing</div>
                  <div className="font-mono font-bold text-amber-400">
                    ${selectedNode.outgoing_volume.toLocaleString()} (
                    {selectedNode.outgoing_tx_count})
                  </div>
                </div>
              </div>

              {selectedNode.explanation_summary && (
                <div className="p-2.5 rounded bg-[#060b16] border border-[#16223b] text-[11px] text-slate-300">
                  <strong className="text-white">Model Signal: </strong>
                  {selectedNode.explanation_summary}
                </div>
              )}

              <div className="grid grid-cols-2 gap-2 pt-1">
                <button
                  onClick={() => {
                    setCenterAccountId(selectedNode.account_id);
                    setAccountInput(selectedNode.account_id);
                    setHops(2);
                  }}
                  className="py-1.5 px-2.5 rounded-lg bg-[#101c35] hover:bg-[#162647] border border-sky-500/30 text-sky-300 text-xs font-medium"
                >
                  Pivot & Expand 2 Hops
                </button>
                <button
                  onClick={() => handleStartInvestigation(selectedNode.account_id)}
                  className="py-1.5 px-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium flex items-center justify-center gap-1"
                >
                  <FolderPlus className="w-3.5 h-3.5" />
                  Open Investigation
                </button>
              </div>
            </div>
          )}

          {/* Selected Edge Traceability Card */}
          {selectedEdge && (
            <div className="p-4 rounded-xl bg-[#0b1324] border border-sky-500/40 space-y-2 text-xs">
              <div className="font-semibold text-sky-300 uppercase text-[10px] font-mono">
                Selected Directed Edge Underlying Transactions
              </div>
              <div className="font-mono font-bold text-white flex items-center gap-1.5">
                {selectedEdge.source} <ArrowRight className="w-3.5 h-3.5 text-sky-400" />{" "}
                {selectedEdge.target}
              </div>
              <div className="flex items-center justify-between text-slate-300">
                <span>Aggregate Amount:</span>
                <strong className="font-mono text-white">
                  ${Number(selectedEdge.total_amount).toLocaleString()} (
                  {selectedEdge.transaction_count} transfers)
                </strong>
              </div>
              <div className="text-[11px] text-slate-400">
                Channels: {(selectedEdge.channels || []).join(", ")}
              </div>
              <div className="text-[10px] text-slate-400 font-mono">
                Traceable TX IDs: {(selectedEdge.transaction_ids || []).slice(0, 6).join(", ")}
              </div>
            </div>
          )}

          {/* Interactive Transaction Path Tracer */}
          <div className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3 text-xs">
            <div className="font-semibold text-white flex items-center gap-1.5">
              <Route className="w-4 h-4 text-sky-400" />
              Transaction Path Tracer
            </div>
            <form onSubmit={handleTracePath} className="space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Source Account</label>
                  <input
                    type="text"
                    value={traceSource}
                    onChange={(e) => setTraceSource(e.target.value)}
                    placeholder="AC-..."
                    className="w-full bg-[#060b16] border border-[#1c2a44] rounded px-2.5 py-1.5 font-mono text-white"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Target Account</label>
                  <input
                    type="text"
                    value={traceTarget}
                    onChange={(e) => setTraceTarget(e.target.value)}
                    placeholder="AC-..."
                    className="w-full bg-[#060b16] border border-[#1c2a44] rounded px-2.5 py-1.5 font-mono text-white"
                  />
                </div>
              </div>
              <button
                type="submit"
                disabled={tracing}
                className="w-full py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-medium"
              >
                {tracing ? "Tracing Hops..." : "Trace Transaction Path"}
              </button>
            </form>

            {traceResult && (
              <div className="pt-2 border-t border-[#1c2a44] space-y-2">
                {!traceResult.found ? (
                  <div className="text-amber-300 text-[11px]">
                    No connected path found within 4 hops between {traceResult.source_account_id}{" "}
                    and {traceResult.target_account_id}.
                  </div>
                ) : (
                  <>
                    <div className="flex items-center justify-between text-[11px] text-slate-300">
                      <span>
                        Hops: <strong>{traceResult.hops.length}</strong> ({traceResult.path_mode})
                      </span>
                      <span className="font-mono text-sky-300 font-bold">
                        Total: ${traceResult.total_amount.toLocaleString()}
                      </span>
                    </div>
                    <div className="space-y-1.5 max-h-48 overflow-y-auto">
                      {traceResult.hops.map((h) => (
                        <div
                          key={h.hop_index}
                          className="p-2 rounded bg-[#060b16] border border-[#16223b] space-y-0.5"
                        >
                          <div className="flex items-center justify-between font-mono text-[11px]">
                            <span className="text-sky-300">
                              #{h.hop_index}: {h.sender_account_id} → {h.receiver_account_id}
                            </span>
                            <span className="text-white font-bold">
                              ${h.total_amount.toLocaleString()}
                            </span>
                          </div>
                          <div className="text-[10px] text-slate-400 font-mono">
                            {h.transaction_count} tx ({h.channel}) • IDs:{" "}
                            {h.sample_transaction_ids.slice(0, 3).join(", ")}
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

