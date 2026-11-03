import React, { useState, useMemo, useEffect } from "react";
import {
  Activity,
  AlertTriangle,
  ChevronRight,
  LayoutGrid,
  List,
  Loader2,
  Play,
  Sparkles,
  Square,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react";
import {
  Opportunity,
  OpportunityCardItem,
  OpportunityCheckItem,
  OpportunityIteration,
} from "../types/opportunities.types";
import { useCheckOpportunity } from "../hooks/useOpportunities";
import { BatchDiagnostics, ResultBadge } from "./BatchDiagnostics";
import {
  formatDateTime,
  formatExpiry,
  formatRupee,
  getMoneyness,
} from "./formatters";
import { OpportunityCard } from "./OpportunityCard";
import { OpportunityCheckChart } from "./OpportunityCheckChart";
import { LOT_SIZES, UNDERLYING_NAMES } from "./underlyingNames";

interface Batch {
  iterationNo: number;
  items: Opportunity[];
  diag: OpportunityIteration | null;
}

interface OpportunitySideSheetProps {
  code: string;
  type: "INDEX" | "COMMODITY";
  card?: OpportunityCardItem;
  iterationsCompleted: number;
  opportunities: Opportunity[];
  iterations?: OpportunityIteration[];
  isLoading: boolean;
  isIterating: boolean;
  onStart?: () => void;
  onStop?: () => void;
  isStarting?: boolean;
  isStopping?: boolean;
  onClose: () => void;
}

type ViewMode = "CARDS" | "TABLE";


function buildBatches(
  opportunities: Opportunity[],
  iterationsCompleted: number,
  iterations: OpportunityIteration[],
): Batch[] {
  // newest diagnostics row per batch number (a failed batch is retried under the same number)
  const diagByIter = new Map<number, OpportunityIteration>();
  for (const it of iterations) {
    const cur = diagByIter.get(it.iterationNo);
    if (!cur || it.id > cur.id) diagByIter.set(it.iterationNo, it);
    if (it.result !== "ERROR" && it.result !== "DATA_ERROR" && it.iterationNo > iterationsCompleted) {
      iterationsCompleted = it.iterationNo;
    }
  }
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
    batches.push({ iterationNo: i, items, diag: diagByIter.get(i) ?? null });
  }
  // newest loop first
  batches.reverse();
  return batches;
}

export const OpportunitySideSheet: React.FC<OpportunitySideSheetProps> = ({
  code,
  type,
  card,
  iterationsCompleted,
  opportunities,
  iterations = [],
  isLoading,
  isIterating,
  onStart,
  onStop,
  isStarting = false,
  isStopping = false,
  onClose,
}) => {
  const [viewMode, setViewMode] = useState<ViewMode>("CARDS");
  const [checkedItems, setCheckedItems] = useState<Record<number, OpportunityCheckItem>>({});
  const [checkingOppId, setCheckingOppId] = useState<number | null>(null);
  const checkOppMutation = useCheckOpportunity();

  const handleCheckOpportunity = (opportunityId: number) => {
    setCheckingOppId(opportunityId);
    checkOppMutation.mutate(opportunityId, {
      onSuccess: (res) => {
        setCheckedItems((prev) => ({
          ...prev,
          [res.opportunityId]: res,
        }));
      },
      onSettled: () => setCheckingOppId(null),
    });
  };

  const batches = useMemo(
    () => buildBatches(opportunities, iterationsCompleted, iterations),
    [opportunities, iterationsCompleted, iterations]
  );

  const newestIter = batches[0]?.iterationNo ?? (iterationsCompleted > 0 ? iterationsCompleted : null);
  const [openBatch, setOpenBatch] = useState<number | null>(newestIter);

  useEffect(() => {
    if (newestIter !== null) setOpenBatch(newestIter);
  }, [newestIter]);

  // Close on Escape key
  useEffect(() => {
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
  const lotSize = LOT_SIZES[code] ?? 25;

  // Derived stats
  const liveCount =
    master?.liveCount ?? opportunities.filter((s) => !s.expired && s.outcome === "PENDING").length;
  const totalSaved = master?.opportunitiesTotal ?? opportunities.length;
  const callCount = master?.callCount ?? opportunities.filter((s) => s.optionType === "CE").length;
  const putCount = master?.putCount ?? opportunities.filter((s) => s.optionType === "PE").length;
  const totalFlow = callCount + putCount;
  const callPct = totalFlow > 0 ? Math.round((callCount / totalFlow) * 100) : 50;
  const putPct = totalFlow > 0 ? 100 - callPct : 50;

  const bestConfidence =
    master?.liveTopConfidence ||
    master?.topConfidence ||
    (opportunities.length > 0 ? Math.max(...opportunities.map((s) => s.confidence)) : 0);

  const bestRewardRisk =
    opportunities.length > 0 ? Math.max(...opportunities.map((s) => s.rewardRisk || 0)) : 0;

  // Extract distinct active strikes
  const activeStrikes = useMemo(() => {
    const map = new Map<string, { strike: number; optionType: "CE" | "PE"; count: number }>();
    for (const op of opportunities) {
      const key = `${op.strike}_${op.optionType}`;
      const existing = map.get(key);
      if (existing) {
        existing.count += 1;
      } else {
        map.set(key, { strike: op.strike, optionType: op.optionType, count: 1 });
      }
    }
    return Array.from(map.values()).slice(0, 5);
  }, [opportunities]);

  return (
    <div className="ss-backdrop" onClick={onClose} role="presentation">
      <div
        className="ss-sheet"
        role="dialog"
        aria-modal="true"
        aria-label={`${code} opportunities console`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── 1. Top Terminal Header Bar ── */}
        <div className="ss-head">
          <div className="ss-head-left">
            <div className="ss-eyebrow">
              <span className={`sp-symbol ${type === "INDEX" ? "sp-symbol--index" : "sp-symbol--commodity"}`}>
                {code}
              </span>
              <h2 className="ss-title">{name}</h2>

              {/* Direction Bias Pill */}
              {!inResearch ? (
                <span className="badge badge--amber">
                  <AlertTriangle size={11} /> UNTRACKED
                </span>
              ) : (
                direction && (
                  <span
                    className={`badge ${
                      direction === "BULLISH"
                        ? "badge--green"
                        : direction === "BEARISH"
                        ? "badge--red"
                        : "badge--slate"
                    }`}
                  >
                    {direction === "BULLISH" ? (
                      <TrendingUp size={11} />
                    ) : direction === "BEARISH" ? (
                      <TrendingDown size={11} />
                    ) : null}
                    {direction} BIAS
                  </span>
                )
              )}

              {/* Scanner Status Badge */}
              <span className={`badge ${isRunning ? "badge--cyan" : "badge--slate"}`}>
                <Activity size={11} />
                {isRunning ? (isIterating ? "EVALUATING CHAIN" : "SCANNER ACTIVE") : "PAUSED"}
              </span>

              {master && (
                <span className="badge badge--blue mono">
                  SESSION #{master.sessionNo}
                </span>
              )}
            </div>

            <div className="ss-subline">
              <span>{type === "INDEX" ? "Index Derivatives" : "Commodity Futures & Options"}</span>
              <span className="ss-dot">·</span>
              <span className="mono">1 Lot = {lotSize} Qty</span>
              {card?.score != null && (
                <>
                  <span className="ss-dot">·</span>
                  <span>
                    Research Score:{" "}
                    <strong className="ss-subline-strong mono">
                      {Number(card.score).toFixed(1)}/100
                    </strong>
                  </span>
                </>
              )}
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
                <Square size={12} />
                <span>{isStopping ? "Stopping..." : "Stop Engine"}</span>
              </button>
            )}
            {!isRunning && onStart && (
              <button
                type="button"
                className="sp-btn sp-btn--run ss-action-btn"
                onClick={onStart}
                disabled={isStarting}
              >
                <Play size={12} />
                <span>{isStarting ? "Starting..." : "Start Engine"}</span>
              </button>
            )}
            <button
              type="button"
              className="ss-close"
              onClick={onClose}
              aria-label="Close opportunity console"
            >
              <X size={17} />
            </button>
          </div>
        </div>

        {/* ── 2. Compact Single-Line Telemetry & Controls Strip ── */}
        <div className="ss-compact-bar">
          <div className="ss-compact-metrics">
            <div className="ss-kpi-item">
              <span className="ss-kpi-label">BATCHES</span>
              <span className="ss-kpi-val mono">
                {iterationsCompleted}
                {isIterating && <Loader2 size={11} className="sp-spin sp-loader" />}
              </span>
              {master?.lastDurationMs != null && (
                <span className="ss-kpi-sub mono">{(master.lastDurationMs / 1000).toFixed(1)}s</span>
              )}
            </div>

            <span className="ss-kpi-sep" />

            <div className="ss-kpi-item">
              <span className="ss-kpi-label">SETUPS</span>
              <span className="ss-kpi-val mono">
                <span className={liveCount > 0 ? "sp-up" : ""}>{liveCount} Live</span>
                <span className="ss-kpi-dim">/</span>
                <span className="ss-kpi-sub">{totalSaved} Total</span>
              </span>
            </div>

            <span className="ss-kpi-sep" />

            <div className="ss-kpi-item">
              <span className="ss-kpi-label">FLOW</span>
              <span className="ss-kpi-val mono">
                <span className="sp-up">{callCount}CE</span>
                <span className="ss-kpi-dim">·</span>
                <span className="sp-down">{putCount}PE</span>
              </span>
              <div className="ss-mini-flow" title={`Calls: ${callPct}% | Puts: ${putPct}%`}>
                <div className="ss-flow-ce" style={{ width: `${callPct}%` }} />
                <div className="ss-flow-pe" style={{ width: `${putPct}%` }} />
              </div>
            </div>

            <span className="ss-kpi-sep" />

            <div className="ss-kpi-item">
              <span className="ss-kpi-label">PEAK EDGE</span>
              <span
                className="ss-kpi-val mono"
                style={{
                  color:
                    bestConfidence >= 75
                      ? "var(--bullish-green)"
                      : bestConfidence >= 55
                      ? "var(--cyan)"
                      : "var(--text-heading)",
                }}
              >
                {bestConfidence > 0 ? bestConfidence.toFixed(1) : "—"}
              </span>
              {bestRewardRisk > 0 && (
                <span className="ss-kpi-rr mono">1:{bestRewardRisk.toFixed(1)}</span>
              )}
            </div>

            {activeStrikes.length > 0 && (
              <>
                <span className="ss-kpi-sep" />
                <div className="ss-inline-strikes">
                  {activeStrikes.map((st, i) => (
                    <span
                      key={i}
                      className={`ss-strike-chip mono ${st.optionType === "CE" ? "is-ce" : "is-pe"}`}
                    >
                      {st.strike.toLocaleString("en-IN")} {st.optionType}
                      {st.count > 1 && <span className="ss-strike-count">×{st.count}</span>}
                    </span>
                  ))}
                </div>
              </>
            )}
          </div>

          <div className="ss-view-toggle">
            <button
              type="button"
              className={`ss-view-btn ${viewMode === "CARDS" ? "is-active" : ""}`}
              onClick={() => setViewMode("CARDS")}
              title="Detailed Trade Cards View"
            >
              <LayoutGrid size={12} />
              <span>Cards</span>
            </button>
            <button
              type="button"
              className={`ss-view-btn ${viewMode === "TABLE" ? "is-active" : ""}`}
              onClick={() => setViewMode("TABLE")}
              title="High-Density Terminal Matrix View"
            >
              <List size={12} />
              <span>Matrix</span>
            </button>
          </div>
        </div>

        {/* Slim inline status alert only when error or important note */}
        {master?.lastError && (
          <div className="ss-notice ss-notice--error">
            <AlertTriangle size={12} />
            <span>Batch Error: {master.lastError}</span>
          </div>
        )}

        {/* ── 5. Scrollable Body: Batches & Contracts ── */}
        <div className="ss-body">
          {isLoading ? (
            <div className="ss-empty-state">
              <Loader2 size={28} className="sp-spin sp-loader" />
              <div className="ss-empty-title">Loading {code} opportunity chain…</div>
              <p className="ss-empty-sub">Fetching option chain snapshots and rule evaluations.</p>
            </div>
          ) : batches.length === 0 ? (
            /* 3-Step Educational / Actionable Empty State */
            <div className="ss-how-it-works-card">
              <div className="ss-how-head">
                <Sparkles size={16} style={{ color: "var(--kite-blue)" }} />
                <div>
                  <h3 className="ss-how-title">{code} Opportunity Scanning Engine</h3>
                  <p className="ss-how-desc">
                    Continuously evaluates live option contracts for {name} and generates actionable entry/exit levels.
                  </p>
                </div>
              </div>

              <div className="ss-steps-grid">
                <div className="ss-step-box">
                  <div className="ss-step-num mono">01</div>
                  <h4 className="ss-step-heading">Chain Evaluation</h4>
                  <p className="ss-step-text">
                    Scans live strike premiums, volume, open interest, and Delta/Gamma profiles around current spot price.
                  </p>
                </div>

                <div className="ss-step-box">
                  <div className="ss-step-num mono">02</div>
                  <h4 className="ss-step-heading">Directional Edge</h4>
                  <p className="ss-step-text">
                    Cross-references setups with research momentum, technical indicators, and intraday price structure.
                  </p>
                </div>

                <div className="ss-step-box">
                  <div className="ss-step-num mono">03</div>
                  <h4 className="ss-step-heading">Defined Risk Plan</h4>
                  <p className="ss-step-text">
                    Calculates exact entry zone, invalidation stop loss, target 1 &amp; 2, and 1:X reward-risk ratios.
                  </p>
                </div>
              </div>

              {onStart && !isRunning && (
                <div className="ss-how-action">
                  <button
                    type="button"
                    className="sp-btn sp-btn--run"
                    onClick={onStart}
                    disabled={isStarting}
                    style={{ padding: "8px 18px", fontSize: "0.82rem" }}
                  >
                    <Play size={14} /> Start {code} Scanning Engine
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="ss-batches-list">
              {batches.map((batch, idx) => {
                const isOpen = openBatch === batch.iterationNo;
                const filteredItems = batch.items;
                const hasOriginalItems = batch.items.length > 0;
                const isLatestBatch = idx === 0;
                const batchCalls = batch.items.filter((i) => i.optionType === "CE").length;
                const batchPuts = batch.items.filter((i) => i.optionType === "PE").length;
                const batchTopScore = hasOriginalItems
                  ? Math.max(...batch.items.map((i) => i.confidence))
                  : null;
                const batchTime = batch.items[0]?.createdAt;

                return (
                  <div
                    key={batch.iterationNo}
                    className={`ss-batch ${isOpen ? "is-open" : ""} ${
                      hasOriginalItems ? "has-items" : "is-empty"
                    }`}
                  >
                    {/* Batch Accordion Header */}
                    <button
                      type="button"
                      className="ss-batch-header"
                      onClick={() => setOpenBatch(isOpen ? null : batch.iterationNo)}
                      aria-expanded={isOpen}
                    >
                      <div className="ss-batch-left">
                        <ChevronRight size={14} className="ss-chevron" />
                        <span className="ss-batch-tag mono">BATCH #{batch.iterationNo}</span>

                        {isLatestBatch && (
                          <span className="badge badge--blue">LATEST</span>
                        )}

                        {batch.diag && !hasOriginalItems && <ResultBadge result={batch.diag.result} />}

                        {hasOriginalItems ? (
                          <span className="badge badge--green">
                            {batch.items.length} {batch.items.length === 1 ? "SET-UP" : "SET-UPS"}
                          </span>
                        ) : (
                          <span className="badge badge--slate">0 SET-UPS</span>
                        )}

                        {hasOriginalItems && (
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
                            <Sparkles size={11} /> {batchTopScore.toFixed(1)} Peak
                          </span>
                        )}
                        {batchTime && (
                          <span className="ss-batch-time mono">
                            {formatDateTime(batchTime)}
                          </span>
                        )}
                      </div>
                    </button>

                    {/* Batch Content */}
                    {isOpen && (
                      <div className="ss-batch-body">
                        {batch.diag && <BatchDiagnostics iteration={batch.diag} />}
                        {!hasOriginalItems ? (
                          !batch.diag && (
                            <div className="ss-empty-batch">
                              <AlertTriangle size={15} />
                              <span>
                                Batch #{batch.iterationNo} completed without opportunities (no diagnostics were recorded
                                for this batch).
                              </span>
                            </div>
                          )
                        ) : viewMode === "CARDS" ? (
                          /* ── Cards View ── */
                          <div className="ss-cards-stack">
                            {filteredItems.map((s) => (
                              <OpportunityCard
                                key={s.id}
                                opportunity={s}
                                checkResult={checkedItems[s.id]}
                                isChecking={checkingOppId === s.id}
                                onCheck={handleCheckOpportunity}
                                defaultExpanded={isLatestBatch}
                              />
                            ))}
                          </div>
                        ) : (
                          /* ── High-Density Terminal Table / Matrix View ── */
                          <div className="ss-table-card">
                            <table className="table ss-matrix-table">
                              <thead>
                                <tr>
                                  <th>Rank</th>
                                  <th>Contract</th>
                                  <th>Type</th>
                                  <th>Moneyness</th>
                                  <th className="text-right">Entry</th>
                                  <th className="text-right">Stop Loss</th>
                                  <th className="text-right">Target</th>
                                  <th className="text-right">R:R</th>
                                  <th className="text-right">Edge Score</th>
                                  <th className="text-right">Tested %</th>
                                  <th>Status</th>
                                  <th className="text-right">Action</th>
                                </tr>
                              </thead>
                              <tbody>
                                {filteredItems.map((item) => {
                                  const isCall = item.optionType === "CE";
                                  const m = getMoneyness(item.spot, item.strike, item.optionType);
                                  const chk = checkedItems[item.id];
                                  const isCheckingRow = checkingOppId === item.id;
                                  return (
                                    <React.Fragment key={item.id}>
                                      <tr>
                                        <td className="mono font-bold">#{item.rank}</td>
                                        <td>
                                          <div className="ss-matrix-contract">
                                            <span className="mono font-bold">
                                              {item.strike.toLocaleString("en-IN")} {item.optionType}
                                            </span>
                                            <span className="ss-matrix-exp mono">
                                              {formatExpiry(item.expiry)}
                                            </span>
                                          </div>
                                        </td>
                                        <td>
                                          <span className={`badge ${isCall ? "badge--green" : "badge--red"}`}>
                                            {isCall ? "CALL" : "PUT"}
                                          </span>
                                        </td>
                                        <td>
                                          <span className="oc-moneyness-tag is-atm mono">
                                            {m.diffFormatted}
                                          </span>
                                        </td>
                                        <td className="text-right mono font-bold">
                                          {formatRupee(item.entry)}
                                        </td>
                                        <td className="text-right mono neg">
                                          {formatRupee(item.stop)}
                                        </td>
                                        <td className="text-right mono pos">
                                          {formatRupee(item.target)}
                                        </td>
                                        <td className="text-right mono">
                                          1 : {item.rewardRisk.toFixed(2)}
                                        </td>
                                        <td className="text-right mono font-bold" style={{ color: "var(--cyan)" }}>
                                          {item.confidence.toFixed(1)}
                                        </td>
                                        <td
                                          className={`text-right mono font-bold ${
                                            chk
                                              ? chk.achievedPct >= 100
                                                ? "pos"
                                                : chk.achievedPct < 0
                                                ? "neg"
                                                : ""
                                              : ""
                                          }`}
                                        >
                                          {chk
                                            ? chk.achievedPct >= 100
                                              ? "100%"
                                              : `${chk.achievedPct > 0 ? "+" : ""}${chk.achievedPct.toFixed(1)}%`
                                            : "—"}
                                        </td>
                                        <td>
                                          <span
                                            className={`badge ${
                                              item.outcome === "TARGET_HIT"
                                                ? "badge--green"
                                                : item.outcome === "STOP_HIT"
                                                ? "badge--red"
                                                : item.expired
                                                ? "badge--slate"
                                                : "badge--blue"
                                            }`}
                                          >
                                            {item.outcome === "PENDING" && !item.expired
                                              ? "ACTIVE"
                                              : item.outcome}
                                          </span>
                                        </td>
                                        <td className="text-right">
                                          <button
                                            type="button"
                                            className={`oc-check-btn ${chk ? "oc-check-btn--done" : ""}`}
                                            onClick={() => handleCheckOpportunity(item.id)}
                                            disabled={isCheckingRow}
                                          >
                                            {isCheckingRow ? (
                                              <Loader2 size={11} className="sp-spin" />
                                            ) : (
                                              <Activity size={11} />
                                            )}
                                            <span>{chk ? "Re-check" : "Check Result"}</span>
                                          </button>
                                        </td>
                                      </tr>
                                      {chk && (
                                        <tr>
                                          <td colSpan={12} style={{ padding: 0 }}>
                                            <OpportunityCheckChart checkResult={chk} />
                                          </td>
                                        </tr>
                                      )}
                                    </React.Fragment>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
