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
import { BatchHistory } from "../components/BatchHistory";
import { RunningTradeCard } from "../components/RunningTradeCard";
import { SessionTradesPanel } from "../components/SessionTradesPanel";
import { ManagerAgentPanel, ScannerStatus } from "../components/agents/ManagerAgentPanel";
import { AutopsySubAgent } from "../components/agents/AutopsySubAgent";
import { AgentActivityFeed } from "../components/agents/AgentActivityFeed";
import { RISK_LEVELS, RISK_META } from "../components/riskLevels";
import { useTradeSearch } from "../../trade-history/hooks/useTrades";
import { tradesQueryKeys } from "../../trade-history/queryKeys/tradesQueryKeys";
import { DEFAULT_TRADER_CODES, DESK_CODE, normalizeTraderCodes } from "../../trade-history/components/traderMeta";
import { DeskPanel } from "../../commodity-desk/components/DeskPanel";
import { NewsSubAgent } from "../../commodity-desk/components/NewsSubAgent";
import { TraderCode } from "../../trade-history/types/trades.types";
import { useAutopsies } from "../../autopsy/hooks/useLearning";
import { learningQueryKeys } from "../../autopsy/queryKeys/learningQueryKeys";
import { formatRupee, formatSignedRupee } from "../../opportunity-finder/components/formatters";
import {
  resumeOpportunityLoop,
  useOpportunityCards,
  useOpportunityLoop,
  useStartOpportunity,
  useStopAll,
} from "../../opportunity-finder/hooks/useOpportunities";
import { RiskLevel, SessionPick } from "../types/sessions.types";

const LOCK_FAILURE_MS = 6000;
const LIVE_REFRESH_MS = 2000;
const IDLE_REFRESH_MS = 15000;

const hhmm = (iso: string): string =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });

type Tab = "CURRENT" | "HISTORY";

/**
 * The session screen: a compact control bar and stat strip, then the session manager agent (its last pass traced
 * scan -> filter -> rank -> decide, with its autopsy sub-agent under it) and the open setups on the left; locked
 * picks, running and closed trades and the agents' activity on the right.
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
  const myCards = oppCards.filter((c) => underlyings.includes(c.code) && c.master);
  const scannersRunning = myCards.filter((c) => c.master?.state === "RUNNING").length;
  const scanners: ScannerStatus[] = myCards.map((c) => ({
    code: c.code,
    note: c.master?.lastError ?? c.master?.lastNote?.toLowerCase() ?? `${c.master?.liveCount ?? 0} live`,
    error: Boolean(c.master?.lastError),
    on: c.master?.state === "RUNNING",
    scans: c.master?.iterationsCompleted ?? 0,
    lastStartedAt: c.master?.lastStartedAt ?? null,
    lastCompletedAt: c.master?.lastCompletedAt ?? null,
    lastDurationMs: c.master?.lastDurationMs ?? null,
    gapSeconds: Number(c.master?.params?.loopGapSeconds ?? 20),
  }));
  const noResearchData =
    !hasResearch ||
    (startScanner.data && !startScanner.data.started && startScanner.data.reason === "NO_RESEARCH_DATA");
  const activeTraders = normalizeTraderCodes(session.traders);
  // the opportunity finders feeding this session (chosen by its scope); old sessions: the ones named in traders
  const sessionFinders = normalizeTraderCodes(session.finders?.length ? session.finders : session.traders);
  const managerCode: TraderCode | null = activeTraders.length === 1 ? activeTraders[0] : null;
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
  const excluded = Object.entries(data?.scanned.excluded ?? {}).sort((a, b) => b[1] - a[1]);
  const bestId = data?.manager?.pickId ?? null;

  const cap = data?.capital;
  const maxLoss = (session.capital * session.maxLossPercentage) / 100;
  const budgetLeft = cap?.remainingLossBudget ?? maxLoss;
  const budgetPct = maxLoss > 0 ? Math.min(100, (budgetLeft / maxLoss) * 100) : 0;
  const realized = cap?.realizedPnl ?? session.realizedPnl;
  const maxParallel = cap?.maxParallelTrades ?? 3;
  const loopState = !isActive ? "SESSION_CLOSED" : (data?.state ?? null);
  const stateMessage = !isActive
    ? "This session is closed."
    : (data?.message ?? (loop.connection === "connecting" ? "Connecting to the session loop…" : "Waiting for the first loop pass."));

  const update = (payload: Parameters<typeof updateMutation.mutate>[0]["payload"]) =>
    updateMutation.mutate({ id: session.id, payload });
  // One session manager per session: switching hands the session over; its finders stay the same
  const chooseManager = (code: TraderCode) => {
    if (managerCode === code) return;
    update({ traders: [code] });
  };
  const openTrade = (tradeId: number) => navigate({ to: "/trades/$tradeId", params: { tradeId: String(tradeId) } });
  const loopPill = loop.error
    ? { cls: "te-pill--red", label: "RECONNECTING" }
    : loop.running && data
      ? { cls: "te-pill--green", label: "LIVE" }
      : { cls: "", label: loop.connection === "connecting" ? "CONNECTING" : "LOOP OFF" };
  const alerts = [
    oppLoop.lastError && `Scanner: ${oppLoop.lastError}`,
    loop.error,
    lockFailure && `Not locked: ${lockFailure}`,
    updateMutation.error instanceof Error && updateMutation.error.message,
  ].filter((m): m is string => Boolean(m));
  const showPick = (pid: number) => {
    setTab("CURRENT");
    setFocusPickId(pid);
  };

  const controls = (
    <div className="sd3-controls" role="toolbar" aria-label="Session controls">
      <div className="sd3-ctl">
        <span className="sd3-ctl__label">Mode</span>
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
      <div className="sd3-ctl">
        <span className="sd3-ctl__label">Risk</span>
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
      <div className="sd3-ctl sd3-ctl--actions">
        <button
          type="button"
          className={`sd2-live ${session.routeThroughUpstox ? "sd2-live--on" : ""}`}
          role="switch"
          aria-checked={session.routeThroughUpstox}
          onClick={() => update({ routeThroughUpstox: !session.routeThroughUpstox })}
          disabled={updateMutation.isPending || !isActive}
          title="Send this session's orders to Upstox (real money) or keep them simulated"
        >
          <Zap size={12} /> {session.routeThroughUpstox ? "Upstox live" : "Simulated"}
        </button>
        {isActive &&
          (scannersRunning > 0 ? (
            <button type="button" className="te-btn te-btn--ghost te-btn--sm" onClick={() => stopScanner.mutate()} disabled={stopScanner.isPending}>
              <Square size={11} /> Stop scanner
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
            <Power size={12} /> Close
          </button>
        )}
      </div>
    </div>
  );

  return (
    <div className="te-desk sd3">
      {/* LEFT 60%: the session manager agent and the opportunities it works on */}
      <div className="sd3-main">
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

        <ManagerAgentPanel
          managerCode={managerCode}
          scope={session.scope}
          finderCodes={sessionFinders}
          state={loopState}
          message={stateMessage}
          isActive={isActive}
          scanners={scanners}
          scannersRunning={scannersRunning}
          scanningCode={oppLoop.running ? oppLoop.currentCode : null}
          candidates={data?.scanned.candidates ?? 0}
          excluded={excluded}
          openCount={picks.length}
          advice={data?.manager}
          locking={lockMutation.isPending}
          switching={updateMutation.isPending}
          onLock={handleLock}
          onShow={showPick}
          onSwitch={chooseManager}
        >
          {sessionFinders.includes(DESK_CODE) ? (
            <DeskPanel codes={underlyings} />
          ) : (
            <NewsSubAgent codes={underlyings} />
          )}
          {(managerCode ? [managerCode] : DEFAULT_TRADER_CODES).map((code) => (
            <AutopsySubAgent key={code} managerCode={code} nested collapsible />
          ))}
        </ManagerAgentPanel>

        <section className="sd3-opps" aria-label="Opportunities">
          <div className="te-tabs">
            <div className="te-tabs__list" role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={tab === "CURRENT"}
                className={`te-tab ${tab === "CURRENT" ? "active" : ""}`}
                onClick={() => setTab("CURRENT")}
              >
                <Radio size={14} /> Opportunities ({picks.length})
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
              <span title="Every setup is confirmed on the 15-minute trend and a 1-minute trigger">15m trend · 1m trigger</span>
            </span>
          </div>

          {tab === "CURRENT" ? (
            <div className="sd2-picks" role="tabpanel">
              {picks.length === 0 ? (
                <div className="te-empty">
                  {!isActive
                    ? "The session is closed."
                    : scannersRunning === 0
                      ? "The scanner is stopped. Start it to look for setups."
                      : "No open opportunity. The session manager offers one here as soon as a setup passes the 15-minute, 5-minute and 1-minute checks."}
                </div>
              ) : (
                picks.map((p) => (
                  <div key={`${p.id}-${focusPickId === p.id}`} id={`pick-${p.id}`}>
                    <SuggestionCard
                      pick={p}
                      clockOffsetMs={loop.clockOffsetMs}
                      locking={lockMutation.isPending && lockMutation.variables === p.id}
                      best={bestId === p.id}
                      defaultExpanded={focusPickId === p.id}
                      onLock={handleLock}
                    />
                  </div>
                ))
              )}
            </div>
          ) : (
            <div role="tabpanel">
              <BatchHistory sessionId={sessionId} />
            </div>
          )}
        </section>
      </div>

      {/* RIGHT 40%: the session itself -- identity, controls, money, positions, trades, activity */}
      <aside className="sd3-side" aria-label="Session details">
        <section className="sd3-card" aria-label="Session">
          <div className="sd3-card__top">
            <button type="button" className="sd2-back" onClick={() => navigate({ to: "/sessions" })} aria-label="Back to sessions">
              <ArrowLeft size={15} />
            </button>
            <div className="sd3-card__id">
              <h1 className="sd2-title">{session.tradeDate}</h1>
              <span className="micro text-muted mono">
                #{session.id} · {hhmm(session.startAt)}–{hhmm(session.closeAt)} IST
              </span>
            </div>
            <span className="sd3-card__pills">
              <span className={`te-pill ${isActive ? "te-pill--green" : ""}`}>{session.sessionStatus}</span>
              <span className={`te-pill ${loopPill.cls}`}>
                <Radio size={10} /> {loopPill.label}
              </span>
            </span>
          </div>
          <span className="sd2-underlyings">
            {underlyings.map((c) => (
              <span key={c} className="sd2-ul">{c}</span>
            ))}
          </span>
          {controls}
          <div className="sd3-kpis" aria-label="Session capital">
            <div className="sd2-kpi">
              <span className="sd2-kpi__label">Capital</span>
              <span className="sd2-kpi__value">{formatRupee(cap?.currentCapital ?? session.currentCapital)}</span>
              <span className={`sd2-kpi__sub ${realized > 0 ? "text-green" : realized < 0 ? "text-red" : ""}`}>
                {formatSignedRupee(realized, true)} ({((realized / session.capital) * 100).toFixed(2)}%)
              </span>
            </div>
            <div className="sd2-kpi">
              <span className="sd2-kpi__label">Free to trade</span>
              <span className="sd2-kpi__value text-green">{formatRupee(cap?.availableCapital ?? session.currentCapital)}</span>
              <span className="sd2-kpi__sub">{formatRupee(cap?.committedPremium ?? 0)} in positions</span>
            </div>
            <div className="sd2-kpi">
              <span className="sd2-kpi__label">Loss budget left</span>
              <span className="sd2-kpi__value">{formatRupee(budgetLeft)}</span>
              <div className="te-budget" title={`${session.maxLossPercentage}% of capital = ${formatRupee(maxLoss)}`}>
                <div
                  className={`te-budget__fill ${budgetPct > 50 ? "" : budgetPct > 20 ? "te-budget__fill--warn" : "te-budget__fill--crit"}`}
                  style={{ width: `${budgetPct}%` }}
                />
              </div>
            </div>
            <div className="sd2-kpi">
              <span className="sd2-kpi__label">Trades</span>
              <span className="sd2-kpi__value">{closed.length > 0 ? `${wins}W · ${closed.length - wins}L` : "0 closed"}</span>
              <span className="sd2-kpi__sub">
                {running.length}/{maxParallel} open · {lockedPicks.length} locked
              </span>
            </div>
          </div>
        </section>

        {lockedPicks.length > 0 && (
          <section className="te-panel" aria-label="Locked picks">
            <span className="te-panel__title">
              <Lock size={14} /> Locked, ready to enter ({lockedPicks.length})
            </span>
            {lockedPicks.map((lp: SessionPick) => (
              <div key={lp.id} className="te-row">
                <span className="te-row__main">
                  <span className="te-row__title mono">
                    {lp.underlyingCode} {lp.strike} {lp.optionType} · {lp.lots} lot{lp.lots === 1 ? "" : "s"}
                  </span>
                  <span className="te-row__sub">
                    at {formatRupee(lp.lockedPrice ?? lp.entry)} · SL {formatRupee(lp.stop)} · T {formatRupee(lp.target)}
                  </span>
                </span>
                <button type="button" className="te-btn te-btn--primary te-btn--sm" onClick={() => setLockedPick(lp)}>
                  <Play size={12} /> Enter
                </button>
              </div>
            ))}
          </section>
        )}
        {running.map((t) => (
          <RunningTradeCard key={t.id} trade={t} onOpen={openTrade} />
        ))}
        <SessionTradesPanel trades={allTrades} autopsies={autopsyByTrade} onOpen={openTrade} />
        <AgentActivityFeed sessionId={sessionId} autopsies={autopsyList} />
      </aside>

      {lockedPick && <TradeLockModal pick={lockedPick} onClose={() => setLockedPick(null)} />}
    </div>
  );
};
