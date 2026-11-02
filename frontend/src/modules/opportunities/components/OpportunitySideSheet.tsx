import React from "react";
import {
  Activity,
  AlertTriangle,
  ChevronRight,
  Clock,
  Layers,
  Loader2,
  Play,
  Sparkles,
  Square,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react";
import { Opportunity, OpportunityCardItem } from "../types/opportunities.types";
import { formatDateTime } from "./formatters";
import { OpportunityCard } from "./OpportunityCard";
import { UNDERLYING_NAMES } from "./underlyingNames";

interface Batch {
  iterationNo: number;
  items: Opportunity[];
}

interface OpportunitySideSheetProps {
  code: string;
  type: "INDEX" | "COMMODITY";
  card?: OpportunityCardItem;
  iterationsCompleted: number;
  opportunities: Opportunity[];
  isLoading: boolean;
  isIterating: boolean;
  onStart?: () => void;
  onStop?: () => void;
  isStarting?: boolean;
  isStopping?: boolean;
  onClose: () => void;
}

const STOP_REASON_LABEL: Record<string, string> = {
  STOPPED_BY_USER: "Stopped by user",
  REPLACED_BY_NEW_START: "Replaced by new session",
  DAY_ENDED: "Trading day ended",
};

function buildBatches(opportunities: Opportunity[], iterationsCompleted: number): Batch[] {
  const byIter = new Map<number, Opportunity[]>();
  let maxIter = iterationsCompleted;
  for (const s of opportunities) {
    const arr = byIter.get(s.iterationNo) ?? [];
    arr.push(s);
    byIter.set(s.iterationNo, arr);
    if (s.iterationNo > maxIter) {
      maxIter = s.iterationNo;
    }
  }

  const batches: Batch[] = [];
  for (let i = 1; i <= maxIter; i++) {
    const items = (byIter.get(i) ?? []).sort((a, b) => a.rank - b.rank);
    batches.push({ iterationNo: i, items });
  }
  // newest first
  batches.reverse();
  return batches;
}

export const OpportunitySideSheet: React.FC<OpportunitySideSheetProps> = ({
  code,
  type,
  card,
  iterationsCompleted,
  opportunities,
  isLoading,
  isIterating,
  onStart,
  onStop,
  isStarting = false,
  isStopping = false,
  onClose,
}) => {
  const batches = React.useMemo(
    () => buildBatches(opportunities, iterationsCompleted),
    [opportunities, iterationsCompleted]
  );

  const newestIter = batches[0]?.iterationNo ?? (iterationsCompleted > 0 ? iterationsCompleted : null);

  const [openBatch, setOpenBatch] = React.useState<number | null>(newestIter);

  // Auto-open the latest batch when iterationsCompleted changes
  React.useEffect(() => {
    if (newestIter !== null) setOpenBatch(newestIter);
  }, [newestIter]);

  // Close on Escape key
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const name = UNDERLYING_NAMES[code] ?? code;
  const master = card?.master ?? null;
  const isRunning = master?.state === "RUNNING";
  const direction = card?.direction ?? master?.direction ?? null;
  const inResearch = card?.inResearch ?? master?.inResearch ?? true;
  const newsStatus = card?.newsStatus ?? master?.newsStatus ?? null;

  // Derived stats
  const liveCount = master?.liveCount ?? opportunities.filter((s) => !s.expired && s.outcome === "PENDING").length;
  const totalSaved = master?.opportunitiesTotal ?? opportunities.length;
  const callCount = master?.callCount ?? opportunities.filter((s) => s.optionType === "CE").length;
  const putCount = master?.putCount ?? opportunities.filter((s) => s.optionType === "PE").length;
  const bestConfidence =
    master?.liveTopConfidence ||
    master?.topConfidence ||
    (opportunities.length > 0 ? Math.max(...opportunities.map((s) => s.confidence)) : 0);

  return (
    <div className="ss-backdrop" onClick={onClose} role="presentation">
      <div
        className="ss-sheet"
        role="dialog"
        aria-modal="true"
        aria-label={`${code} opportunities`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Terminal Header */}
        <div className="ss-head">
          <div className="ss-head-left">
            <div className="ss-eyebrow">
              <span className={`sp-symbol ${type === "INDEX" ? "sp-symbol--index" : "sp-symbol--commodity"}`}>
                {code}
              </span>
              <h2 className="ss-title">{name}</h2>

              {!inResearch ? (
                <span className="badge badge--amber">
                  <AlertTriangle size={11} /> NOT IN RESEARCH
                </span>
              ) : (
                direction && (
                  <span className={`badge ${direction === "BULLISH" ? "badge--green" : "badge--red"}`}>
                    {direction === "BULLISH" ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                    {direction}
                  </span>
                )
              )}

              {master && (
                <span className={`badge ${isRunning ? "badge--cyan" : "badge--slate"}`}>
                  <Activity size={11} />
                  {isRunning ? (isIterating ? "ITERATING" : "RUNNING") : "STOPPED"}
                </span>
              )}
            </div>

            <div className="ss-subline">
              <span>{type}</span>
              <span className="ss-dot">·</span>
              <span>
                {master
                  ? `Session #${master.sessionNo}`
                  : "No active session today"}
              </span>
              {newsStatus && (
                <>
                  <span className="ss-dot">·</span>
                  <span>
                    News:{" "}
                    <strong className="ss-subline-strong">
                      {newsStatus.replace(/_/g, " ")}
                    </strong>
                  </span>
                </>
              )}
              {card?.score != null && (
                <>
                  <span className="ss-dot">·</span>
                  <span>
                    Research Score:{" "}
                    <strong className="ss-subline-strong mono">
                      {Number(card.score).toFixed(1)}
                    </strong>
                  </span>
                </>
              )}
            </div>
          </div>

          <div className="ss-head-actions">
            {isRunning && onStop && (
              <button
                type="button"
                className="sp-btn sp-btn--stop ss-action-btn"
                onClick={onStop}
                disabled={isStopping}
              >
                <Square size={12} /> Stop
              </button>
            )}
            {!isRunning && onStart && (
              <button
                type="button"
                className="sp-btn sp-btn--run ss-action-btn"
                onClick={onStart}
                disabled={isStarting}
              >
                <Play size={12} /> Start
              </button>
            )}
            <button type="button" className="ss-close" onClick={onClose} aria-label="Close">
              <X size={18} />
            </button>
          </div>
        </div>

        {/* 4-Column Executive Metric Strip */}
        <div className="ss-metrics-strip">
          <div className="ss-metric-cell">
            <div className="ss-metric-label">Loops Completed</div>
            <div className="ss-metric-val">
              <span>{iterationsCompleted}</span>
              {isIterating && <Loader2 size={13} className="sp-spin sp-loader" />}
            </div>
            <div className="ss-metric-sub">
              {master?.iterationsFailed
                ? `${master.iterationsFailed} failed`
                : master
                ? `Session #${master.sessionNo}`
                : "Idle"}
            </div>
          </div>

          <div className="ss-metric-cell">
            <div className="ss-metric-label">Live Contracts</div>
            <div className="ss-metric-val" style={{ color: liveCount > 0 ? "var(--bullish-green)" : "var(--text-heading)" }}>
              {liveCount}
            </div>
            <div className="ss-metric-sub">{totalSaved} saved today</div>
          </div>

          <div className="ss-metric-cell">
            <div className="ss-metric-label">Call / Put Split</div>
            <div className="ss-metric-val">
              <span className="sp-up">{callCount} CE</span>
              <span className="sp-dim"> / </span>
              <span className="sp-down">{putCount} PE</span>
            </div>
            <div className="ss-metric-sub">Option flow balance</div>
          </div>

          <div className="ss-metric-cell">
            <div className="ss-metric-label">Peak Setup Score</div>
            <div
              className="ss-metric-val"
              style={{
                color:
                  bestConfidence >= 75
                    ? "var(--bullish-green)"
                    : bestConfidence >= 55
                    ? "var(--cyan)"
                    : "var(--text-muted)",
              }}
            >
              {bestConfidence > 0 ? `${bestConfidence.toFixed(1)}` : "—"}
            </div>
            <div className="ss-metric-sub">Out of 100.0</div>
          </div>
        </div>

        {/* Live Status & Diagnostics Strip */}
        <div className="ss-meta">
          <div className="ss-meta-row">
            {isIterating ? (
              <span className="ss-running">
                <Loader2 size={13} className="sp-spin" />
                <span>Evaluating option chain &amp; generating loop #{iterationsCompleted + 1}…</span>
              </span>
            ) : (
              <span className="ss-muted">
                <Clock size={13} />
                <span>
                  {master
                    ? `${
                        isRunning
                          ? "Active session · "
                          : `${STOP_REASON_LABEL[master.stopReason ?? ""] ?? "Stopped"} · `
                      }Last loop: ${formatDateTime(master.lastCompletedAt)}`
                    : `${iterationsCompleted} loop${iterationsCompleted !== 1 ? "s" : ""} completed today`}
                </span>
              </span>
            )}

            {master?.lastDurationMs != null && (
              <span className="ss-duration mono">
                {(master.lastDurationMs / 1000).toFixed(1)}s
              </span>
            )}
          </div>

          {master?.lastError && (
            <div className="ss-alert ss-alert--error">
              <AlertTriangle size={13} />
              <span>Error: {master.lastError}</span>
            </div>
          )}

          {master?.lastNote && !master?.lastError && (
            <div className={`ss-alert ${master.lastOpportunityCount === 0 ? "ss-alert--warn" : "ss-alert--info"}`}>
              <Sparkles size={13} />
              <span>{master.lastNote}</span>
            </div>
          )}
        </div>

        {/* Scrollable Body */}
        <div className="ss-body">
          {isLoading ? (
            <div className="ss-center">
              <Loader2 size={26} className="sp-spin sp-loader" />
              <div className="ss-center-title">Loading {code} opportunities…</div>
              <span className="ss-center-sub">Fetching per-loop option contract batches</span>
            </div>
          ) : batches.length === 0 ? (
            <div className="ss-center">
              <div className="ss-empty-icon">
                <Clock size={26} />
              </div>
              <div className="ss-center-title">No iterations executed for {code} yet</div>
              <p className="ss-center-sub">
                Start this card to scan live option chains, evaluate Greeks &amp; risk-reward levels, and generate per-loop contract opportunities.
              </p>
              {onStart && !isRunning && (
                <button
                  type="button"
                  className="sp-btn sp-btn--run ss-empty-cta"
                  onClick={onStart}
                  disabled={isStarting}
                >
                  <Play size={14} /> Start {code} Engine
                </button>
              )}
            </div>
          ) : (
            <>
              <div className="ss-section-bar">
                <div className="ss-section-title">
                  <Layers size={13} />
                  <span>Iteration History ({batches.length} {batches.length === 1 ? "Loop" : "Loops"})</span>
                </div>
                <span className="ss-section-hint">Click any loop to inspect contracts</span>
              </div>

              <div className="ss-batches">
                {batches.map((batch, idx) => {
                  const isOpen = openBatch === batch.iterationNo;
                  const hasItems = batch.items.length > 0;
                  const isLatestBatch = idx === 0;
                  const batchCalls = batch.items.filter((i) => i.optionType === "CE").length;
                  const batchPuts = batch.items.filter((i) => i.optionType === "PE").length;
                  const batchTopScore = hasItems
                    ? Math.max(...batch.items.map((i) => i.confidence))
                    : null;
                  const batchTime = batch.items[0]?.createdAt;

                  return (
                    <div
                      key={batch.iterationNo}
                      className={`ss-batch ${isOpen ? "ss-batch--open" : ""} ${
                        hasItems ? "ss-batch--has-items" : "ss-batch--empty"
                      }`}
                    >
                      <button
                        type="button"
                        className="ss-batch-header"
                        onClick={() => setOpenBatch(isOpen ? null : batch.iterationNo)}
                      >
                        <div className="ss-batch-left">
                          <ChevronRight size={15} className="ss-chevron" />
                          <span className="ss-batch-label">LOOP #{batch.iterationNo}</span>

                          {isLatestBatch && (
                            <span className="badge badge--blue">LATEST</span>
                          )}

                          {hasItems ? (
                            <span className="badge badge--green ss-batch-count">
                              {batch.items.length} {batch.items.length === 1 ? "CONTRACT" : "CONTRACTS"}
                            </span>
                          ) : (
                            <span className="badge badge--slate ss-batch-empty">
                              0 CONTRACTS
                            </span>
                          )}

                          {hasItems && (
                            <span className="ss-batch-split mono">
                              <span className="sp-up">{batchCalls}CE</span>
                              <span className="sp-dim">/</span>
                              <span className="sp-down">{batchPuts}PE</span>
                            </span>
                          )}
                        </div>

                        <div className="ss-batch-right">
                          {batchTopScore !== null && (
                            <span className="ss-batch-score mono">
                              <Sparkles size={11} /> {batchTopScore.toFixed(1)}
                            </span>
                          )}
                          {batchTime && (
                            <span className="ss-batch-time mono">
                              {formatDateTime(batchTime)}
                            </span>
                          )}
                          {!hasItems && (
                            <span className="ss-batch-warn" title="No executable contracts in this loop">
                              <AlertTriangle size={14} />
                            </span>
                          )}
                        </div>
                      </button>

                      {isOpen && (
                        <div className="ss-batch-body">
                          {hasItems ? (
                            batch.items.map((s) => (
                              <OpportunityCard key={s.id} opportunity={s} />
                            ))
                          ) : (
                            <div className="ss-empty-batch">
                              <AlertTriangle size={15} />
                              <span>
                                Loop #{batch.iterationNo} completed without finding option contracts meeting minimum confidence and R:R thresholds.
                              </span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

