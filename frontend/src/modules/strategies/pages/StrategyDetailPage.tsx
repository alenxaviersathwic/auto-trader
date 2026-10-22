import React, { useState } from "react";
import { useParams, useNavigate } from "@tanstack/react-router";
import {
  ArrowLeft,
  Edit,
  Copy,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  BookOpen,
  Layers,
  Settings,
  Activity,
  History,
  Terminal,
  ListChecks,
  ExternalLink,
} from "lucide-react";
import {
  useCloneStrategy,
  useDeleteStrategy,
  useStrategyDetail,
  useUpdateStrategy,
  useUpdateStrategyEnabled,
  useUpdateStrategyLifecycle,
} from "../hooks/useStrategies";
import { DefinitionViewer } from "../components/DefinitionViewer";
import { PerformanceSection } from "../components/PerformanceSection";
import { HealthSection } from "../components/HealthSection";
import { VersionsSection } from "../components/VersionsSection";
import { RequirementsSection } from "../components/RequirementsSection";
import { StrategyTestPanel } from "../components/StrategyTestPanel";

export const StrategyDetailPage: React.FC = () => {
  const { id } = useParams({ strict: false }) as { id: string };
  const strategyId = Number(id);
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<
    | "overview"
    | "definition"
    | "parameters"
    | "performance"
    | "health"
    | "versions"
    | "requirements"
    | "test"
  >("overview");

  const { data: strategy, isLoading, refetch } = useStrategyDetail(strategyId);
  const updateLifecycleMutation = useUpdateStrategyLifecycle();
  const toggleEnabledMutation = useUpdateStrategyEnabled();
  const deleteMutation = useDeleteStrategy();
  const cloneMutation = useCloneStrategy();
  const updateStrategyMutation = useUpdateStrategy();

  // Parameter editing state
  const [paramsForm, setParamsForm] = useState<Record<string, any>>({});
  const [paramsInitialized, setParamsInitialized] = useState(false);

  if (isLoading) {
    return <div className="p-8 text-center text-muted">Loading strategy #{strategyId}...</div>;
  }

  if (!strategy) {
    return (
      <div className="p-8 text-center text-rose">
        <h2>Strategy #{strategyId} not found.</h2>
        <button
          type="button"
          className="btn-outline mt-4"
          onClick={() => navigate({ to: "/strategies" as any })}
        >
          Back to Strategies
        </button>
      </div>
    );
  }

  const currentVersion = strategy.currentVersion;
  const definition = currentVersion?.definition || {};
  const parameters = definition.parameters || {};

  if (!paramsInitialized && Object.keys(parameters).length > 0) {
    const initial: Record<string, any> = {};
    Object.entries(parameters).forEach(([k, v]: any) => {
      initial[k] = v?.default ?? v;
    });
    setParamsForm(initial);
    setParamsInitialized(true);
  }

  const handleLifecycleChange = (to: string) => {
    if (!strategy.executable && to === "ACTIVE") {
      alert("Cannot activate: Strategy has definition issues or missing handlers and is not executable.");
      return;
    }
    const reason = window.prompt(`Reason for transitioning lifecycle to ${to}:`, `Manual review change to ${to}`);
    if (reason) {
      updateLifecycleMutation.mutate({ id: strategyId, to, reason });
    }
  };

  const handleSaveParameters = () => {
    const updatedDef = {
      ...definition,
      parameters: {
        ...parameters,
      },
    };
    // Update defaults from form
    Object.entries(paramsForm).forEach(([k, v]) => {
      if (updatedDef.parameters[k]) {
        if (typeof updatedDef.parameters[k] === "object") {
          updatedDef.parameters[k].default = Number(v);
        } else {
          updatedDef.parameters[k] = Number(v);
        }
      }
    });

    updateStrategyMutation.mutate(
      {
        id: strategyId,
        payload: {
          definition: updatedDef,
          changeNote: "Updated strategy parameters",
        },
      },
      {
        onSuccess: () => {
          alert("Parameters updated. Created a new immutable version!");
          refetch();
        },
      }
    );
  };

  return (
    <div className="strategy-detail-page module-page">
      {/* Top Navigation Back */}
      <button
        type="button"
        className="btn-back flex items-center gap-1.5 text-xs text-muted hover:text-primary mb-3"
        onClick={() => navigate({ to: "/strategies" as any })}
      >
        <ArrowLeft size={14} />
        <span>Back to Strategies List</span>
      </button>

      {/* Header Card */}
      <div className="detail-header-card card-surface p-5 border border-subtle rounded-lg mb-4">
        <div className="flex flex-wrap justify-between items-start gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-xl font-bold text-primary">{strategy.name}</h1>
              <span className="font-mono text-xs text-cyan bg-cyan/10 px-2 py-0.5 rounded">
                {strategy.code}
              </span>
              <span className="badge-pill bg-elevated text-xs font-mono">
                v{currentVersion?.versionNo || 1}
              </span>
            </div>
            <p className="text-xs text-secondary max-w-3xl leading-relaxed">
              {strategy.description || "No description provided."}
            </p>

            {/* Chips bar */}
            <div className="flex flex-wrap items-center gap-2 mt-3">
              <span className="badge-pill bg-elevated font-mono text-xs">
                {strategy.structure || strategy.category}
              </span>
              <span className="badge-pill bg-elevated text-xs">
                {strategy.bias || "DYNAMIC"}
              </span>
              <span className="badge-pill bg-elevated text-xs">
                {strategy.markets?.join(", ")}
              </span>
              <span
                className={`badge-pill text-xs font-semibold ${
                  strategy.lifecycleStatus === "ACTIVE"
                    ? "bg-emerald/20 text-emerald"
                    : strategy.lifecycleStatus === "SUSPENDED"
                    ? "bg-rose/20 text-rose"
                    : "bg-surface text-muted"
                }`}
              >
                {strategy.lifecycleStatus}
              </span>
              <span
                className={`badge-pill text-xs font-bold ${
                  strategy.effectiveHealth === "HEALTHY"
                    ? "text-emerald"
                    : strategy.effectiveHealth === "DEGRADED"
                    ? "text-amber"
                    : "text-rose"
                }`}
              >
                Health: {strategy.effectiveHealth || strategy.health}
              </span>
              <span className="badge-pill text-xs bg-elevated text-secondary">
                {strategy.validationStatus}
              </span>
              {strategy.suggestable && (
                <span className="badge-pill bg-emerald/20 text-emerald text-xs flex items-center gap-1">
                  <CheckCircle2 size={12} />
                  Suggestable
                </span>
              )}
            </div>
          </div>

          {/* Action controls */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 pr-3 border-r border-subtle">
              <span className="text-xs text-muted">Enabled:</span>
              <label className="toggle-switch">
                <input
                  type="checkbox"
                  checked={strategy.enabled}
                  onChange={(e) =>
                    toggleEnabledMutation.mutate({
                      id: strategy.id,
                      enabled: e.target.checked,
                    })
                  }
                />
                <span className="slider round"></span>
              </label>
            </div>

            {/* Lifecycle Dropdown */}
            <select
              className="filter-select text-xs"
              value={strategy.lifecycleStatus}
              onChange={(e) => handleLifecycleChange(e.target.value)}
            >
              <option value="DRAFT">DRAFT</option>
              <option value="IN_REVIEW">IN_REVIEW</option>
              <option value="ACTIVE" disabled={!strategy.executable}>
                ACTIVE {!strategy.executable ? "(Blocked: Not Executable)" : ""}
              </option>
              <option value="SUSPENDED">SUSPENDED</option>
              <option value="ARCHIVED">ARCHIVED</option>
            </select>

            <button
              type="button"
              className="btn-outline text-xs flex items-center gap-1"
              onClick={() => navigate({ to: `/strategies/${strategy.id}/edit` as any })}
            >
              <Edit size={13} />
              <span>Edit</span>
            </button>
            <button
              type="button"
              className="btn-outline text-xs flex items-center gap-1"
              onClick={() =>
                cloneMutation.mutate(strategy.id, {
                  onSuccess: (c) => navigate({ to: `/strategies/${c.id}` as any }),
                })
              }
            >
              <Copy size={13} />
              <span>Clone</span>
            </button>
            <button
              type="button"
              className="btn-icon text-rose"
              onClick={() => {
                if (window.confirm("Soft delete this strategy?")) {
                  deleteMutation.mutate(strategy.id, {
                    onSuccess: () => navigate({ to: "/strategies" as any }),
                  });
                }
              }}
            >
              <Trash2 size={15} />
            </button>
          </div>
        </div>

        {/* Untested Notice Banner if UNTESTED */}
        {strategy.validationStatus === "UNTESTED" && (
          <div className="mt-3 p-2.5 bg-amber/10 border border-amber/30 rounded text-amber text-xs flex items-center gap-2">
            <AlertTriangle size={15} className="shrink-0" />
            <span>
              <strong>Untested Notice:</strong> No live validation yet. No win probability is shown. Historical numbers are from legacy import (domain unknown).
            </span>
          </div>
        )}
      </div>

      {/* Tabs Navigation */}
      <div className="tabs-header border-b border-subtle mb-4 flex gap-1">
        <button
          type="button"
          className={`tab-btn ${activeTab === "overview" ? "active" : ""}`}
          onClick={() => setActiveTab("overview")}
        >
          <BookOpen size={14} />
          <span>Overview</span>
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === "definition" ? "active" : ""}`}
          onClick={() => setActiveTab("definition")}
        >
          <Layers size={14} />
          <span>Definition</span>
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === "parameters" ? "active" : ""}`}
          onClick={() => setActiveTab("parameters")}
        >
          <Settings size={14} />
          <span>Parameters</span>
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === "performance" ? "active" : ""}`}
          onClick={() => setActiveTab("performance")}
        >
          <Activity size={14} />
          <span>Performance</span>
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === "health" ? "active" : ""}`}
          onClick={() => setActiveTab("health")}
        >
          <Activity size={14} />
          <span>Health</span>
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === "versions" ? "active" : ""}`}
          onClick={() => setActiveTab("versions")}
        >
          <History size={14} />
          <span>Versions</span>
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === "requirements" ? "active" : ""}`}
          onClick={() => setActiveTab("requirements")}
        >
          <ListChecks size={14} />
          <span>Requirements</span>
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === "test" ? "active" : ""}`}
          onClick={() => setActiveTab("test")}
        >
          <Terminal size={14} />
          <span>Test / Evaluate</span>
        </button>
      </div>

      {/* Tab Panels */}
      <div className="tab-content">
        {activeTab === "overview" && (
          <div className="overview-tab space-y-4">
            {/* How It Works Steps */}
            {strategy.howItWorks && strategy.howItWorks.length > 0 && (
              <div className="card-surface p-4 border border-subtle rounded-lg">
                <h3 className="font-semibold text-primary mb-3 text-sm">
                  How It Works (Execution Logic)
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {strategy.howItWorks.map((step, idx) => (
                    <div key={idx} className="step-card p-3 bg-base/50 rounded border border-subtle">
                      <div className="text-cyan font-semibold text-xs mb-1">
                        {idx + 1}. {step.title}
                      </div>
                      <p className="text-xs text-secondary leading-relaxed">
                        {step.description}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Risk Profile & Capital */}
            <div className="card-surface p-4 border border-subtle rounded-lg">
              <h3 className="font-semibold text-primary mb-3 text-sm">Risk & Capital Profile</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                <div>
                  <span className="text-muted block">Risk Category</span>
                  <span className="font-semibold text-secondary">
                    {strategy.riskProfile?.riskCategory || "Standard"}
                  </span>
                </div>
                <div>
                  <span className="text-muted block">Estimated Margin</span>
                  <span className="font-semibold text-primary">
                    {strategy.riskProfile?.marginAmount
                      ? `₹${Number(strategy.riskProfile.marginAmount).toLocaleString()}`
                      : "—"}
                  </span>
                </div>
                <div>
                  <span className="text-muted block">Declared Max DD</span>
                  <span className="font-semibold text-rose">
                    {strategy.riskProfile?.declaredMaxDrawdown
                      ? `₹${Number(strategy.riskProfile.declaredMaxDrawdown).toLocaleString()}`
                      : "—"}
                  </span>
                </div>
                <div>
                  <span className="text-muted block">Execution Modes</span>
                  <span className="font-semibold text-secondary">
                    {strategy.executionModes?.join(", ") || "PAPER"}
                  </span>
                </div>
              </div>
            </div>

            {/* Research References */}
            {strategy.references && strategy.references.length > 0 && (
              <div className="card-surface p-4 border border-subtle rounded-lg">
                <h3 className="font-semibold text-primary mb-2 text-sm">Research References</h3>
                <ul className="space-y-2 text-xs">
                  {strategy.references.map((ref, idx) => (
                    <li key={idx} className="border-b border-subtle/50 pb-2">
                      <a
                        href={ref.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-cyan hover:underline flex items-center gap-1 font-medium"
                      >
                        {ref.title}
                        <ExternalLink size={11} />
                      </a>
                      <p className="text-muted text-[11px] mt-0.5">{ref.scope}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {activeTab === "definition" && (
          <DefinitionViewer definition={definition} format={strategy.definitionFormat} />
        )}

        {activeTab === "parameters" && (
          <div className="parameters-tab card-surface p-4 border border-subtle rounded-lg">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h3 className="font-semibold text-primary text-sm">Strategy Parameters</h3>
                <p className="text-xs text-muted">
                  Configurable threshold parameters. Modifying parameters creates a new version.
                </p>
              </div>
              <button
                type="button"
                className="btn-kite-primary text-xs"
                onClick={handleSaveParameters}
                disabled={updateStrategyMutation.isPending}
              >
                {updateStrategyMutation.isPending ? "Saving..." : "Save Parameters"}
              </button>
            </div>

            {Object.keys(parameters).length === 0 ? (
              <p className="text-xs text-muted">This strategy has no parameterized variables.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(parameters).map(([key, config]: any) => (
                  <div key={key} className="form-group border border-subtle p-3 rounded">
                    <div className="flex justify-between items-center mb-1">
                      <label className="text-xs font-mono font-semibold text-cyan">{key}</label>
                      {config?.min !== undefined && (
                        <span className="text-[10px] text-muted">
                          Range: {config.min} – {config.max}
                        </span>
                      )}
                    </div>
                    <input
                      type="number"
                      className="filter-input w-full text-xs"
                      value={paramsForm[key] ?? ""}
                      onChange={(e) =>
                        setParamsForm({ ...paramsForm, [key]: e.target.value })
                      }
                    />
                    {config?.description && (
                      <p className="text-[11px] text-muted mt-1">{config.description}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === "performance" && <PerformanceSection strategyId={strategyId} />}

        {activeTab === "health" && <HealthSection strategyId={strategyId} />}

        {activeTab === "versions" && (
          <VersionsSection
            strategyId={strategyId}
            currentVersionId={strategy.currentVersionId}
          />
        )}

        {activeTab === "requirements" && (
          <RequirementsSection
            strategyId={strategyId}
            versionNo={currentVersion?.versionNo || 1}
          />
        )}

        {activeTab === "test" && currentVersion && (
          <StrategyTestPanel versionId={currentVersion.id} />
        )}
      </div>
    </div>
  );
};
