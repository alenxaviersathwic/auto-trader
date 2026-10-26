import React, { useState } from "react";
import {
  useImportUnderlyings,
  useResearchConfig,
  useRiskTerms,
  useSources,
  useTestSource,
  useToggleUnderlyingEnabled,
  useUnderlyings,
  useUpdateResearchConfig,
} from "../hooks/useResearch";
import {
  Settings,
  ArrowLeft,
  Layers,
  Globe,
  AlertTriangle,
  Sliders,
  Upload,
  CheckCircle,
  XCircle,
} from "lucide-react";
import { useNavigate } from "@tanstack/react-router";
import { ResearchConfig, UnderlyingType } from "../types/research.types";

export type SettingsTab = "underlyings" | "sources" | "riskTerms" | "parameters" | "health";

export const ResearchSettingsPage: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<SettingsTab>("underlyings");

  // Tab 1: Underlyings
  const [underlyingTypeFilter, setUnderlyingTypeFilter] = useState<UnderlyingType | "ALL">("ALL");
  const { data: underlyingsData, refetch: refetchUnderlyings } = useUnderlyings({
    underlyingType: underlyingTypeFilter === "ALL" ? undefined : underlyingTypeFilter,
    page: 0,
    limit: 50,
  });
  const { mutate: toggleUnderlyingEnabled } = useToggleUnderlyingEnabled();
  const { mutate: importUnderlyings, isPending: importing } = useImportUnderlyings();

  // Tab 2: Sources
  const { data: sourcesData } = useSources({ page: 0, limit: 30 });
  const { mutate: testSource, isPending: testingSource } = useTestSource();
  const [testResult, setTestResult] = useState<any>(null);

  // Tab 3: Risk Terms
  const { data: riskTermsData } = useRiskTerms({ page: 0, limit: 50 });

  // Tab 4: Parameters Config
  const { data: configData, refetch: refetchConfig } = useResearchConfig();
  const { mutate: updateConfig, isPending: updatingConfig } = useUpdateResearchConfig();
  const [configDraft, setConfigDraft] = useState<Partial<ResearchConfig> | null>(null);

  React.useEffect(() => {
    if (configData && !configDraft) {
      setConfigDraft(configData);
    }
  }, [configData]);

  // CSV Import handler
  const handleCsvUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("dryRun", "false");

    importUnderlyings(formData, {
      onSuccess: (res) => {
        alert(`Successfully imported ${res.importedCount} underlyings into universe!`);
        refetchUnderlyings();
      },
      onError: (err: any) => {
        alert(`CSV import error: ${err.message || "Failed to parse"}`);
      },
    });
  };

  const handleTestSource = (id: number) => {
    setTestResult(null);
    testSource(id, {
      onSuccess: (res) => {
        setTestResult(res);
      },
      onError: (err: any) => {
        setTestResult({ success: false, error: err.message || "Test failed" });
      },
    });
  };

  const handleSaveConfig = (e: React.FormEvent) => {
    e.preventDefault();
    if (!configDraft) return;

    updateConfig(configDraft, {
      onSuccess: () => {
        alert("Configuration updated successfully to new version!");
        refetchConfig();
      },
      onError: (err: any) => {
        alert(`Failed to update config: ${err.message || "Error"}`);
      },
    });
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#232b3b]">
        <div>
          <button
            onClick={() => navigate({ to: "/research" as any })}
            className="flex items-center gap-1.5 text-xs text-sky-400 hover:text-sky-300 font-medium mb-1 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Research Engine
          </button>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
              <Settings className="w-5 h-5" />
            </div>
            <h1 className="text-xl font-bold text-slate-100">Research Engine Configuration</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Universe underlyings, feed registries, risk term taxonomy, and scoring threshold parameters
          </p>
        </div>

        {/* Tab navigation */}
        <div className="flex items-center bg-[#111520] p-1 rounded-2xl border border-[#232b3b]">
          {[
            { id: "underlyings", label: "Underlyings", icon: Layers },
            { id: "sources", label: "Sources", icon: Globe },
            { id: "riskTerms", label: "Risk Terms", icon: AlertTriangle },
            { id: "parameters", label: "Parameters", icon: Sliders },
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as SettingsTab)}
                className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                  activeTab === tab.id
                    ? "bg-[#232b3b] text-slate-100 shadow-md"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* SUB-TAB 1: UNDERLYINGS */}
      {activeTab === "underlyings" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#161b26] p-4 rounded-2xl border border-[#232b3b]">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Filter Type:</span>
              <div className="flex gap-1 bg-[#111520] p-1 rounded-xl border border-[#232b3b] text-xs">
                {(["ALL", "INDEX", "COMMODITY", "STOCK"] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setUnderlyingTypeFilter(t)}
                    className={`px-2.5 py-0.5 rounded-lg font-medium transition-colors ${
                      underlyingTypeFilter === t
                        ? "bg-[#232b3b] text-slate-100"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            {/* CSV Import */}
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-[#111520] hover:bg-[#1c2230] text-sky-400 border border-[#232b3b] cursor-pointer transition-colors">
                <Upload className="w-3.5 h-3.5" />
                <span>{importing ? "Importing..." : "Import Stocks CSV"}</span>
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleCsvUpload}
                  disabled={importing}
                  className="hidden"
                />
              </label>
            </div>
          </div>

          {/* Underlyings Table */}
          <div className="bg-[#161b26] border border-[#232b3b] rounded-2xl overflow-hidden shadow-xl">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#111520] border-b border-[#232b3b] text-slate-400 uppercase tracking-wider text-[11px]">
                  <th className="py-3 px-4 font-semibold">Code</th>
                  <th className="py-3 px-4 font-semibold">Name</th>
                  <th className="py-3 px-4 font-semibold">Type</th>
                  <th className="py-3 px-4 font-semibold">Group</th>
                  <th className="py-3 px-4 font-semibold">Exchange</th>
                  <th className="py-3 px-4 font-semibold">Aliases</th>
                  <th className="py-3 px-4 font-semibold text-right">Enabled</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#232b3b]">
                {underlyingsData?.list.map((u) => (
                  <tr key={u.id} className="hover:bg-[#1c2230]/50 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-slate-100">{u.code}</td>
                    <td className="py-3 px-4 text-slate-300">{u.name}</td>
                    <td className="py-3 px-4">
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#111520] text-slate-400 border border-[#232b3b]">
                        {u.underlyingType}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-400">{u.groupName}</td>
                    <td className="py-3 px-4 font-mono text-slate-400">{u.exchange}</td>
                    <td className="py-3 px-4 text-slate-400 text-[11px]">
                      {u.aliases?.join(", ") || "—"}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <input
                        type="checkbox"
                        checked={u.enabled}
                        onChange={(e) =>
                          toggleUnderlyingEnabled({ id: u.id, enabled: e.target.checked })
                        }
                        className="rounded border-[#232b3b] text-emerald-500 focus:ring-0 bg-[#0e1117] cursor-pointer"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* SUB-TAB 2: SOURCES */}
      {activeTab === "sources" && (
        <div className="space-y-4">
          {testResult && (
            <div
              className={`p-4 rounded-2xl border text-xs flex items-start gap-3 ${
                testResult.success
                  ? "bg-emerald-950/20 border-emerald-800/40 text-emerald-300"
                  : "bg-rose-950/20 border-rose-800/40 text-rose-300"
              }`}
            >
              {testResult.success ? (
                <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              ) : (
                <XCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              )}
              <div className="space-y-1">
                <div className="font-semibold">
                  Source Test: {testResult.name} — {testResult.success ? "Success" : "Failed"}
                </div>
                {testResult.success ? (
                  <div>
                    Items fetched: {testResult.itemCount} · Newest:{" "}
                    {testResult.newestItemDate ? new Date(testResult.newestItemDate).toLocaleString() : "None"}
                  </div>
                ) : (
                  <div>Error: {testResult.error}</div>
                )}
              </div>
            </div>
          )}

          <div className="bg-[#161b26] border border-[#232b3b] rounded-2xl overflow-hidden shadow-xl">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#111520] border-b border-[#232b3b] text-slate-400 uppercase tracking-wider text-[11px]">
                  <th className="py-3 px-4 font-semibold">Source</th>
                  <th className="py-3 px-4 font-semibold">Type</th>
                  <th className="py-3 px-4 font-semibold">Credibility</th>
                  <th className="py-3 px-4 font-semibold">Feed / URL</th>
                  <th className="py-3 px-4 font-semibold">Status (OK / Fail)</th>
                  <th className="py-3 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#232b3b]">
                {sourcesData?.list.map((s) => (
                  <tr key={s.id} className="hover:bg-[#1c2230]/50 transition-colors">
                    <td className="py-3 px-4 font-semibold text-slate-100">{s.name}</td>
                    <td className="py-3 px-4">
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#111520] text-sky-400 border border-sky-500/20">
                        {s.sourceType}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-emerald-400 font-semibold">
                      {(s.credibilityWeight * 100).toFixed(0)}%
                    </td>
                    <td className="py-3 px-4 text-slate-400 font-mono text-[11px] max-w-xs truncate">
                      {s.feedUrl || s.baseUrl}
                    </td>
                    <td className="py-3 px-4 text-slate-400 text-[11px]">
                      <span className="text-emerald-400">{s.okCount} OK</span> /{" "}
                      <span className="text-rose-400">{s.failCount} Fail</span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => handleTestSource(s.id)}
                        disabled={testingSource}
                        className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-[#111520] text-sky-400 border border-[#232b3b] hover:border-sky-500/40 transition-colors"
                      >
                        Test Feed
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* SUB-TAB 3: RISK TERMS */}
      {activeTab === "riskTerms" && (
        <div className="bg-[#161b26] border border-[#232b3b] rounded-2xl overflow-hidden shadow-xl">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-[#111520] border-b border-[#232b3b] text-slate-400 uppercase tracking-wider text-[11px]">
                <th className="py-3 px-4 font-semibold">Risk Term</th>
                <th className="py-3 px-4 font-semibold">Category</th>
                <th className="py-3 px-4 font-semibold">Severity (1-5)</th>
                <th className="py-3 px-4 font-semibold">Applies To</th>
                <th className="py-3 px-4 font-semibold text-right">Enabled</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#232b3b]">
              {riskTermsData?.list.map((r) => (
                <tr key={r.id} className="hover:bg-[#1c2230]/50 transition-colors">
                  <td className="py-3 px-4 font-mono font-bold text-rose-300">{r.term}</td>
                  <td className="py-3 px-4 text-slate-300">{r.category}</td>
                  <td className="py-3 px-4 font-mono text-amber-400 font-bold">{r.defaultSeverity}</td>
                  <td className="py-3 px-4 text-slate-400 text-[11px]">
                    {r.appliesToTypes?.join(", ")}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <input
                      type="checkbox"
                      checked={r.enabled}
                      readOnly
                      className="rounded border-[#232b3b] text-emerald-500 bg-[#0e1117]"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* SUB-TAB 4: PARAMETERS */}
      {activeTab === "parameters" && configDraft && (
        <form onSubmit={handleSaveConfig} className="space-y-6">
          <div className="p-3.5 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>
              All threshold and scoring weights are starting values in research_config and can be tuned safely.
              Saving creates a new version and preserves previous configurations.
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Freshness & Thresholds */}
            <div className="p-5 rounded-2xl bg-[#161b26] border border-[#232b3b] space-y-4">
              <h3 className="text-sm font-semibold text-slate-100 pb-2 border-b border-[#232b3b]">
                Freshness & Source Rules
              </h3>

              <div>
                <label className="block text-xs text-slate-300 mb-1">
                  Freshness Window: {configDraft.thresholds?.windowHours ?? 24} hours
                </label>
                <input
                  type="range"
                  min="6"
                  max="48"
                  value={configDraft.thresholds?.windowHours ?? 24}
                  onChange={(e) =>
                    setConfigDraft((prev) => ({
                      ...prev,
                      thresholds: { ...prev?.thresholds, windowHours: Number(e.target.value) },
                    }))
                  }
                  className="w-full accent-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs text-slate-300 mb-1">
                  Recency Half-Life: {configDraft.thresholds?.halfLifeHours ?? 12} hours
                </label>
                <input
                  type="range"
                  min="4"
                  max="24"
                  value={configDraft.thresholds?.halfLifeHours ?? 12}
                  onChange={(e) =>
                    setConfigDraft((prev) => ({
                      ...prev,
                      thresholds: { ...prev?.thresholds, halfLifeHours: Number(e.target.value) },
                    }))
                  }
                  className="w-full accent-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs text-slate-300 mb-1">
                  Minimum Independent Sources
                </label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={configDraft.thresholds?.minSources ?? 3}
                  onChange={(e) =>
                    setConfigDraft((prev) => ({
                      ...prev,
                      thresholds: { ...prev?.thresholds, minSources: Number(e.target.value) },
                    }))
                  }
                  className="w-full px-3 py-1.5 rounded-xl bg-[#0e1117] border border-[#232b3b] text-xs text-slate-200"
                />
              </div>
            </div>

            {/* Negative Clearance Rules */}
            <div className="p-5 rounded-2xl bg-[#161b26] border border-[#232b3b] space-y-4">
              <h3 className="text-sm font-semibold text-slate-100 pb-2 border-b border-[#232b3b]">
                Negative News Clearance
              </h3>

              <div>
                <label className="block text-xs text-slate-300 mb-1">
                  Material Negative Magnitude Min: {configDraft.thresholds?.negMagnitudeMin ?? 3}
                </label>
                <input
                  type="range"
                  min="1"
                  max="5"
                  value={configDraft.thresholds?.negMagnitudeMin ?? 3}
                  onChange={(e) =>
                    setConfigDraft((prev) => ({
                      ...prev,
                      thresholds: { ...prev?.thresholds, negMagnitudeMin: Number(e.target.value) },
                    }))
                  }
                  className="w-full accent-rose-500"
                />
              </div>

              <div>
                <label className="block text-xs text-slate-300 mb-1">
                  Negative Share Limit (Clearance Threshold)
                </label>
                <input
                  type="number"
                  step="0.05"
                  min="0.1"
                  max="0.5"
                  value={configDraft.thresholds?.negShareLimit ?? 0.25}
                  onChange={(e) =>
                    setConfigDraft((prev) => ({
                      ...prev,
                      thresholds: { ...prev?.thresholds, negShareLimit: Number(e.target.value) },
                    }))
                  }
                  className="w-full px-3 py-1.5 rounded-xl bg-[#0e1117] border border-[#232b3b] text-xs text-slate-200"
                />
              </div>

              <div className="flex items-center justify-between pt-2">
                <span className="text-xs text-slate-300">Veto on Scheduled Event Risk:</span>
                <input
                  type="checkbox"
                  checked={configDraft.thresholds?.vetoOnEventRisk ?? false}
                  onChange={(e) =>
                    setConfigDraft((prev) => ({
                      ...prev,
                      thresholds: { ...prev?.thresholds, vetoOnEventRisk: e.target.checked },
                    }))
                  }
                  className="rounded border-[#232b3b] text-emerald-500 bg-[#0e1117] cursor-pointer"
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-[#232b3b]">
            <button
              type="submit"
              disabled={updatingConfig}
              className="px-6 py-2 rounded-xl text-xs font-semibold bg-emerald-500 hover:bg-emerald-400 text-black shadow-lg shadow-emerald-500/20 disabled:opacity-50"
            >
              {updatingConfig ? "Saving..." : "Save New Configuration Version"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
};
