import React, { useEffect, useState } from "react";
import { Newspaper, Info, ShieldCheck, BookOpen } from "lucide-react";
import { api } from "../services/api";
import { RiskBadge } from "../components/RiskBadge";

export const FinancialContextPage: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getFinancialContext()
      .then((res) => setData(res))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="p-10 text-center text-xs text-slate-400">
        Loading Regulatory & Financial Crime Typology Context...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Newspaper className="w-5 h-5 text-sky-400" />
            Financial & Regulatory Typology Context
          </h1>
          <p className="text-xs text-slate-400">
            Modular reference library mapping FATF, FinCEN, and EBA money-mule advisories to model features
          </p>
        </div>
      </div>

      {/* Honest Offline Status Banner */}
      <div className="p-3.5 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-start gap-3 text-xs text-sky-200">
        <Info className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
        <div>
          <div className="font-semibold text-white">
            Offline Reference Mode (No External Live API Configured)
          </div>
          <p className="text-slate-300 mt-0.5">
            {data?.honest_status_banner}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(data?.typology_advisories || []).map((adv: any) => (
          <div
            key={adv.id}
            className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3 text-xs"
          >
            <div className="flex items-center justify-between">
              <span className="px-2 py-0.5 rounded bg-slate-800 text-sky-300 font-mono text-[10px]">
                {adv.id} • {adv.category}
              </span>
              <RiskBadge category={adv.severity} />
            </div>

            <div>
              <h2 className="text-sm font-bold text-white">{adv.title}</h2>
              <div className="text-[11px] text-slate-400 flex items-center gap-1 mt-0.5">
                <BookOpen className="w-3 h-3" /> Source Authority: {adv.authority}
              </div>
            </div>

            <p className="text-slate-300 leading-relaxed">{adv.summary}</p>

            <div className="space-y-1">
              <div className="text-[10px] uppercase font-mono text-slate-400">
                Corroborating Model Features:
              </div>
              <div className="flex flex-wrap gap-1.5">
                {(adv.corroborating_features || []).map((f: string) => (
                  <span
                    key={f}
                    className="px-2 py-0.5 rounded bg-[#060b16] border border-[#16223b] font-mono text-[11px] text-sky-300"
                  >
                    {f}
                  </span>
                ))}
              </div>
            </div>

            <div className="p-2.5 rounded bg-emerald-950/20 border border-emerald-500/30 text-[11px] text-emerald-200 flex items-start gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <strong>False-Positive Mitigation Guidance:</strong> {adv.false_positive_guidance}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

