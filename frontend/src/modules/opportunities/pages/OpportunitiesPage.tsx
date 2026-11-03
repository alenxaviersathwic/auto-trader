import React from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";
import {
  Activity,
  AlertTriangle,
  ChevronRight,
  Clock,
  Layers,
  Lightbulb,
  Loader2,
  Play,
  Sparkles,
  Square,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import {
  resumeOpportunityLoop,
  useMasterIterations,
  useMasterOpportunityHistory,
  useOpportunityCards,
  useOpportunityLoop,
  useStartOpportunity,
  useStopAll,
  useStopCard,
} from "../hooks/useOpportunities";
import { OpportunitySideSheet } from "../components/OpportunitySideSheet";
import { formatDateTime } from "../components/formatters";
import { UNDERLYING_NAMES } from "../components/underlyingNames";
import { OpportunityCardItem } from "../types/opportunities.types";

type Tab = "INDEX" | "COMMODITY";

const STOP_REASON: Record<string, string> = {
  STOPPED_BY_USER: "Stopped",
  REPLACED_BY_NEW_START: "Replaced",
  DAY_ENDED: "Day ended",
};

// ── Side-sheet data loader ────────────────────────────────────────────────────
const SheetLoader: React.FC<{
  card: OpportunityCardItem;
  isIterating: boolean;
  onStart: () => void;
  onStop: () => void;
  isStarting: boolean;
  isStopping: boolean;
  onClose: () => void;
}> = ({ card, isIterating, onStart, onStop, isStarting, isStopping, onClose }) => {
  const loop = useOpportunityLoop();
  // Per-master history, not useLatestOpportunities: the side sheet shows every past loop as its
  // own batch, and /opportunities/latest only ever has the single newest (isLatest=True) one.
  const { data, isLoading } = useMasterOpportunityHistory(card.master?.id ?? null, loop.running);
  const iterations = useMasterIterations(card.master?.id ?? null, loop.running);
  return (
    <OpportunitySideSheet
      code={card.code}
      type={card.type}
      card={card}
      iterationsCompleted={card.master?.iterationsCompleted ?? 0}
      opportunities={data?.list ?? []}
      iterations={iterations.data?.list ?? []}
      isLoading={isLoading}
      isIterating={isIterating}
      onStart={onStart}
      onStop={onStop}
      isStarting={isStarting}
      isStopping={isStopping}
      onClose={onClose}
    />
  );
};

// ── Page ──────────────────────────────────────────────────────────────────────
export const OpportunitiesPage: React.FC = () => {
  const navigate = useNavigate({ from: "/opportunities" });
  const search = useSearch({ from: "/opportunities" }) as { tab?: Tab; card?: string };

  const tab: Tab = search.tab ?? "INDEX";
  const openCard = search.card ?? null;

  const loop = useOpportunityLoop();
  const { cards: all, hasResearch, tradeDate, isLoading, error } =
    useOpportunityCards(loop.running);
  const startMutation = useStartOpportunity();
  const stopCard = useStopCard();
  const stopAll = useStopAll();

  const byType = (t: Tab) => all.filter((u) => u.type === t);
  const cards = byType(tab);

  // Minimal informative summary counts
  const runningCount = all.filter((c) => c.master?.state === "RUNNING").length;
  const tabRunningCount = cards.filter((c) => c.master?.state === "RUNNING").length;
  const totalLive = all.reduce((sum, u) => sum + (u.master?.liveCount ?? 0), 0);
  const totalSaved = all.reduce((sum, u) => sum + (u.master?.opportunitiesTotal ?? 0), 0);
  const totalCalls = all.reduce((sum, u) => sum + (u.master?.callCount ?? 0), 0);
  const totalPuts = all.reduce((sum, u) => sum + (u.master?.putCount ?? 0), 0);
  const bullCount = cards.filter((c) => c.direction === "BULLISH").length;
  const bearCount = cards.filter((c) => c.direction === "BEARISH").length;

  React.useEffect(() => {
    if (runningCount > 0 && !loop.running) resumeOpportunityLoop();
  }, [runningCount, loop.running]);

  const setTab = (t: Tab) =>
    navigate({ search: (s) => ({ ...s, tab: t, card: undefined }) });

  const openSheet = (code: string) =>
    navigate({ search: (s) => ({ ...s, card: code }) });

  const closeSheet = () =>
    navigate({ search: (s) => ({ ...s, card: undefined }) });

  const activeCard = openCard ? all.find((c) => c.code === openCard) ?? null : null;

  const startResult = startMutation.data;
  const noResearch =
    !hasResearch || (startResult && !startResult.started && startResult.reason === "NO_RESEARCH_DATA");

  const handleStartTab = () => {
    const codes = cards.map((c) => c.code);
    if (codes.length > 0) {
      startMutation.mutate({ underlyings: codes });
    }
  };

  return (
    <div className="sp-page">
      {/* Minimal High-Density Command & Summary Strip */}
      <div className="sp-toolbar">
        <div className="sp-toolbar-left">
          <div className="sp-tabs" role="tablist">
            {(["INDEX", "COMMODITY"] as const).map((t) => {
              const list = byType(t);
              const liveInTab = list.reduce((acc, item) => acc + (item.master?.liveCount ?? 0), 0);
              const runningInTab = list.filter((item) => item.master?.state === "RUNNING").length;
              return (
                <button
                  key={t}
                  type="button"
                  role="tab"
                  aria-selected={tab === t}
                  className={`sp-tab ${tab === t ? "sp-tab--active" : ""}`}
                  onClick={() => setTab(t)}
                >
                  <Layers size={13} />
                  <span>{t === "INDEX" ? "Indices" : "Commodities"}</span>
                  <span className="sp-tab-count mono">{list.length}</span>
                  {runningInTab > 0 && <span className="sp-pulse-dot" title={`${runningInTab} running`} />}
                  {liveInTab > 0 && (
                    <span className="sp-tab-live mono">{liveInTab} live</span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Minimal Inline Summary Telemetry */}
          <div className="sp-summary-strip">
            <div className="sp-stat-pill" title="Active scanning loops across underlyings">
              <span className={`sp-status-dot ${runningCount > 0 ? "sp-status-dot--live" : ""}`} />
              <span className="sp-stat-label">Active</span>
              <span className="sp-stat-val mono">
                {runningCount}/{all.length}
              </span>
            </div>

            <div className="sp-stat-pill" title="Live active setups / total saved today">
              <Sparkles size={12} className="sp-up" />
              <span className="sp-stat-label">Live</span>
              <span className="sp-stat-val mono sp-up">{totalLive}</span>
              {totalSaved > 0 && <span className="sp-stat-sub mono">/ {totalSaved}</span>}
            </div>

            <div className="sp-stat-pill" title="Total Call vs Put option setups">
              <span className="sp-stat-label">Flow</span>
              <span className="sp-stat-val mono">
                <span className="sp-up">{totalCalls}C</span>
                <span className="sp-dim">/</span>
                <span className="sp-down">{totalPuts}P</span>
              </span>
            </div>

            <div className="sp-stat-pill" title="Current tab directional bias">
              <span className="sp-stat-label">Bias</span>
              <span className="sp-stat-val mono">
                <span className="sp-up">{bullCount}↑</span>
                <span className="sp-dim">·</span>
                <span className="sp-down">{bearCount}↓</span>
              </span>
            </div>

            {loop.running && (
              <div className="sp-stat-pill sp-stat-pill--live">
                <Loader2 size={12} className="sp-spin" />
                <span className="mono">
                  R{loop.round}
                  {loop.currentCode ? ` · ${loop.currentCode}` : ""}
                </span>
              </div>
            )}

            {tradeDate && (
              <div className="sp-stat-pill sp-stat-pill--date mono">{tradeDate}</div>
            )}
          </div>
        </div>

        <div className="sp-actions">
          {runningCount > 0 && (
            <button
              type="button"
              className="sp-btn sp-btn--stop"
              onClick={() => stopAll.mutate()}
              disabled={stopAll.isPending}
            >
              <Square size={12} /> Stop All
            </button>
          )}
          {tabRunningCount < cards.length && cards.length > 0 && (
            <button
              type="button"
              className="sp-btn sp-btn--secondary"
              onClick={handleStartTab}
              disabled={startMutation.isPending}
            >
              <Play size={12} /> Start {tab === "INDEX" ? "Indices" : "Commodities"}
            </button>
          )}
          <button
            type="button"
            className="sp-btn sp-btn--run"
            onClick={() => startMutation.mutate(undefined)}
            disabled={startMutation.isPending || all.length === 0}
          >
            <Play size={12} /> Start All
          </button>
        </div>
      </div>

      {/* Compact Alerts */}
      {noResearch && (
        <div className="sp-notice" role="alert">
          <AlertTriangle size={14} />
          <span>Research Engine has no data yet. Run the Research Engine first.</span>
        </div>
      )}
      {error && (
        <div className="sp-notice" role="alert">
          <AlertTriangle size={14} />
          <span>Could not load cards: {error.message}</span>
        </div>
      )}
      {loop.lastError && (
        <div className="sp-notice" role="alert">
          <AlertTriangle size={14} />
          <span>Last iteration error: {loop.lastError}</span>
        </div>
      )}

      {/* Cards Grid */}
      {isLoading ? (
        <div className="sp-empty">
          <Loader2 size={22} className="sp-spin sp-loader" />
          <div className="sp-empty-title">Loading instruments…</div>
        </div>
      ) : cards.length === 0 ? (
        <div className="sp-empty">
          <Lightbulb size={26} />
          <div className="sp-empty-title">No {tab.toLowerCase()} underlyings available</div>
          <p className="sp-muted">Run the Research Engine first to evaluate underlyings.</p>
        </div>
      ) : (
        <div className="sp-grid">
          {cards.map((u) => {
            const m = u.master;
            const running = m?.state === "RUNNING";
            const iterating = m !== null && loop.currentMasterId === m.id;
            const isOpen = openCard === u.code;
            const tone =
              u.direction === "BULLISH"
                ? "sp-card--bull"
                : u.direction === "BEARISH"
                ? "sp-card--bear"
                : "";
            const liveCount = m?.liveCount ?? 0;
            const savedTotal = m?.opportunitiesTotal ?? 0;
            const topConf = m?.liveTopConfidence || m?.topConfidence || 0;

            return (
              <div
                key={u.code}
                className={`sp-card ${tone} ${running ? "sp-card--running" : ""} ${
                  iterating ? "sp-card--iterating" : ""
                } ${isOpen ? "sp-card--selected" : ""}`}
                onClick={() => openSheet(u.code)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    openSheet(u.code);
                  }
                }}
              >
                {/* Card Top Header */}
                <div className="sp-card-top">
                  <div className="sp-card-title-group">
                    <div className="sp-symbol-row">
                      <span
                        className={`sp-symbol ${
                          u.type === "INDEX" ? "sp-symbol--index" : "sp-symbol--commodity"
                        }`}
                      >
                        {u.code}
                      </span>
                      <h2 className="sp-name">{UNDERLYING_NAMES[u.code] ?? u.code}</h2>
                      {m && <span className="sp-session-tag mono">S#{m.sessionNo}</span>}
                    </div>
                  </div>

                  <div className="sp-card-badges">
                    {u.score != null && (
                      <span className="sp-score-chip mono" title="Research Opportunity Score">
                        {Number(u.score).toFixed(0)}
                      </span>
                    )}
                    {!u.inResearch ? (
                      <span className="badge badge--amber">UNTRACKED</span>
                    ) : (
                      u.direction && (
                        <span
                          className={`badge ${
                            u.direction === "BULLISH" ? "badge--green" : "badge--red"
                          }`}
                        >
                          {u.direction === "BULLISH" ? (
                            <TrendingUp size={11} />
                          ) : (
                            <TrendingDown size={11} />
                          )}
                          {u.direction}
                        </span>
                      )
                    )}
                    {running ? (
                      <button
                        type="button"
                        className="sp-card-action sp-card-action--stop"
                        onClick={(e) => {
                          e.stopPropagation();
                          stopCard.mutate(m.id);
                        }}
                        disabled={stopCard.isPending}
                        title={`Stop ${u.code}`}
                      >
                        <Square size={11} /> Stop
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="sp-card-action sp-card-action--run"
                        onClick={(e) => {
                          e.stopPropagation();
                          startMutation.mutate({ underlyings: [u.code] });
                        }}
                        disabled={startMutation.isPending}
                        title={`Start ${u.code}`}
                      >
                        <Play size={11} /> Start
                      </button>
                    )}
                  </div>
                </div>

                {/* 4-Column Compact Telemetry Strip */}
                <div className="sp-metrics">
                  <div className="sp-metric-cell">
                    <div className="sp-metric-label">Status</div>
                    <div className="sp-metric-value">
                      {iterating ? (
                        <span className="sp-state-pill sp-state-pill--iterating">
                          <Loader2 size={11} className="sp-spin" /> SCAN
                        </span>
                      ) : running ? (
                        <span className="sp-state-pill sp-state-pill--running">
                          <span className="sp-pulse-dot" /> LIVE
                        </span>
                      ) : m ? (
                        <span className="sp-state-pill sp-state-pill--stopped">
                          {STOP_REASON[m.stopReason ?? ""] ?? "STOP"}
                        </span>
                      ) : (
                        <span className="sp-state-pill sp-state-pill--idle">IDLE</span>
                      )}
                    </div>
                  </div>

                  <div className="sp-metric-cell">
                    <div className="sp-metric-label">Batches</div>
                    <div className="sp-metric-value mono">
                      <span>{m?.iterationsCompleted ?? 0}</span>
                      {m && m.iterationsFailed > 0 && (
                        <span className="sp-fail-tag" title={`${m.iterationsFailed} failed`}>
                          !{m.iterationsFailed}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="sp-metric-cell">
                    <div className="sp-metric-label">Live / Saved</div>
                    <div className="sp-metric-value mono">
                      <span className={liveCount > 0 ? "sp-up" : ""}>{liveCount}</span>
                      <span className="sp-dim">/</span>
                      <span className="sp-muted-num">{savedTotal}</span>
                    </div>
                  </div>

                  <div className="sp-metric-cell">
                    <div className="sp-metric-label">CE / PE · Peak</div>
                    <div className="sp-metric-value mono">
                      <span className="sp-up">{m?.callCount ?? 0}</span>
                      <span className="sp-dim">/</span>
                      <span className="sp-down">{m?.putCount ?? 0}</span>
                      {topConf > 0 && <span className="sp-conf-chip">{topConf}%</span>}
                    </div>
                  </div>
                </div>

                {/* Compact Informative Status Note (only if present) */}
                {(m?.lastError || m?.lastNote) && (
                  <div
                    className={`sp-note-bar ${
                      m?.lastError || m?.lastOpportunityCount === 0 ? "sp-note-bar--warn" : ""
                    }`}
                  >
                    <Activity size={11} className="sp-note-icon" />
                    <span className="sp-note-text">
                      {m.lastError ? `Error: ${m.lastError}` : m.lastNote}
                    </span>
                  </div>
                )}

                {/* Minimal Card Footer */}
                <div className="sp-card-foot">
                  <div className="sp-foot-left">
                    <span className="sp-news-tag">
                      {u.newsStatus ? u.newsStatus.replace(/_/g, " ") : "NO NEWS"}
                    </span>
                    <span className="sp-dot">·</span>
                    <span className="sp-foot-time mono">
                      <Clock size={11} />
                      {m?.lastCompletedAt
                        ? formatDateTime(m.lastCompletedAt)
                        : "Not run today"}
                    </span>
                  </div>

                  <span className="sp-inspect-link">
                    <span>Setups</span>
                    <ChevronRight size={13} />
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Side sheet */}
      {activeCard && (
        <SheetLoader
          card={activeCard}
          isIterating={loop.currentMasterId === (activeCard.master?.id ?? -1)}
          onStart={() => startMutation.mutate({ underlyings: [activeCard.code] })}
          onStop={() => {
            if (activeCard.master) stopCard.mutate(activeCard.master.id);
          }}
          isStarting={startMutation.isPending}
          isStopping={stopCard.isPending}
          onClose={closeSheet}
        />
      )}
    </div>
  );
};
