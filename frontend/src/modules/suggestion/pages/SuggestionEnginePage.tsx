import React from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  AlertTriangle,
  Clock,
  Layers,
  Lightbulb,
  Loader2,
  Play,
  RefreshCw,
  Square,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import {
  useRunSuggestion,
  useStopSuggestion,
  useSuggestionStatus,
  useSuggestionUnderlyings,
} from "../hooks/useSuggestion";
import { formatDateTime } from "../components/formatters";
import { UNDERLYING_NAMES } from "../components/underlyingNames";
import { SuggestionUnderlying } from "../types/suggestion.types";

const NODE_LABELS: Record<string, string> = {
  load_research: "Reading Research data",
  analyze_underlying: "Analysing underlyings",
  pick_top: "Picking top suggestions",
  save: "Saving suggestions",
  track_outcomes: "Checking past outcomes",
};

type Tab = "INDEX" | "COMMODITY";

export const SuggestionEnginePage: React.FC = () => {
  const navigate = useNavigate();
  const [tab, setTab] = React.useState<Tab>("INDEX");
  const { data: status, refetch: refetchStatus } = useSuggestionStatus();
  const isLooping = Boolean(status?.isLooping);
  const { data: under, refetch, isLoading } = useSuggestionUnderlyings(isLooping);
  const runMutation = useRunSuggestion();
  const stopMutation = useStopSuggestion();

  const all: SuggestionUnderlying[] = under?.list ?? [];
  const byType = (t: Tab) => all.filter((u) => u.type === t);
  const cards = byType(tab);
  const activeSet = new Set(status?.active ?? []);
  const totalSuggestions = all.reduce((sum, u) => sum + u.count, 0);

  const runResult = runMutation.data;
  const noResearch =
    (under && !under.hasResearch) ||
    (runResult && !runResult.started && runResult.reason === "NO_RESEARCH_DATA") ||
    status?.stopReason === "NO_RESEARCH";

  const handleRefresh = () => {
    refetchStatus();
    refetch();
  };

  return (
    <div className="page-container sp-page">
      <div className="sp-header">
        <div>
          <div className="sp-title-row">
            <h1 className="sp-title">Suggestion Engine</h1>
            {totalSuggestions > 0 && <span className="badge badge--green">{totalSuggestions} Suggestions</span>}
            {isLooping && (
              <span className="badge badge--cyan sp-live">
                <RefreshCw size={12} className="sp-spin" />
                Loop {status?.iteration} · {status?.progressPct ?? 0}%
              </span>
            )}
          </div>
          <p className="sp-desc">
            Small, frequent wins: each suggestion targets 5-10% on the premium with a tight stop. Top 5 index and
            top 3 commodity underlyings from Research; strategies and rules choose CALL or PUT, the trend is only
            context. Each underlying keeps looping until you stop it.
          </p>
        </div>
        <div className="sp-actions">
          <button type="button" className="sp-btn" onClick={handleRefresh} title="Refresh">
            <RefreshCw size={13} className={isLooping ? "sp-spin" : ""} /> Refresh
          </button>
          {isLooping ? (
            <button
              type="button"
              className="sp-btn sp-btn--stop"
              onClick={() => stopMutation.mutate(undefined)}
              disabled={stopMutation.isPending}
            >
              <Square size={14} /> Stop all
            </button>
          ) : null}
          <button
            type="button"
            className="sp-btn sp-btn--run"
            onClick={() => runMutation.mutate(undefined)}
            disabled={runMutation.isPending || all.length === 0}
          >
            <Play size={14} /> Run all
          </button>
        </div>
      </div>

      {noResearch && (
        <div className="sp-notice" role="alert">
          <AlertTriangle size={16} />
          <span>Research Engine has no data yet. Run the Research Engine first, then start suggestions.</span>
        </div>
      )}

      {isLooping && (
        <div className="sp-progress">
          <Loader2 size={14} className="sp-spin" />
          <span>{NODE_LABELS[status?.currentNode ?? ""] ?? "Starting"}</span>
          <span className="sp-muted">
            · {status?.stats?.picked ?? 0} picked last run · AI {status?.stats?.aiUsed ?? 0} / code-only{" "}
            {status?.stats?.baselineUsed ?? 0}
          </span>
        </div>
      )}

      <div className="sp-tabbar">
        <div className="sp-tabs" role="tablist">
          {(["INDEX", "COMMODITY"] as const).map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={tab === t}
              className={`sp-tab ${tab === t ? "sp-tab--active" : ""}`}
              onClick={() => setTab(t)}
            >
              <Layers size={14} />
              <span>
                {t === "INDEX" ? "Indices" : "Commodities"} ({byType(t).length})
              </span>
            </button>
          ))}
        </div>
        <div className="sp-muted mono">Showing {cards.length} underlyings from Research</div>
      </div>

      {isLoading ? (
        <div className="sp-empty">
          <RefreshCw size={24} className="sp-spin" />
          <div className="sp-empty-title">Loading underlyings...</div>
        </div>
      ) : cards.length === 0 ? (
        <div className="sp-empty">
          <Lightbulb size={28} />
          <div className="sp-empty-title">No {tab.toLowerCase()} underlyings yet</div>
          <p className="sp-muted">Run the Research Engine, then come back to start suggestions.</p>
        </div>
      ) : (
        <div className="sp-grid">
          {cards.map((u) => {
            const running = u.active || activeSet.has(u.code);
            const tone = u.direction === "BULLISH" ? "sp-card--bull" : u.direction === "BEARISH" ? "sp-card--bear" : "";
            return (
              <div key={u.code} className={`sp-card ${tone}`}>
                <button
                  type="button"
                  className="sp-card-body"
                  onClick={() => navigate({ to: "/suggestion/$underlying/detail", params: { underlying: u.code } })}
                >
                  <div className="sp-card-top">
                    <div>
                      <div className="sp-symbol-row">
                        <span className={`sp-symbol ${u.type === "INDEX" ? "sp-symbol--index" : "sp-symbol--commodity"}`}>
                          {u.code}
                        </span>
                        <h2 className="sp-name">{UNDERLYING_NAMES[u.code] ?? u.code}</h2>
                      </div>
                      <div className="sp-muted sp-sub">
                        {u.type} · {u.count} {u.count === 1 ? "suggestion" : "suggestions"}
                      </div>
                    </div>
                    {u.direction && (
                      <span className={`badge ${u.direction === "BULLISH" ? "badge--green" : "badge--red"}`}>
                        {u.direction === "BULLISH" ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
                        {u.direction}
                      </span>
                    )}
                  </div>

                  <div className="sp-metrics">
                    <div>
                      <div className="sp-metric-label">Suggestions</div>
                      <div className="sp-metric-value">
                        {u.count}
                        {running && <Loader2 size={13} className="sp-spin sp-loader" aria-label="Iterating" />}
                      </div>
                    </div>
                    <div>
                      <div className="sp-metric-label">Top conf.</div>
                      <div className="sp-metric-value">{u.count > 0 ? u.topConfidence : "—"}</div>
                    </div>
                    <div>
                      <div className="sp-metric-label">Call / Put</div>
                      <div className="sp-metric-value">
                        <span className="sp-up">{u.callCount}</span>
                        <span className="sp-dim"> / </span>
                        <span className="sp-down">{u.putCount}</span>
                      </div>
                    </div>
                  </div>

                  <div className="sp-iterated">
                    <Clock size={12} />
                    <span>
                      {running ? "Loop running · " : ""}Last completed
                      {u.lastLoop ? ` (loop ${u.lastLoop})` : ""}: {formatDateTime(u.lastIteratedAt)}
                    </span>
                  </div>
                  {u.lastNote && (
                    <div className={`sp-note ${u.count === 0 ? "sp-note--warn" : ""}`}>{u.lastNote}</div>
                  )}
                </button>

                <div className="sp-card-foot">
                  <span className="sp-muted">
                    {u.newsStatus ? u.newsStatus.replace("_", " ") : "No research status"}
                  </span>
                  {running ? (
                    <button
                      type="button"
                      className="sp-btn sp-btn--stop"
                      onClick={() => stopMutation.mutate([u.code])}
                      disabled={stopMutation.isPending}
                    >
                      <Square size={13} /> Stop
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="sp-btn sp-btn--run"
                      onClick={() => runMutation.mutate({ underlyings: [u.code] })}
                      disabled={runMutation.isPending}
                    >
                      <Play size={13} /> Run
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
      <p className="sp-muted sp-footnote">
        Prices are from the last run. They are re-checked at Trade Lock before any order.
      </p>
    </div>
  );
};
