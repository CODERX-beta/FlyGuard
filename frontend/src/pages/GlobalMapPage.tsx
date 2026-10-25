import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import L from "leaflet";
import { AlertTriangle, Filter, Globe2, Share2 } from "lucide-react";
import { api } from "../services/api";
import { RiskBadge } from "../components/RiskBadge";

export const GlobalMapPage: React.FC = () => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const layerGroupRef = useRef<L.LayerGroup | null>(null);

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [minAmount, setMinAmount] = useState(1000);
  const [riskFilter, setRiskFilter] = useState("all");
  const [days, setDays] = useState(90);
  const [selectedCorridor, setSelectedCorridor] = useState<any>(null);
  const navigate = useNavigate();

  const fetchMapData = async () => {
    setLoading(true);
    try {
      const res = await api.getGlobalMap({
        min_amount: minAmount,
        risk_filter: riskFilter,
        days,
      });
      setData(res);
      if (res.corridors?.length > 0) {
        setSelectedCorridor(res.corridors[0]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMapData();
  }, [minAmount, riskFilter, days]);

  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;
    const map = L.map(mapContainerRef.current, {
      center: [24, 15],
      zoom: 2,
      minZoom: 2,
      maxZoom: 8,
      worldCopyJump: true,
    });

    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: "&copy; OpenStreetMap &copy; CARTO (Synthetic Overlay)",
      subdomains: "abcd",
    }).addTo(map);

    layerGroupRef.current = L.layerGroup().addTo(map);
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  useEffect(() => {
    const group = layerGroupRef.current;
    if (!group || !data) return;
    group.clearLayers();

    // Draw cross-region corridors
    (data.corridors || []).forEach((c: any) => {
      const isCritical = c.max_risk_score >= 85;
      const isHigh = c.max_risk_score >= 65;
      const color = isCritical ? "#ef4444" : isHigh ? "#f97316" : "#38bdf8";

      const line = L.polyline(
        [
          [c.source_lat, c.source_lng],
          [c.target_lat, c.target_lng],
        ],
        {
          color,
          weight: Math.min(5, Math.max(1.5, Math.log10(c.total_volume || 100))),
          opacity: 0.65,
          dashArray: isHigh ? "6, 4" : undefined,
        }
      );
      line.on("click", () => setSelectedCorridor(c));
      line.bindTooltip(
        `<div style="font-size:11px"><strong>${c.corridor_id}</strong><br/>Volume: $${Number(
          c.total_volume
        ).toLocaleString()}<br/>Max Risk Score: ${c.max_risk_score}/100</div>`
      );
      line.addTo(group);
    });

    // Draw regional hubs
    (data.hubs || []).forEach((h: any) => {
      const isHigh = h.flagged_accounts > 20;
      const circle = L.circleMarker([h.lat, h.lng], {
        radius: Math.min(18, Math.max(7, Math.sqrt(h.flagged_accounts + 4) * 1.4)),
        fillColor: isHigh ? "#ef4444" : "#38bdf8",
        color: "#ffffff",
        weight: 1.2,
        fillOpacity: 0.8,
      });
      circle.bindPopup(
        `<div style="color:#0f172a;font-size:12px">
          <strong>${h.region} (Synthetic Hub)</strong><br/>
          Monitored Accounts: ${h.total_accounts.toLocaleString()}<br/>
          High/Critical Accounts: <b>${h.flagged_accounts}</b><br/>
          Avg Risk Score: ${h.avg_risk_score}
        </div>`
      );
      circle.addTo(group);
    });
  }, [data]);

  return (
    <div className="space-y-4">
      {/* Synthetic Geographic Data Honesty Banner */}
      <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/40 flex items-center justify-between gap-3 text-xs text-amber-200">
        <div className="flex items-center gap-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>
            <strong>SIMULATED GEOGRAPHIC OVERLAY:</strong>{" "}
            {data?.synthetic_disclaimer ||
              "Locations represent regional hub tags assigned by the synthetic data generator. Exact street/GPS coordinates are never fabricated."}
          </span>
        </div>
        <span className="px-2 py-0.5 rounded bg-amber-500/20 border border-amber-400/40 font-mono text-[10px] shrink-0">
          SYNTHETIC HUBS ONLY
        </span>
      </div>

      {/* Filter Bar */}
      <div className="p-3.5 rounded-xl bg-[#0b1324] border border-[#1c2a44] flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Globe2 className="w-4 h-4 text-sky-400" />
          <h1 className="text-sm font-bold text-white">
            Global Synthetic Corridor & Regional Activity Monitor
          </h1>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400">Time Window:</span>
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="bg-[#060b16] border border-[#1c2a44] rounded px-2 py-1 text-slate-200"
            >
              <option value={14}>Last 14 Days</option>
              <option value={30}>Last 30 Days</option>
              <option value={90}>Full 90-Day Window</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-slate-400">Min Transfer:</span>
            <select
              value={minAmount}
              onChange={(e) => setMinAmount(Number(e.target.value))}
              className="bg-[#060b16] border border-[#1c2a44] rounded px-2 py-1 text-slate-200"
            >
              <option value={0}>All Amounts</option>
              <option value={1000}>$1,000+</option>
              <option value={5000}>$5,000+</option>
              <option value={10000}>$10,000+</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-slate-400">Corridor Risk:</span>
            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="bg-[#060b16] border border-[#1c2a44] rounded px-2 py-1 text-slate-200"
            >
              <option value="all">All Risk Levels</option>
              <option value="high_only">High & Critical (65+)</option>
              <option value="critical_only">Critical Only (85+)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Map + Corridor Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-8 rounded-xl overflow-hidden border border-[#1c2a44] bg-[#070e1c] relative h-[520px]">
          <div ref={mapContainerRef} className="w-full h-full z-10" />
          {loading && (
            <div className="absolute inset-0 bg-slate-950/60 z-20 flex items-center justify-center text-xs text-sky-300">
              Updating synthetic regional corridors...
            </div>
          )}
        </div>

        <div className="lg:col-span-4 flex flex-col gap-4">
          {selectedCorridor && (
            <div className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-sky-400 uppercase tracking-wider">
                  Selected Corridor Lead
                </span>
                <RiskBadge
                  category={
                    selectedCorridor.max_risk_score >= 85
                      ? "Critical"
                      : selectedCorridor.max_risk_score >= 65
                      ? "High"
                      : "Moderate"
                  }
                  score={selectedCorridor.max_risk_score}
                />
              </div>
              <div className="text-sm font-bold text-white">{selectedCorridor.corridor_id}</div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="p-2 rounded bg-[#060b16] border border-[#16223b]">
                  <div className="text-slate-400 text-[10px]">Sample Volume</div>
                  <div className="font-mono font-bold text-white">
                    ${Number(selectedCorridor.total_volume).toLocaleString()}
                  </div>
                </div>
                <div className="p-2 rounded bg-[#060b16] border border-[#16223b]">
                  <div className="text-slate-400 text-[10px]">Sample Transfers</div>
                  <div className="font-mono font-bold text-white">
                    {selectedCorridor.transaction_count}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 pt-1">
                <button
                  onClick={() => navigate(`/network?account=${selectedCorridor.sample_sender}`)}
                  className="flex-1 py-1.5 px-3 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium flex items-center justify-center gap-1.5"
                >
                  <Share2 className="w-3.5 h-3.5" />
                  Inspect Sender ({selectedCorridor.sample_sender})
                </button>
              </div>
            </div>
          )}

          <div className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] flex-1 overflow-y-auto max-h-[320px] space-y-2.5">
            <h2 className="text-xs font-semibold text-white uppercase tracking-wider">
              Top Cross-Region Transfer Corridors
            </h2>
            {(data?.corridors || []).slice(0, 10).map((c: any) => (
              <div
                key={c.corridor_id}
                onClick={() => setSelectedCorridor(c)}
                className={`p-2.5 rounded-lg border cursor-pointer transition-colors ${
                  selectedCorridor?.corridor_id === c.corridor_id
                    ? "bg-blue-950/40 border-blue-500/50"
                    : "bg-[#060b16] border-[#16223b] hover:bg-[#0f1a30]"
                }`}
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-slate-200">{c.corridor_id}</span>
                  <span className="font-mono text-sky-400">
                    ${Number(c.total_volume).toLocaleString()}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1">
                  <span>{c.transaction_count} high-value transfers</span>
                  <span>Max Score: {c.max_risk_score}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

