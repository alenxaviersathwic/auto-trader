import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  History,
  Loader2,
  Lock,
  Play,
  Power,
  Radio,
  Sparkles,
  Square,
  Zap,
} from "lucide-react";
import { useLockSessionPick, useSessionDetail, useUpdateSession } from "../hooks/useSessions";
import { useSessionLoop } from "../hooks/useSessionLoop";
import { sessionsQueryKeys } from "../queryKeys/sessionsQueryKeys";
import { TradeLockModal } from "../components/TradeLockModal";
import { SuggestionCard } from "../components/SuggestionCard";
import { ManagerCard } from "../components/ManagerCard";
import { BatchHistory } from "../components/BatchHistory";
import { RunningTradeCard } from "../components/RunningTradeCard";
import { SessionTradesPanel } from "../components/SessionTradesPanel";
import { AutopsyAgentPanel } from "../components/AutopsyAgentPanel";
import { RISK_LEVELS, RISK_META } from "../components/riskLevels";
import { useTradeSearch } from "../../trades/hooks/useTrades";
import { tradesQueryKeys } from "../../trades/queryKeys/tradesQueryKeys";
import {
  TRADER_CODES,
  TRADER_META,
  normalizeTraderCode,
  normalizeTraderCodes,
  traderForStrategy,
} from "../../trades/components/traderMeta";
import { TraderCode } from "../../trades/types/trades.types";
import { useAutopsies } from "../../learning/hooks/useLearning";
import { learningQueryKeys } from "../../learning/queryKeys/learningQueryKeys";
import { formatRupee, formatSignedRupee } from "../../opportunities/components/formatters";
import {
  resumeOpportunityLoop,
  useOpportunityCards,
  useOpportunityLoop,
  useStartOpportunity,
  useStopAll,
} from "../../opportunities/hooks/useOpportunities";
import { RiskLevel, SessionLoopStateName, SessionPick } from "../types/sessions.types";

const LOCK_FAILURE_MS = 6000;
const LIVE_REFRESH_MS = 2000;
const IDLE_REFRESH_MS = 15000;

const STATE_COPY: Record<SessionLoopStateName, string> = {
  SCHEDULED: "Waiting for the session start time",
  WAITING: "Both traders are watching; nothing passes its checks yet",
  PICK_READY: "Setups are open",
  HALTED: "Halted: a loss limit was reached",
  SESSION_CLOSED: "This session is closed",
  UNSUPPORTED_TYPE: "This session type has no loop yet",
};

const hhmm = (iso: string): string =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });

const pickTrader = (p: SessionPick): TraderCode => normalizeTraderCode(p.traderCode) ?? traderForStrategy(p.strategy);

type Tab = "CURRENT" | "HISTORY";

/**
 * The session screen, laid out like trading-engine's session desk: header with the session controls, a stat row,
 * then the session manager's best suggestion with Current / History tabs on the left and running trades, session
 * trades and the autopsy agent on the right.
 */
export const SessionDetailPage: React.FC = () => {
  const { id } = useParams({ strict: false }) as { id: string };
  const navigate = useNavigate({ from: "/sessions/$id" });
  const queryClient = useQueryClient();
  const sessionId = Number(id);

  const { data: session, isLoading } = useSessionDetail(sessionId);
  const isActive = !!session && session.sessionStatus === "ACTIVE";
  const loop = useSessionLoop(sessionId, isActive);
  const hasLiveTrades = (loop.data?.capital.activeTradeIds ?? []).length > 0;
  const trades = useTradeSearch(
    { page: 0, limit: 25, sortBy: "createdAt", sortDir: "desc", sessionId },
    hasLiveTrades ? LIVE_REFRESH_MS : IDLE_REFRESH_MS,
  );
  const autopsies = useAutopsies({ page: 0, limit: 50, sortBy: "createdAt", sortDir: "desc", sessionId }, IDLE_REFRESH_MS);
  const lockMutation = useLockSessionPick(sessionId);
  const updateMutation = useUpdateSession();

  // The scanner creates the opportunities this session picks from; the session never calls the engine itself.
  const oppLoop = useOpportunityLoop();
  const { cards: oppCards, hasResearch, isLoading: oppCardsLoading } = useOpportunityCards(oppLoop.running);
  const startScanner = useStartOpportunity();
  const stopScanner = useStopAll();
  const autoStartedScannerRef = useRef<boolean>(false);

  const [tab, setTab] = useState<Tab>("CURRENT");
  const [focusPickId, setFocusPickId] = useState<number | null>(null);
  const [lockedPick, setLockedPick] = useState<SessionPick | null>(null);
  const [lockFailure, setLockFailure] = useState<string | null>(null);
  const failureTimer = useRef<number | undefined>(undefined);

  const pickIds = (loop.data?.picks ?? []).map((p) => p.id).join(",");
  const activeTradeIdsKey = (loop.data?.capital.activeTradeIds ?? []).join(",");
  const lockedPicksKey = (loop.data?.lockedPicks ?? []).map((p) => p.id).join(",");

  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: sessionsQueryKeys.batches(sessionId) });
    queryClient.invalidateQueries({ queryKey: tradesQueryKeys.lists() });
    // a trade that just closed has a fresh autopsy and may have changed a scorecard
    queryClient.invalidateQueries({ queryKey: learningQueryKeys.all });
  }, [pickIds, activeTradeIdsKey, lockedPicksKey, sessionId, queryClient]);

  useEffect(() => () => window.clearTimeout(failureTimer.current), []);

  useEffect(() => {
    if (focusPickId === null) return;
    const t = window.setTimeout(() => {
      document.getElementById(`pick-${focusPickId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 50);
    return () => window.clearTimeout(t);
  }, [focusPickId]);

  // Resume or start the scanner for this session's underlyings when an ACTIVE session is opened.
  useEffect(() => {
    if (!session || session.sessionStatus !== "ACTIVE" || oppCardsLoading) return;
    const codes = session.scope === "INDEX" ? session.underlyings : session.commodityItems;
    if (!codes || codes.length === 0) return;
    const running = oppCards.filter((c) => codes.includes(c.code) && c.master?.state === "RUNNING");
    if (running.length > 0) {
      if (!oppLoop.running) resumeOpportunityLoop();
      return;
    }
    if (!autoStartedScannerRef.current && hasResearch && !startScanner.isPending) {
      autoStartedScannerRef.current = true;
      startScanner.mutate({ underlyings: codes });
    }
  }, [session, oppCards, oppCardsLoading, oppLoop.running, hasResearch, startScanner]);

  const handleLock = (pid: number) => {
    lockMutation.mutate(pid, {
      onSuccess: (locked) => setLockedPick(locked),
      onError: (err) => {
        setLockFailure(err instanceof Error ? err.message : "Trade lock failed");
        window.clearTimeout(failureTimer.current);
        failureTimer.current = window.setTimeout(() => setLockFailure(null), LOCK_FAILURE_MS);
      },
    });
  };

  if (isLoading || !session) {
    return <div className="te-empty">Loading trading session #{id}…</div>;
  }

  const underlyings = session.scope === "INDEX" ? session.underlyings : session.commodityItems;
  const scannersRunning = oppCards.filter((c) => underlyings.includes(c.code) && c.master?.state === "RUNNING").length;
  const noResearchData =
    !hasResearch ||
    (startScanner.data && !startScanner.data.started && startScanner.data.reason === "NO_RESEARCH_DATA");
  const activeTraders = normalizeTraderCodes(session.traders);
  const riskLevel: RiskLevel = session.riskLevel ?? "HIGH";
  const data = loop.data;
  const picks = data?.picks ?? [];
  const lockedPicks = data?.lockedPicks ?? [];
  const allTrades = trades.data?.list ?? [];
  const running = allTrades.filter((t) => t.tradeState === "RUNNING");
  const closed = allTrades.filter((t) => t.tradeState === "EXITED");
  const wins = closed.filter((t) => t.netPnl > 0).length;
  const autopsyList = autopsies.data?.list ?? [];
  const autopsyByTrade = new Map(autopsyList.map((a) => [a.tradeId, a]));
  const excluded = Object.entries(data?.scanned.excluded ?? {});
  const bestId = data?.manager?.pickId ?? null;

  const cap = data?.capital;
  const maxLoss = (session.capital * session.maxLossPercentage) / 100;
  const budgetLeft = cap?.remainingLossBudget ?? maxLoss;
  const budgetPct = maxLoss > 0 ? Math.min(100, (budgetLeft / maxLoss) * 100) : 0;
  const realized = cap?.realizedPnl ?? session.realizedPnl;
  const stateTitle = !isActive ? STATE_COPY.SESSION_CLOSED : data ? STATE_COPY[data.state] : STATE_COPY.WAITING;
  const stateMessage = data?.message ?? "Waiting for the first loop tick.";

  const update = (payload: Parameters<typeof updateMutation.mutate>[0]["payload"]) =>
    updateMutation.mutate({ id: session.id, payload });
  const toggleTrader = (code: TraderCode) => {
    const on = activeTraders.includes(code);
    if (on && activeTraders.length <= 1) return; // one trader must stay on
    update({ traders: on ? activeTraders.filter((c) => c !== code) : [...activeTraders, code] });
  };
  const openTrade = (tradeId: number) => navigate({ to: "/trades/$tradeId", params: { tradeId: String(tradeId) } });
  const loopPill = loop.error
    ? { cls: "te-pill--red", label: "RECONNECTING" }
    : loop.running && data
      ? { cls: "te-pill--green", label: "LOOP LIVE" }
      : { cls: "", label: loop.connection === "connecting" ? "CONNECTING" : "LOOP OFF" };
  const alerts = [
    oppLoop.lastError && `Scanner: ${oppLoop.lastError}`,
    loop.error,
    lockFailure && `Not locked: ${lockFailure}`,
    updateMutation.error instanceof Error && updateMutation.error.message,
  ].filter((m): m is string => Boolean(m));

  return (
    <div className="te-desk">
      {/* 1. Header: where you are + the session controls */}
      <header className="te-head">
        <div className="te-head__left">
          <button type="button" className="te-btn te-btn--ghost te-btn--sm" onClick={() => navigate({ to: "/sessions" })}>
            <ArrowLeft size={14} /> Sessions
          </button>
          <h1 className="te-title">{session.name}</h1>
          <span className={`te-mode-tag ${session.routeThroughUpstox ? "te-mode-tag--live" : "te-mode-tag--sim"}`}>
            {session.routeThroughUpstox ? "UPSTOX LIVE" : "SIMULATED"}
          </span>
          <span className={`te-pill ${isActive ? "te-pill--green" : ""}`}>{session.sessionStatus}</span>
          <span className={`te-pill ${loopPill.cls}`}>
            <Radio size={10} /> {loopPill.label}
          </span>
          <span className="micro text-muted mono">
            {session.tradeDate} · {hhmm(session.startAt)}–{hhmm(session.closeAt)} IST
          </span>
        </div>
        <div className="te-head__right">
          <div className="te-control">
            <span className="label">Mode</span>
            <div className="sd-seg-group" role="group" aria-label="Session mode">
              {(["MANUAL", "SEMI_AUTO", "FULL_AUTO"] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  className={`sd-seg-btn ${session.sessionType === mode ? "active" : ""}`}
                  aria-pressed={session.sessionType === mode}
                  onClick={() => update({ sessionType: mode })}
                  disabled={updateMutation.isPending || !isActive}
                >
                  {mode.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>
          <div className="te-control">
            <span className="label">Risk</span>
            <div className="sd-seg-group" role="group" aria-label="Session risk level">
              {RISK_LEVELS.map((lv) => (
                <button
                  key={lv}
                  type="button"
                  className={`sd-seg-btn ${riskLevel === lv ? "active" : ""}`}
                  aria-pressed={riskLevel === lv}
                  title={RISK_META[lv].takes}
                  onClick={() => update({ riskLevel: lv })}
                  disabled={updateMutation.isPending || !isActive}
                >
                  {lv}
                </button>
              ))}
            </div>
          </div>
          <button
            type="button"
            className={`upstox-switch-btn ${session.routeThroughUpstox ? "upstox-switch-btn--live" : ""}`}
            role="switch"
            aria-checked={session.routeThroughUpstox}
            onClick={() => update({ routeThroughUpstox: !session.routeThroughUpstox })}
            disabled={updateMutation.isPending || !isActive}
            title="Send this session's orders to Upstox (real money) or keep them simulated"
          >
            <div className={`upstox-switch-track ${session.routeThroughUpstox ? "upstox-switch-track--on" : ""}`}>
              <div className="upstox-switch-thumb" />
            </div>
            <Zap size={12} />
            <span>{session.routeThroughUpstox ? "UPSTOX LIVE" : "SIMULATED"}</span>
          </button>
          {isActive &&
            (scannersRunning > 0 ? (
              <button type="button" className="te-btn te-btn--ghost te-btn--sm" onClick={() => stopScanner.mutate()} disabled={stopScanner.isPending}>
                <Square size={11} />
                {oppLoop.running && oppLoop.currentCode ? `Scanning ${oppLoop.currentCode} · Stop` : "Stop scanner"}
              </button>
            ) : (
              <button
                type="button"
                className="te-btn te-btn--primary te-btn--sm"
                onClick={() => startScanner.mutate({ underlyings })}
                disabled={startScanner.isPending || underlyings.length === 0}
              >
                {startScanner.isPending ? <Loader2 size={12} className="sp-spin" /> : <Play size={12} />}
                {startScanner.isPending ? "Starting…" : "Start scanner"}
              </button>
            ))}
          {isActive && (
            <button
              type="button"
              className="te-btn te-btn--ghost te-btn--sm"
              onClick={() => update({ sessionStatus: "CLOSED" })}
              disabled={updateMutation.isPending || running.length > 0}
              title={running.length > 0 ? "Exit the running trades first" : "Close this session"}
            >
              <Power size={13} /> Close session
            </button>
          )}
        </div>
      </header>

      {noResearchData && (
        <div className="card desk-alert desk-alert--amber">
          <div className="desk-alert__text micro">
            <AlertTriangle size={15} />
            <span>The Research Engine has no data for today, so the scanner cannot look for setups in {underlyings.join(", ")}.</span>
          </div>
          <button type="button" className="te-btn te-btn--primary te-btn--sm" onClick={() => navigate({ to: "/research" })}>
            <Sparkles size={13} /> Run Research Engine
          </button>
        </div>
      )}
      {alerts.map((message) => (
        <div key={message} className="card desk-alert desk-alert--red">
          <div className="desk-alert__text micro">
            <AlertTriangle size={14} />
            <span>{message}</span>
          </div>
        </div>
      ))}

      {/* 2. Stat row */}
      <div className="card te-stats">
        <div className="te-stat">
          <div className="te-stat__label">Current capital</div>
          <div className="te-stat__value">{formatRupee(cap?.currentCapital ?? session.currentCapital)}</div>
          <div className={`te-stat__sub ${realized >= 0 ? "text-green" : "text-red"}`}>
            {formatSignedRupee(realized, true)} ({((realized / session.capital) * 100).toFixed(2)}%)
          </div>
        </div>
        <div className="te-stat">
          <div className="te-stat__label">Starting capital</div>
          <div className="te-stat__value">{formatRupee(session.capital)}</div>
          <div className="te-stat__sub">Max loss {session.maxLossPercentage}% = {formatRupee(maxLoss)}</div>
        </div>
        <div className="te-stat">
          <div className="te-stat__label">Free to trade</div>
          <div className="te-stat__value text-green">{formatRupee(cap?.availableCapital ?? session.currentCapital)}</div>
          <div className="te-stat__sub">{formatRupee(cap?.committedPremium ?? 0)} in open positions</div>
        </div>
        <div className="te-stat">
          <div className="te-stat__label">Loss budget left</div>
          <div className="te-stat__value">{formatRupee(budgetLeft)}</div>
          <div className="te-budget">
            <div
              className={`te-budget__fill ${budgetPct > 50 ? "" : budgetPct > 20 ? "te-budget__fill--warn" : "te-budget__fill--crit"}`}
              style={{ width: `${budgetPct}%` }}
            />
          </div>
        </div>
        <div className="te-stat">
          <div className="te-stat__label">Trades</div>
          <div className="te-stat__value">
            {running.length} live · {closed.length} closed
          </div>
          <div className="te-stat__sub">
            {closed.length > 0 ? `${wins}W / ${closed.length - wins}L` : "No closed trades yet"} · max{" "}
            {cap?.maxParallelTrades ?? 3} at once
          </div>
        </div>
        <div className="te-stat">
          <div className="te-stat__label">Profile</div>
          <div className="te-chips" style={{ marginTop: 4 }}>
            <span className="te-pill te-pill--blue">{session.sessionType.replace("_", " ")}</span>
            <span className={`te-pill ${riskLevel === "LOW" ? "te-pill--green" : riskLevel === "MEDIUM" ? "te-pill--amber" : "te-pill--red"}`}>
              {riskLevel} RISK
            </span>
          </div>
          <div className="te-stat__sub">{underlyings.join(", ")}</div>
        </div>
      </div>

      {/* 3. Desk */}
      <div className="te-grid">
        <div className="te-desk">
          <ManagerCard
            advice={data?.manager}
            stateTitle={stateTitle}
            stateMessage={stateMessage}
            openCount={picks.length}
            candidates={data?.scanned.candidates ?? 0}
            riskLevel={riskLevel}
            locking={lockMutation.isPending}
            canLock={isActive}
            onLock={handleLock}
            onShow={(pid) => {
              setTab("CURRENT");
              setFocusPickId(pid);
            }}
          />

          <div className="te-tabs">
            <div className="te-tabs__list" role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={tab === "CURRENT"}
                className={`te-tab ${tab === "CURRENT" ? "active" : ""}`}
                onClick={() => setTab("CURRENT")}
              >
                <Radio size={14} /> Current ({picks.length})
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={tab === "HISTORY"}
                className={`te-tab ${tab === "HISTORY" ? "active" : ""}`}
                onClick={() => setTab("HISTORY")}
              >
                <History size={14} /> History · batches
              </button>
            </div>
            <span className="te-tabs__meta">
              {oppLoop.running && (
                <span>
                  <Loader2 size={11} className="sp-spin" />{" "}
                  {oppLoop.currentCode ? `scanning ${oppLoop.currentCode}` : `round ${oppLoop.round}`}
                </span>
              )}
              {tab === "CURRENT" && (
                <span>
                  Sorted by <strong>expected net</strong>
                </span>
              )}
            </span>
          </div>

          {tab === "CURRENT" ? (
            <div className="te-desk" role="tabpanel">
              {excluded.length > 0 && (
                <div className="te-chips" aria-label="Why candidates were skipped">
                  {excluded.map(([reason, n]) => (
                    <span key={reason} className="te-pill" title="Candidates skipped for this reason">
                      {n} · {reason}
                    </span>
                  ))}
                </div>
              )}

              {lockedPicks.length > 0 && (
                <section className="te-panel" aria-label="Locked picks">
                  <span className="te-panel__title">
                    <Lock size={14} /> Locked, ready to enter ({lockedPicks.length})
                  </span>
                  {lockedPicks.map((lp) => (
                    <div key={lp.id} className="te-row">
                      <span className="te-row__main">
                        <span className="te-row__title mono">
                          {lp.underlyingCode} {lp.strike} {lp.optionType} · {lp.lots} lot{lp.lots === 1 ? "" : "s"}
                        </span>
                        <span className="te-row__sub">
                          Locked at {formatRupee(lp.lockedPrice ?? lp.entry)} · stop {formatRupee(lp.stop)} · target{" "}
                          {formatRupee(lp.target)}
                        </span>
                      </span>
                      <button type="button" className="te-btn te-btn--primary te-btn--sm" onClick={() => setLockedPick(lp)}>
                        <Play size={12} /> Enter trade
                      </button>
                    </div>
                  ))}
                </section>
              )}

              {TRADER_CODES.map((code) => {
                const meta = TRADER_META[code];
                const on = activeTraders.includes(code);
                const mine = picks.filter((p) => pickTrader(p) === code);
                return (
                  <section key={code} className={`te-trader ${on ? "" : "te-trader--off"}`} aria-label={meta.name}>
                    <div className="te-trader__head">
                      <div className="te-trader__name">
                        <span className={`badge ${on ? meta.badgeClass : "badge--slate"} mono`}>{meta.tag}</span>
                        <h3>{meta.name}</h3>
                        <span className="micro text-muted">{mine.length} open</span>
                      </div>
                      <button
                        type="button"
                        className={`desk-switch ${on ? "desk-switch--on" : ""}`}
                        role="switch"
                        aria-checked={on}
                        aria-label={`${meta.name} ${on ? "on" : "off"}`}
                        disabled={updateMutation.isPending || (on && activeTraders.length <= 1) || !isActive}
                        title={on && activeTraders.length <= 1 ? "At least one trader must stay on" : undefined}
                        onClick={() => toggleTrader(code)}
                      >
                        <span className="desk-switch__track">
                          <span className="desk-switch__thumb" />
                        </span>
                        <span className="micro">{on ? "ON" : "OFF"}</span>
                      </button>
                    </div>
                    {mine.length === 0 ? (
                      <div className="te-empty">
                        {!on
                          ? "Switched off for this session."
                          : !isActive
                            ? "The session is closed."
                            : scannersRunning === 0
                              ? "The scanner is stopped. Start it to look for setups."
                              : `Watching: ${meta.checks[0].toLowerCase()}.`}
                      </div>
                    ) : (
                      mine.map((p) => (
                        <div key={`${p.id}-${focusPickId === p.id}`} id={`pick-${p.id}`}>
                          <SuggestionCard
                            pick={p}
                            clockOffsetMs={loop.clockOffsetMs}
                            locking={lockMutation.isPending && lockMutation.variables === p.id}
                            best={bestId === p.id}
                            defaultExpanded={focusPickId === p.id || (bestId === p.id && focusPickId === null)}
                            onLock={handleLock}
                          />
                        </div>
                      ))
                    )}
                  </section>
                );
              })}

              {oppCards.some((c) => underlyings.includes(c.code) && c.master) && (
                <div className="te-chips" aria-label="Scanner status per underlying">
                  {oppCards
                    .filter((c) => underlyings.includes(c.code) && c.master)
                    .map((c) => (
                      <span key={c.code} className={`te-pill ${c.master?.lastError ? "te-pill--red" : ""}`}>
                        {c.code} · scan {c.master?.iterationsCompleted ?? 0} ·{" "}
                        {c.master?.lastError ?? c.master?.lastNote ?? `${c.master?.liveCount ?? 0} live`}
                      </span>
                    ))}
                </div>
              )}
            </div>
          ) : (
            <div role="tabpanel">
              <BatchHistory sessionId={sessionId} />
            </div>
          )}
        </div>

        <aside className="te-side" aria-label="Trades and learning">
          {running.map((t) => (
            <RunningTradeCard key={t.id} trade={t} onOpen={openTrade} />
          ))}
          <SessionTradesPanel trades={allTrades} autopsies={autopsyByTrade} onOpen={openTrade} />
          <AutopsyAgentPanel latest={autopsyList[0]} />
        </aside>
      </div>

      {lockedPick && <TradeLockModal pick={lockedPick} onClose={() => setLockedPick(null)} />}
    </div>
  );
};
