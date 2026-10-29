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
  resumeSuggestionLoop,
  useStartSuggestion,
  useStopAll,
  useStopCard,
  useSuggestionCards,
  useSuggestionLoop,
} from "../hooks/useSuggestion";
import { formatDateTime } from "../components/formatters";
import { UNDERLYING_NAMES } from "../components/underlyingNames";

type Tab = "INDEX" | "COMMODITY";

const STOP_REASON: Record<string, string> = {
  STOPPED_BY_USER: "Stopped",
  REPLACED_BY_NEW_START: "Replaced by a new start",
  DAY_ENDED: "Day ended",
};

export const SuggestionEnginePage: React.FC = () => {
  const navigate = useNavigate();
  const [tab, setTab] = React.useState<Tab>("INDEX");
  const loop = useSuggestionLoop();
  const { cards: all, hasResearch, tradeDate, isLoading, error, refetch } = useSuggestionCards(loop.running);
  const startMutation = useStartSuggestion();
  const stopCard = useStopCard();
  const stopAll = useStopAll();

  const byType = (t: Tab) => all.filter((u) => u.type === t);
  const cards = byType(tab);
  const runningCount = all.filter((c) => c.master?.state === "RUNNING").length;
  const totalSuggestions = all.reduce((sum, u) => sum + (u.master?.liveCount ?? 0), 0);

  // Sessions still RUNNING in the DB (page reload, another visit) continue as soon as the page is open.
  React.useEffect(() => {
    if (runningCount > 0 && !loop.running) resumeSuggestionLoop();
  }, [runningCount, loop.running]);

  const startResult = startMutation.data;
  const noResearch =
    !hasResearch || (startResult && !startResult.started && startResult.reason === "NO_RESEARCH_DATA");

  return (
    <div className="page-container sp-page">
      <div className="sp-header">
        <div>
          <div className="sp-title-row">
            <h1 className="sp-title">Suggestion Engine</h1>
            {totalSuggestions > 0 && <span className="badge badge--green">{totalSuggestions} Suggestions</span>}
            {loop.running && (
              <span className="badge badge--cyan sp-live">
                <RefreshCw size={12} className="sp-spin" />
                Round {loop.round}
                {loop.currentCode ? ` · ${loop.currentCode}` : " · waiting"}
              </span>
            )}
          </div>
          <p className="sp-desc">
            Each Start opens a new session per card. Cards are iterated one by one from this page; every card keeps
            its own loop count until you stop it. Targets are 5-10% on the premium with a tight stop.
          </p>
        </div>
        <div className="sp-actions">
          <button type="button" className="sp-btn" onClick={() => refetch()} title="Refresh">
            <RefreshCw size={13} className={loop.running ? "sp-spin" : ""} /> Refresh
          </button>
          {runningCount > 0 && (
            <button
              type="button"
              className="sp-btn sp-btn--stop"
              onClick={() => stopAll.mutate()}
              disabled={stopAll.isPending}
            >
              <Square size={14} /> Stop all
            </button>
          )}
          <button
            type="button"
            className="sp-btn sp-btn--run"
            onClick={() => startMutation.mutate(undefined)}
            disabled={startMutation.isPending || all.length === 0}
          >
            <Play size={14} /> Start all
          </button>
        </div>
      </div>

      {noResearch && (
        <div className="sp-notice" role="alert">
          <AlertTriangle size={16} />
          <span>Research Engine has no data yet. Run the Research Engine first, then start suggestions.</span>
        </div>
      )}
      {error && (
        <div className="sp-notice" role="alert">
          <AlertTriangle size={16} />
          <span>Could not load cards: {error.message}</span>
        </div>
      )}
      {loop.lastError && (
        <div className="sp-notice" role="alert">
          <AlertTriangle size={16} />
          <span>Last iteration error: {loop.lastError}</span>
        </div>
      )}

      {loop.running && (
        <div className="sp-progress">
          <Loader2 size={14} className="sp-spin" />
          <span>{loop.currentCode ? `Iterating ${loop.currentCode}` : "Waiting for the next round"}</span>
          <span className="sp-muted">· {runningCount} card(s) running · one card at a time</span>
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
        <div className="sp-muted mono">{tradeDate}</div>
      </div>

      {isLoading ? (
        <div className="sp-empty">
          <RefreshCw size={24} className="sp-spin" />
          <div className="sp-empty-title">Loading cards...</div>
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
            const m = u.master;
            const running = m?.state === "RUNNING";
            const iterating = m !== null && loop.currentMasterId === m.id;
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
                        {u.type}
                        {m ? ` · session #${m.sessionNo} · ${m.suggestionsTotal} saved today` : " · not started today"}
                      </div>
                    </div>
                    {!u.inResearch ? (
                      <span className="badge badge--amber">
                        <AlertTriangle size={13} /> NOT IN RESEARCH
                      </span>
                    ) : (
                      u.direction && (
                        <span className={`badge ${u.direction === "BULLISH" ? "badge--green" : "badge--red"}`}>
                          {u.direction === "BULLISH" ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
                          {u.direction}
                        </span>
                      )
                    )}
                  </div>

                  <div className="sp-metrics">
                    <div>
                      <div className="sp-metric-label">Loops</div>
                      <div className="sp-metric-value">
                        {m?.iterationsCompleted ?? 0}
                        {iterating && <Loader2 size={13} className="sp-spin sp-loader" aria-label="Iterating" />}
                      </div>
                    </div>
                    <div>
                      <div className="sp-metric-label">Live</div>
                      <div className="sp-metric-value">
                        {m?.liveCount ?? 0}
                        {m && m.liveCount > 0 && <span className="sp-dim"> · {m.liveTopConfidence}</span>}
                      </div>
                    </div>
                    <div>
                      <div className="sp-metric-label">Call / Put</div>
                      <div className="sp-metric-value">
                        <span className="sp-up">{m?.callCount ?? 0}</span>
                        <span className="sp-dim"> / </span>
                        <span className="sp-down">{m?.putCount ?? 0}</span>
                      </div>
                    </div>
                  </div>

                  <div className="sp-iterated">
                    <Clock size={12} />
                    <span>
                      {m
                        ? `${running ? (iterating ? "Iterating now · " : "Running · ") : `${STOP_REASON[m.stopReason ?? ""] ?? "Stopped"} · `}` +
                          `Last completed${m.iterationsCompleted ? ` (loop ${m.iterationsCompleted})` : ""}: ${formatDateTime(m.lastCompletedAt)}`
                        : "Not started today"}
                      {m && m.iterationsFailed > 0 ? ` · ${m.iterationsFailed} failed` : ""}
                    </span>
                  </div>
                  {m?.lastError && <div className="sp-note sp-note--warn">Error: {m.lastError}</div>}
                  {m?.lastNote && (
                    <div className={`sp-note ${m.lastSuggestionCount === 0 ? "sp-note--warn" : ""}`}>{m.lastNote}</div>
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
                      onClick={() => stopCard.mutate(m.id)}
                      disabled={stopCard.isPending}
                    >
                      <Square size={13} /> Stop
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="sp-btn sp-btn--run"
                      onClick={() => startMutation.mutate({ underlyings: [u.code] })}
                      disabled={startMutation.isPending}
                      title="Starts a new session for this card"
                    >
                      <Play size={13} /> Start
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
      <p className="sp-muted sp-footnote">
        Iterations run from this browser tab: closing the tab pauses them, reopening the page resumes running cards.
        Prices are re-checked at Trade Lock before any order.
      </p>
    </div>
  );
};
