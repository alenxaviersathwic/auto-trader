import React, { useState } from "react";
import { useParams, useNavigate } from "@tanstack/react-router";
import {
  ArrowLeft,
  Edit,
  Copy,
  Trash2,
  AlertTriangle,
  ExternalLink,
  RotateCcw,
  Save,
  ChevronRight,
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
import { StrategyBacktestPanel } from "../components/StrategyBacktestPanel";

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
    | "backtest"
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
    return (
      <div className="sd-page">
        <div className="sd-card sd-loading-box">
          <div className="spinner" />
          <span>Loading strategy #{strategyId}…</span>
        </div>
      </div>
    );
  }

  if (!strategy) {
    return (
      <div className="sd-page">
        <div className="sd-card sd-loading-box">
          <span className="text-red">Strategy #{strategyId} not found.</span>
          <button
            type="button"
            className="sd-ctrl-btn"
            onClick={() => navigate({ to: "/strategies" as any })}
          >
            <ArrowLeft size={13} />
            <span>Back to Strategies</span>
          </button>
        </div>
      </div>
    );
  }

  const currentVersion = strategy.currentVersion;
  const definition = currentVersion?.definition || {};
  const parameters = definition.parameters || {};
  const paramKeys = Object.keys(parameters);
  const snapshot = strategy.latestPerformance && strategy.latestPerformance[0];
  const hasReviewFlags = strategy.reviewFlags && strategy.reviewFlags.length > 0;

  if (!paramsInitialized && paramKeys.length > 0) {
    const initial: Record<string, any> = {};
    Object.entries(parameters).forEach(([k, v]: any) => {
      initial[k] = typeof v === "object" && v !== null ? v.default ?? "" : v;
    });
    setParamsForm(initial);
    setParamsInitialized(true);
  }

  const handleResetParameters = () => {
    const reset: Record<string, any> = {};
    Object.entries(parameters).forEach(([k, v]: any) => {
      reset[k] = typeof v === "object" && v !== null ? v.default ?? "" : v;
    });
    setParamsForm(reset);
  };

  const handleLifecycleChange = (to: string) => {
    if (!strategy.executable && to === "ACTIVE") {
      alert("Cannot activate: Strategy has definition issues or missing handlers and is not executable.");
      return;
    }
    const reason = window.prompt(
      `Reason for transitioning lifecycle to ${to}:`,
      `Manual review change to ${to}`
    );
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
    Object.entries(paramsForm).forEach(([k, v]) => {
      if (updatedDef.parameters[k] !== undefined) {
        if (typeof updatedDef.parameters[k] === "object" && updatedDef.parameters[k] !== null) {
          updatedDef.parameters[k] = {
            ...updatedDef.parameters[k],
            default: Number(v),
          };
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

  const formatOptimalTag = () => {
    if (strategy.tags && strategy.tags.length > 0) {
      const rawTags: string[] = Array.isArray(strategy.tags)
        ? strategy.tags
        : String(strategy.tags).split(",");
      const cleaned = rawTags
        .map((t: string) => t.replace(/_/g, " ").trim())
        .filter((t: string) => !["BUILT IN", "TEXTBOOK", "LEGACY"].includes(t.toUpperCase()))
        .filter(Boolean);
      if (cleaned.length > 0) return cleaned.join(", ");
    }
    if (strategy.structure) {
      return `${strategy.bias ? strategy.bias + " " : ""}${strategy.structure.replace(/_/g, " ")}`;
    }
    return "—";
  };

  const effectiveHealth = strategy.effectiveHealth || strategy.health || "UNKNOWN";
  const sessionEntry = definition.bounds?.session?.entryTime || "09:15";
  const sessionExit = definition.bounds?.session?.exitTime || "15:14";
  const maxTradesPerDay = definition.bounds?.maxTradesPerDay;

  const formatRupeeValue = (val: number | string | null | undefined, showSign = false) => {
    if (val === null || val === undefined || val === "") return "—";
    const num = Number(val);
    if (Number.isNaN(num)) return "—";
    const sign = showSign && num > 0 ? "+" : num < 0 ? "-" : "";
    return `${sign}₹${Math.abs(num).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
  };

  return (
    <div className="sd-page">
      {/* 1. Compact Aligned Top Bar */}
      <div className="sd-topbar">
        <div className="sd-topbar-left">
          <button
            type="button"
            className="sd-ctrl-btn"
            onClick={() => navigate({ to: "/strategies" as any })}
          >
            <ArrowLeft size={13} />
            <span>Strategies</span>
          </button>

          <span className="sd-topbar-sep">/</span>
          <span className="sd-code-tag mono">{strategy.code.toUpperCase()}</span>
          <span className="sd-ver-tag mono">v{currentVersion?.versionNo || 1}</span>
          <span
            className={`sd-status-pill ${
              strategy.lifecycleStatus === "ACTIVE"
                ? "is-green"
                : strategy.lifecycleStatus === "SUSPENDED"
                ? "is-red"
                : strategy.lifecycleStatus === "IN_REVIEW"
                ? "is-amber"
                : "is-blue"
            }`}
          >
            <span className="sd-status-dot" />
            {strategy.lifecycleStatus}
          </span>
        </div>

        <div className="sd-topbar-right">
          {/* Enable / Disable Toggle Control */}
          <label className={`sd-toggle-pill ${strategy.enabled ? "is-on" : ""}`}>
            <span className="sd-toggle-label">
              {strategy.enabled ? "Live Active" : "Disabled"}
            </span>
            <span className="toggle-switch">
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
            </span>
          </label>

          {/* Lifecycle Select */}
          <select
            className="sd-ctrl-select mono"
            value={strategy.lifecycleStatus}
            onChange={(e) => handleLifecycleChange(e.target.value)}
            title="Transition Lifecycle Status"
          >
            <option value="DRAFT">DRAFT</option>
            <option value="IN_REVIEW">IN_REVIEW</option>
            <option value="ACTIVE" disabled={!strategy.executable}>
              ACTIVE {!strategy.executable ? "(Not Executable)" : ""}
            </option>
            <option value="SUSPENDED">SUSPENDED</option>
            <option value="ARCHIVED">ARCHIVED</option>
          </select>

          <button
            type="button"
            className="sd-ctrl-btn"
            onClick={() => navigate({ to: `/strategies/${strategy.id}/edit` as any })}
          >
            <Edit size={13} />
            <span>Edit</span>
          </button>

          <button
            type="button"
            className="sd-ctrl-btn"
            onClick={() =>
              cloneMutation.mutate(strategy.id, {
                onSuccess: (c) => navigate({ to: `/strategies/${c.id}` as any }),
              })
            }
            disabled={cloneMutation.isPending}
          >
            <Copy size={13} />
            <span>Clone</span>
          </button>

          <button
            type="button"
            className="sd-ctrl-btn sd-ctrl-btn--danger"
            title="Delete Strategy"
            onClick={() => {
              if (window.confirm(`Soft delete "${strategy.name}"?`)) {
                deleteMutation.mutate(strategy.id, {
                  onSuccess: () => navigate({ to: "/strategies" as any }),
                });
              }
            }}
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      {/* 2. Compact Summary & Telemetry Card */}
      <div className="sd-summary-card">
        <div className="sd-summary-head">
          <div className="sd-summary-title-block">
            <h1 className="sd-title">{strategy.name}</h1>
            <p className="sd-desc">
              {strategy.description || "Algorithmic option strategy."}
            </p>
          </div>

          <div className="sd-summary-badges">
            <span className="sd-tag sd-tag--cyan">
              {strategy.structure || strategy.category}
            </span>
            <span
              className={`sd-tag ${
                strategy.bias === "BULLISH"
                  ? "sd-tag--green"
                  : strategy.bias === "BEARISH"
                  ? "sd-tag--red"
                  : "sd-tag--amber"
              }`}
            >
              {strategy.bias || "DYNAMIC"}
            </span>
            {strategy.markets?.map((m) => (
              <span key={m} className="sd-tag">
                {m}
              </span>
            ))}
            {strategy.timeframe && (
              <span className="sd-tag mono">{strategy.timeframe}</span>
            )}
            {strategy.suggestable && (
              <span className="sd-tag sd-tag--green">SUGGESTABLE</span>
            )}
          </div>
        </div>

        {/* 6-Column Compact Telemetry Strip (Matching StrategyCard aesthetic) */}
        <div className="sd-telemetry-strip">
          <div className="sd-telemetry-cell">
            <span className="sd-telemetry-label">Win Rate</span>
            <span
              className={`sd-telemetry-val mono ${
                snapshot && snapshot.winRatePct >= 50
                  ? "text-green"
                  : snapshot
                  ? "text-red"
                  : ""
              }`}
            >
              {snapshot ? `${Number(snapshot.winRatePct).toFixed(1)}%` : "—"}
            </span>
            <span className="sd-telemetry-sub mono">
              {snapshot
                ? `${snapshot.totalTrades}T (${snapshot.winningTrades}W/${snapshot.losingTrades}L)`
                : strategy.validationStatus}
            </span>
          </div>

          <div className="sd-telemetry-cell">
            <span className="sd-telemetry-label">Profit Factor</span>
            <span className="sd-telemetry-val mono text-amber">
              {snapshot?.profitFactor ? Number(snapshot.profitFactor).toFixed(2) : "—"}
            </span>
            <span className="sd-telemetry-sub mono">
              {snapshot?.domain || strategy.validationStatus}
            </span>
          </div>

          <div className="sd-telemetry-cell">
            <span className="sd-telemetry-label">Net P&amp;L</span>
            <span
              className={`sd-telemetry-val mono ${
                snapshot && snapshot.netPnl > 0
                  ? "text-green"
                  : snapshot && snapshot.netPnl < 0
                  ? "text-red"
                  : ""
              }`}
            >
              {snapshot ? formatRupeeValue(snapshot.netPnl, true) : "—"}
            </span>
            <span className="sd-telemetry-sub mono">
              DD: {snapshot?.maxDrawdown ? formatRupeeValue(snapshot.maxDrawdown) : "—"}
            </span>
          </div>

          <div className="sd-telemetry-cell">
            <span className="sd-telemetry-label">Est. Margin</span>
            <span className="sd-telemetry-val mono">
              {formatRupeeValue(strategy.riskProfile?.marginAmount)}
            </span>
            <span className="sd-telemetry-sub mono">
              Max DD Cap: {formatRupeeValue(strategy.riskProfile?.declaredMaxDrawdown)}
            </span>
          </div>

          <div className="sd-telemetry-cell">
            <span className="sd-telemetry-label">Session Window</span>
            <span className="sd-telemetry-val mono text-cyan">
              {sessionEntry}–{sessionExit}
            </span>
            <span className="sd-telemetry-sub mono">
              {maxTradesPerDay ? `Max ${maxTradesPerDay} trades/d` : "Unlimited trades"}
            </span>
          </div>

          <div className="sd-telemetry-cell">
            <span className="sd-telemetry-label">Health &amp; Tags</span>
            <span
              className={`sd-telemetry-val mono ${
                effectiveHealth === "HEALTHY"
                  ? "text-green"
                  : effectiveHealth === "DEGRADED"
                  ? "text-amber"
                  : effectiveHealth === "SUSPENDED"
                  ? "text-red"
                  : ""
              }`}
            >
              {effectiveHealth}
            </span>
            <span className="sd-telemetry-sub mono">
              {strategy.tags?.length ? `${strategy.tags.length} tag${strategy.tags.length > 1 ? "s" : ""}` : "No tags"} ·{" "}
              {strategy.executionModes?.join("/") || "PAPER"}
            </span>
          </div>
        </div>

        {/* Compact Single-Line Notices */}
        {(hasReviewFlags || strategy.validationStatus === "UNTESTED") && (
          <div className="sd-notices-row">
            {hasReviewFlags && (
              <div className="sd-compact-notice is-warn">
                <AlertTriangle size={12} />
                <span>
                  <strong>Review Flags:</strong> {strategy.reviewFlags?.join(", ")}
                </span>
              </div>
            )}
            {strategy.validationStatus === "UNTESTED" && (
              <div className="sd-compact-notice">
                <AlertTriangle size={12} />
                <span>
                  <strong>Untested:</strong> No live validation yet. Run Backtest or record Paper snapshots to verify edge.
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 3. Clean Uniform Tab Navigation */}
      <div className="sd-tabs-nav" role="tablist">
        {(
          [
            { id: "overview", label: "Overview" },
            { id: "definition", label: "Rule Definition" },
            {
              id: "parameters",
              label: "Parameters",
              count: paramKeys.length > 0 ? String(paramKeys.length) : undefined,
            },
            { id: "performance", label: "Performance" },
            { id: "health", label: "Health" },
            {
              id: "versions",
              label: "Versions",
              count: `v${currentVersion?.versionNo || 1}`,
            },
            { id: "requirements", label: "Requirements" },
            { id: "test", label: "Evaluate" },
            { id: "backtest", label: "Backtest" },
          ] as const
        ).map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={activeTab === t.id}
            className={`sd-nav-tab ${activeTab === t.id ? "active" : ""}`}
            onClick={() => setActiveTab(t.id)}
          >
            <span>{t.label}</span>
            {"count" in t && t.count && (
              <span className="sd-nav-tab-badge mono">{t.count}</span>
            )}
          </button>
        ))}
      </div>

      {/* 4. Tab Content Area */}
      <div className="sd-content">
        {activeTab === "overview" && (
          <div className="sd-panel">
            {/* Equal 2-Column Spec & Schedule Sheet */}
            <div className="sd-overview-cols">
              {/* Left Column: Strategy Configuration */}
              <div className="sd-card">
                <div className="sd-card-header">
                  <span className="sd-card-title">Strategy Specification</span>
                  <span className="sd-tag mono">
                    {strategy.executable ? "EXECUTABLE" : "SUMMARY ONLY"}
                  </span>
                </div>
                <div className="sd-spec-list">
                  <div className="sd-spec-row">
                    <span className="sd-spec-key">Strategy Code</span>
                    <span className="sd-spec-val mono text-amber">{strategy.code}</span>
                  </div>
                  <div className="sd-spec-row">
                    <span className="sd-spec-key">Category &amp; Structure</span>
                    <span className="sd-spec-val mono">
                      {strategy.category} · {strategy.structure || "SINGLE_LONG"}
                    </span>
                  </div>
                  <div className="sd-spec-row">
                    <span className="sd-spec-key">Bias &amp; Option Side</span>
                    <span
                      className={`sd-spec-val mono ${
                        strategy.bias === "BULLISH"
                          ? "text-green"
                          : strategy.bias === "BEARISH"
                          ? "text-red"
                          : ""
                      }`}
                    >
                      {strategy.bias || "DYNAMIC"} · {strategy.optionSide || "BOTH"}
                    </span>
                  </div>
                  <div className="sd-spec-row">
                    <span className="sd-spec-key">Markets &amp; Exchange</span>
                    <span className="sd-spec-val mono">
                      {strategy.markets?.join(", ") || "—"} ({strategy.exchange || "NSE"})
                    </span>
                  </div>
                  <div className="sd-spec-row">
                    <span className="sd-spec-key">Timeframe &amp; Mode</span>
                    <span className="sd-spec-val mono">
                      {strategy.timeframe || "5m"} ·{" "}
                      {strategy.tradingModes?.join(", ") || "INTRADAY"}
                    </span>
                  </div>
                  <div className="sd-spec-row">
                    <span className="sd-spec-key">Execution Domains</span>
                    <span className="sd-spec-val mono">
                      {strategy.executionModes?.join(" / ") || "PAPER"}
                    </span>
                  </div>
                  <div className="sd-spec-row">
                    <span className="sd-spec-key">Definition Format</span>
                    <span className="sd-spec-val mono text-cyan">
                      {strategy.definitionFormat} (v{currentVersion?.versionNo || 1})
                    </span>
                  </div>
                  <div className="sd-spec-row">
                    <span className="sd-spec-key">Optimal Focus / Tags</span>
                    <span className="sd-spec-val">{formatOptimalTag()}</span>
                  </div>
                </div>
              </div>

              {/* Right Column: Risk Limits & Day-Context Tags */}
              <div className="sd-card">
                <div className="sd-card-header">
                  <span className="sd-card-title">Risk Limits &amp; Day-Context Tags</span>
                  <span className={`sd-tag ${strategy.tags?.length ? "sd-tag--green" : "sd-tag--amber"}`}>
                    {strategy.tags?.length ? `${strategy.tags.length} TAG${strategy.tags.length > 1 ? "S" : ""}` : "NO TAGS"}
                  </span>
                </div>

                {/* Day-Context Tags: matched against today's computed context (AFTER_HOLIDAY, EXPIRY_DAY,
                    DAY_MONDAY, ...) to nudge opportunity confidence -- replaces the old fixed weekly
                    schedule / Holiday Shift concept entirely. */}
                <div className="sd-schedule-bar">
                  <span className="sd-spec-key">Tags</span>
                  <div className="sd-weekdays-inline">
                    {strategy.tags && strategy.tags.length > 0 ? (
                      strategy.tags.map((tag) => (
                        <span key={tag} className="sd-day-chip mono is-on">
                          {tag}
                        </span>
                      ))
                    ) : (
                      <span className="sd-spec-val mono">None set</span>
                    )}
                  </div>
                </div>

                <div className="sd-spec-list">
                  <div className="sd-spec-row">
                    <span className="sd-spec-key">Session Entry – Exit</span>
                    <span className="sd-spec-val mono text-cyan">
                      {sessionEntry} – {sessionExit} IST
                    </span>
                  </div>
                  <div className="sd-spec-row">
                    <span className="sd-spec-key">Max Trades / Day</span>
                    <span className="sd-spec-val mono">
                      {maxTradesPerDay ?? "Unlimited"}
                    </span>
                  </div>
                  <div className="sd-spec-row">
                    <span className="sd-spec-key">Stop Loss % (Win-Rate Driven)</span>
                    <span className="sd-spec-val mono text-red">
                      {strategy.stopLossPct != null ? `${Number(strategy.stopLossPct).toFixed(1)}%` : "3.5%"}
                      {snapshot?.winRatePct != null && (
                        <span className="text-muted text-[11px] font-normal ml-1">
                          (WR: {Number(snapshot.winRatePct).toFixed(0)}%)
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="sd-spec-row">
                    <span className="sd-spec-key">Risk Category &amp; Stop Mode</span>
                    <span className="sd-spec-val mono">
                      {strategy.riskProfile?.riskCategory || "Standard"} ·{" "}
                      {definition.riskPolicy?.stopMode || "STRATEGY_FIXED"}
                    </span>
                  </div>
                  <div className="sd-spec-row">
                    <span className="sd-spec-key">Estimated Margin</span>
                    <span className="sd-spec-val mono">
                      {formatRupeeValue(strategy.riskProfile?.marginAmount)}
                    </span>
                  </div>
                  <div className="sd-spec-row">
                    <span className="sd-spec-key">Declared Max Drawdown</span>
                    <span className="sd-spec-val mono text-red">
                      {formatRupeeValue(strategy.riskProfile?.declaredMaxDrawdown)}
                    </span>
                  </div>
                  <div className="sd-spec-row">
                    <span className="sd-spec-key">Day Stop Gain / Loss</span>
                    <span className="sd-spec-val mono">
                      <span className="text-green">
                        {formatRupeeValue(definition.bounds?.dayStopGain?.value, true)}
                      </span>
                      {" / "}
                      <span className="text-red">
                        {formatRupeeValue(definition.bounds?.dayStopLoss?.value)}
                      </span>
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Execution Workflow Steps (if present) */}
            {strategy.howItWorks && strategy.howItWorks.length > 0 && (
              <div className="sd-card">
                <div className="sd-card-header">
                  <span className="sd-card-title">Execution Workflow</span>
                  <span className="sd-tag mono">{strategy.howItWorks.length} STEPS</span>
                </div>
                <div className="sd-steps-grid">
                  {strategy.howItWorks.map((step, idx) => (
                    <div key={idx} className="sd-step-item">
                      <div className="sd-step-top">
                        <span className="sd-step-index mono">{idx + 1}</span>
                        <span className="sd-step-name">{step.title}</span>
                      </div>
                      <p className="sd-step-body">{step.description}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Compact Execution Legs Summary Table (if definition.cases exist) */}
            {Array.isArray(definition.cases) && definition.cases.length > 0 && (
              <div className="sd-card">
                <div className="sd-card-header">
                  <span className="sd-card-title">
                    Configured Cases &amp; Option Legs ({definition.cases.length})
                  </span>
                  <button
                    type="button"
                    className="sd-link-btn"
                    onClick={() => setActiveTab("definition")}
                  >
                    <span>View Full Rule Tree</span>
                    <ChevronRight size={13} />
                  </button>
                </div>
                <div className="table-scroll-container">
                  <table className="data-table sd-compact-table">
                    <thead>
                      <tr>
                        <th>Case</th>
                        <th>Bias</th>
                        <th>Leg</th>
                        <th>Side</th>
                        <th>Option</th>
                        <th>Expiry</th>
                        <th>Strike</th>
                        <th>Qty</th>
                        <th>Stop Loss</th>
                        <th>Target</th>
                      </tr>
                    </thead>
                    <tbody>
                      {definition.cases.flatMap((c: any, cIdx: number) => {
                        const legs = c.entry?.legs || [];
                        if (legs.length === 0) {
                          return [
                            <tr key={`case-${cIdx}`}>
                              <td className="mono">#{c.key ?? cIdx + 1}</td>
                              <td>
                                <span className="sd-tag">{c.bias || "DYNAMIC"}</span>
                              </td>
                              <td colSpan={8} className="text-muted">
                                No option legs configured
                              </td>
                            </tr>,
                          ];
                        }
                        return legs.map((leg: any, lIdx: number) => (
                          <tr key={`${cIdx}-${leg.legId || lIdx}`}>
                            <td className="mono">#{c.key ?? cIdx + 1}</td>
                            <td>
                              <span
                                className={`sd-tag ${
                                  c.bias === "BULLISH"
                                    ? "sd-tag--green"
                                    : c.bias === "BEARISH"
                                    ? "sd-tag--red"
                                    : "sd-tag--cyan"
                                }`}
                              >
                                {c.bias || "DYNAMIC"}
                              </span>
                            </td>
                            <td className="mono">L{leg.legId || lIdx + 1}</td>
                            <td>
                              <span
                                className={`sd-tag ${
                                  leg.side === "BUY" ? "sd-tag--green" : "sd-tag--red"
                                }`}
                              >
                                {leg.side}
                              </span>
                            </td>
                            <td className="mono">{leg.instrument?.optionType || "CE/PE"}</td>
                            <td className="mono">
                              {leg.instrument?.expiry?.cycle || "WEEKLY"} (
                              {leg.instrument?.expiry?.index || 1})
                            </td>
                            <td className="mono text-cyan">
                              {leg.instrument?.strike?.selector === "ATM_OFFSET"
                                ? `ATM${
                                    leg.instrument.strike.steps > 0
                                      ? `+${leg.instrument.strike.steps}`
                                      : leg.instrument.strike.steps === 0
                                      ? ""
                                      : leg.instrument.strike.steps
                                  }`
                                : leg.instrument?.strike?.selector || "ATM"}
                            </td>
                            <td className="mono">
                              {leg.quantity?.value ?? 1} {leg.quantity?.unit || "LOT"}
                            </td>
                            <td className="mono text-red">
                              {leg.stopLoss
                                ? `-${leg.stopLoss.value}${
                                    leg.stopLoss.type === "PERCENT" ? "%" : "pt"
                                  }`
                                : "—"}
                            </td>
                            <td className="mono text-green">
                              {leg.target
                                ? `+${leg.target.value}${
                                    leg.target.type === "PERCENT" ? "%" : "pt"
                                  }`
                                : "—"}
                            </td>
                          </tr>
                        ));
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Risk Notes & References Row */}
            {((strategy.riskNotes && strategy.riskNotes.length > 0) ||
              (strategy.references && strategy.references.length > 0)) && (
              <div className="sd-overview-cols">
                {strategy.riskNotes && strategy.riskNotes.length > 0 && (
                  <div className="sd-card">
                    <div className="sd-card-header">
                      <span className="sd-card-title">Risk Notes</span>
                    </div>
                    <ul className="sd-bullet-list">
                      {strategy.riskNotes.map((note, idx) => (
                        <li key={idx}>{note}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {strategy.references && strategy.references.length > 0 && (
                  <div className="sd-card">
                    <div className="sd-card-header">
                      <span className="sd-card-title">Research References</span>
                    </div>
                    <ul className="sd-ref-list">
                      {strategy.references.map((ref, idx) => (
                        <li key={idx} className="sd-ref-item">
                          <a
                            href={ref.url}
                            target="_blank"
                            rel="noreferrer"
                            className="sd-ref-link"
                          >
                            <span>{ref.title}</span>
                            <ExternalLink size={11} />
                          </a>
                          <p className="sd-ref-scope">{ref.scope}</p>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === "definition" && (
          <DefinitionViewer definition={definition} format={strategy.definitionFormat} />
        )}

        {activeTab === "parameters" && (
          <div className="sd-card">
            <div className="sd-card-header">
              <div>
                <span className="sd-card-title">
                  Strategy Parameters ({paramKeys.length})
                </span>
                <p className="sd-card-sub">
                  Modifying parameter defaults creates a new immutable strategy version.
                </p>
              </div>
              {paramKeys.length > 0 && (
                <div className="sd-topbar-right">
                  <button
                    type="button"
                    className="sd-ctrl-btn"
                    onClick={handleResetParameters}
                  >
                    <RotateCcw size={12} />
                    <span>Reset</span>
                  </button>
                  <button
                    type="button"
                    className="sd-ctrl-btn sd-ctrl-btn--primary"
                    onClick={handleSaveParameters}
                    disabled={updateStrategyMutation.isPending}
                  >
                    <Save size={12} />
                    <span>
                      {updateStrategyMutation.isPending ? "Saving…" : "Save Parameters"}
                    </span>
                  </button>
                </div>
              )}
            </div>

            {paramKeys.length === 0 ? (
              <div className="sd-empty-inline">
                No configurable parameters defined for this strategy.
              </div>
            ) : (
              <div className="sd-param-grid">
                {Object.entries(parameters).map(([key, config]: any) => {
                  const defaultVal =
                    typeof config === "object" && config !== null ? config.default : config;
                  return (
                    <div key={key} className="sd-param-card">
                      <div className="sd-param-head">
                        <label className="sd-param-key">{key}</label>
                        <div className="sd-summary-badges">
                          {config?.min !== undefined && (
                            <span className="sd-tag mono">
                              {config.min} – {config.max}
                            </span>
                          )}
                          {defaultVal !== undefined && (
                            <span className="sd-tag sd-tag--cyan mono">
                              Def: {defaultVal}
                            </span>
                          )}
                        </div>
                      </div>
                      <input
                        type="number"
                        step="any"
                        className="input mono"
                        value={paramsForm[key] ?? ""}
                        onChange={(e) =>
                          setParamsForm({ ...paramsForm, [key]: e.target.value })
                        }
                      />
                      {config?.description && (
                        <p className="sd-param-desc">{config.description}</p>
                      )}
                    </div>
                  );
                })}
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

        {activeTab === "backtest" && (
          <StrategyBacktestPanel
            strategyId={strategyId}
            markets={strategy.markets || []}
          />
        )}
      </div>
    </div>
  );
};
