import React, { useEffect, useState } from "react";
import {
  Settings,
  Cpu,
  Database,
  Sliders,
  Play,
  CheckCircle2,
  RefreshCw,
} from "lucide-react";
import { api } from "../services/api";

export const SettingsModelOpsPage: React.FC = () => {
  const [modelsData, setModelsData] = useState<any>(null);
  const [dbHealth, setDbHealth] = useState<any>(null);
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusBanner, setStatusBanner] = useState<string | null>(null);

  // Threshold form
  const [moderateT, setModerateT] = useState(35);
  const [highT, setHighT] = useState(65);
  const [criticalT, setCriticalT] = useState(85);

  // Synthetic Generator Form
  const [genAccounts, setGenAccounts] = useState(2000);
  const [genTransactions, setGenTransactions] = useState(15000);
  const [genSeed, setGenSeed] = useState(42);
  const [genSuspRate, setGenSuspRate] = useState(0.06);

  // Model Training Form
  const [nEstimators, setNEstimators] = useState(140);
  const [maxDepth, setMaxDepth] = useState(5);
  const [learningRate, setLearningRate] = useState(0.07);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [m, db, j] = await Promise.all([
        api.getModels(),
        api.getDbHealth(),
        api.getJobs(),
      ]);
      setModelsData(m);
      setDbHealth(db);
      setJobs(j.items || []);
      if (m.thresholds) {
        setModerateT(m.thresholds.moderate);
        setHighT(m.thresholds.high);
        setCriticalT(m.thresholds.critical);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const handleUpdateThresholds = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.updateThresholds({
        moderate: moderateT,
        high: highT,
        critical: criticalT,
        updated_by: "Sarah Chen (AML Lead)",
      });
      setStatusBanner(
        `Updated risk thresholds (Moderate=${moderateT}, High=${highT}, Critical=${criticalT}) and re-scored accounts.`
      );
      await loadAll();
    } catch (err: any) {
      setStatusBanner(`Error: ${err.message}`);
    }
  };

  const handleTriggerGeneration = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api.generateSyntheticData(
        {
          num_accounts: genAccounts,
          num_transactions: genTransactions,
          random_seed: genSeed,
          suspicious_rate: genSuspRate,
          reset_existing: true,
          auto_train_and_score: true,
          actor: "ML Operations Lead",
        },
        true
      );
      setStatusBanner(`Started background job ${res.job.job_id}: ${res.job.description}`);
      await loadAll();
    } catch (err: any) {
      setStatusBanner(`Error: ${err.message}`);
    }
  };

  const handleTriggerTraining = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api.trainModel(
        {
          random_seed: genSeed,
          n_estimators: nEstimators,
          max_depth: maxDepth,
          learning_rate: learningRate,
          activate_if_passed: true,
          score_all_accounts: true,
          actor: "ML Operations Lead",
        },
        true
      );
      setStatusBanner(`Started background training job ${res.job.job_id}`);
      await loadAll();
    } catch (err: any) {
      setStatusBanner(`Error: ${err.message}`);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Settings className="w-5 h-5 text-sky-400" />
            Settings, Dataset Pipeline & Model Management
          </h1>
          <p className="text-xs text-slate-400">
            Configure risk thresholds, launch synthetic generation & XGBoost training jobs, and inspect model artifacts
          </p>
        </div>

        <button
          onClick={loadAll}
          className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium flex items-center gap-1.5"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Status
        </button>
      </div>

      {statusBanner && (
        <div className="p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/40 text-xs text-emerald-200 flex items-center justify-between">
          <span>{statusBanner}</span>
          <button onClick={() => setStatusBanner(null)} className="underline text-[11px]">
            Dismiss
          </button>
        </div>
      )}

      {/* Top Row: Configurable Thresholds + Synthetic Generator + Model Trainer */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 text-xs">
        {/* 1. Risk Thresholds */}
        <form
          onSubmit={handleUpdateThresholds}
          className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3"
        >
          <div className="font-semibold text-white flex items-center gap-1.5 text-sm">
            <Sliders className="w-4 h-4 text-sky-400" />
            Configurable Triage Thresholds (0–100)
          </div>
          <p className="text-[11px] text-slate-400">
            Adjust categorical cutoffs on the normalized 0–100 risk score and immediately re-classify accounts.
          </p>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-amber-300">Moderate Threshold:</label>
              <input
                type="number"
                value={moderateT}
                onChange={(e) => setModerateT(Number(e.target.value))}
                className="w-24 bg-[#060b16] border border-[#1c2a44] rounded px-2 py-1 font-mono text-white"
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="text-orange-300">High Risk Threshold (Alert Cutoff):</label>
              <input
                type="number"
                value={highT}
                onChange={(e) => setHighT(Number(e.target.value))}
                className="w-24 bg-[#060b16] border border-[#1c2a44] rounded px-2 py-1 font-mono text-white"
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="text-red-300">Critical Threshold:</label>
              <input
                type="number"
                value={criticalT}
                onChange={(e) => setCriticalT(Number(e.target.value))}
                className="w-24 bg-[#060b16] border border-[#1c2a44] rounded px-2 py-1 font-mono text-white"
              />
            </div>
          </div>
          <button
            type="submit"
            className="w-full py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold"
          >
            Save Thresholds & Re-Score
          </button>
        </form>

        {/* 2. Synthetic Data Generator Controls */}
        <form
          onSubmit={handleTriggerGeneration}
          className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3"
        >
          <div className="font-semibold text-white flex items-center gap-1.5 text-sm">
            <Database className="w-4 h-4 text-emerald-400" />
            Synthetic Dataset Generator
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-slate-300">Synthetic Accounts:</label>
              <input
                type="number"
                value={genAccounts}
                onChange={(e) => setGenAccounts(Number(e.target.value))}
                className="w-28 bg-[#060b16] border border-[#1c2a44] rounded px-2 py-1 font-mono text-white"
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="text-slate-300">Synthetic Transactions:</label>
              <input
                type="number"
                value={genTransactions}
                onChange={(e) => setGenTransactions(Number(e.target.value))}
                className="w-28 bg-[#060b16] border border-[#1c2a44] rounded px-2 py-1 font-mono text-white"
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="text-slate-300">Random Seed:</label>
              <input
                type="number"
                value={genSeed}
                onChange={(e) => setGenSeed(Number(e.target.value))}
                className="w-28 bg-[#060b16] border border-[#1c2a44] rounded px-2 py-1 font-mono text-white"
              />
            </div>
          </div>
          <button
            type="submit"
            className="w-full py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold flex items-center justify-center gap-1.5"
          >
            <Play className="w-3.5 h-3.5" /> Generate Dataset (Background Job)
          </button>
        </form>

        {/* 3. XGBoost Model Training Controls */}
        <form
          onSubmit={handleTriggerTraining}
          className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3"
        >
          <div className="font-semibold text-white flex items-center gap-1.5 text-sm">
            <Cpu className="w-4 h-4 text-purple-400" />
            Train New XGBoost Model Version
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-slate-300">n_estimators (Trees):</label>
              <input
                type="number"
                value={nEstimators}
                onChange={(e) => setNEstimators(Number(e.target.value))}
                className="w-24 bg-[#060b16] border border-[#1c2a44] rounded px-2 py-1 font-mono text-white"
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="text-slate-300">max_depth:</label>
              <input
                type="number"
                value={maxDepth}
                onChange={(e) => setMaxDepth(Number(e.target.value))}
                className="w-24 bg-[#060b16] border border-[#1c2a44] rounded px-2 py-1 font-mono text-white"
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="text-slate-300">learning_rate:</label>
              <input
                type="number"
                step="0.01"
                value={learningRate}
                onChange={(e) => setLearningRate(Number(e.target.value))}
                className="w-24 bg-[#060b16] border border-[#1c2a44] rounded px-2 py-1 font-mono text-white"
              />
            </div>
          </div>
          <button
            type="submit"
            className="w-full py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-semibold flex items-center justify-center gap-1.5"
          >
            <Play className="w-3.5 h-3.5" /> Train & Evaluate Model
          </button>
        </form>
      </div>

      {/* Model Versions Registry */}
      <div className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3 text-xs">
        <h2 className="text-sm font-semibold text-white">
          Trained Model Artifact Registry & Evaluation Gates
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="text-[10px] uppercase text-slate-400 border-b border-[#1c2a44]">
                <th className="py-2 px-3">Model Version</th>
                <th className="py-2 px-3">Dataset ID</th>
                <th className="py-2 px-3">Test ROC-AUC</th>
                <th className="py-2 px-3">Test PR-AUC</th>
                <th className="py-2 px-3">Test F1</th>
                <th className="py-2 px-3">Artifact Path</th>
                <th className="py-2 px-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#152036]">
              {(modelsData?.models || []).map((m: any) => (
                <tr key={m.model_version}>
                  <td className="py-2.5 px-3 font-mono font-bold text-sky-300">
                    {m.model_version}
                  </td>
                  <td className="py-2.5 px-3 font-mono text-slate-300">{m.dataset_id}</td>
                  <td className="py-2.5 px-3 font-mono text-emerald-400 font-bold">
                    {m.metrics?.roc_auc}
                  </td>
                  <td className="py-2.5 px-3 font-mono text-sky-400 font-bold">
                    {m.metrics?.pr_auc}
                  </td>
                  <td className="py-2.5 px-3 font-mono text-white font-bold">
                    {m.metrics?.f1_score}
                  </td>
                  <td className="py-2.5 px-3 font-mono text-[11px] text-slate-400 truncate max-w-xs">
                    {m.artifact_path}
                  </td>
                  <td className="py-2.5 px-3">
                    {m.is_active ? (
                      <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-mono text-[10px] inline-flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" /> ACTIVE
                      </span>
                    ) : (
                      <button
                        onClick={async () => {
                          await api.activateModel(m.model_version);
                          await loadAll();
                        }}
                        className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-sky-300 text-[11px]"
                      >
                        Activate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Feature Schema Documentation Table */}
      <div className="p-4 rounded-xl bg-[#0b1324] border border-[#1c2a44] space-y-3 text-xs">
        <h2 className="text-sm font-semibold text-white">
          Engineered Feature Schema & Limitations ({modelsData?.feature_schema?.length || 26} Features)
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5 max-h-80 overflow-y-auto">
          {(modelsData?.feature_schema || []).map((f: any) => (
            <div
              key={f.name}
              className="p-2.5 rounded bg-[#060b16] border border-[#16223b] space-y-1"
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-white">{f.display_name}</span>
                <span className="text-[10px] font-mono text-sky-400">{f.category}</span>
              </div>
              <div className="text-[10px] font-mono text-slate-400">{f.name}</div>
              <p className="text-[11px] text-slate-300">{f.description}</p>
              <p className="text-[10px] text-amber-300/80">Limitation: {f.limitations}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

