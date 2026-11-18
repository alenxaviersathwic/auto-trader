import React, { useEffect, useRef, useState, useMemo } from "react";
import { useNavigate, useParams } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  Bot,
  History,
  Lock,
  Pencil,
  Play,
  Power,
  Radio,
  ScanSearch,
  Sparkles,
  Square,
  Zap,
} from "lucide-react";
import { useLockSessionPick, useSessionDetail, useUpdateSession } from "../hooks/useSessions";
import { useSessionLoop } from "../hooks/useSessionLoop";
import { sessionsQueryKeys } from "../queryKeys/sessionsQueryKeys";
import { TradeLockModal } from "../components/TradeLockModal";
import { SessionEditModal } from "../components/SessionEditModal";
import { UnderlyingChartModal } from "../components/UnderlyingChartModal";
import { SuggestionCard } from "../components/SuggestionCard";
import { BatchHistory } from "../components/BatchHistory";
import { RunningTradeCard } from "../components/RunningTradeCard";
import { SessionTradesPanel } from "../components/SessionTradesPanel";
import { RISK_META } from "../components/riskLevels";
import { useTradeSearch } from "../../trade-history/hooks/useTrades";
import { tradesQueryKeys } from "../../trade-history/queryKeys/tradesQueryKeys";
import { TRADER_META, managerFor, normalizeTraderCodes } from "../../trade-history/components/traderMeta";
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
  const { cards: oppCards, hasResearch, isLoading: oppCardsLoading } = useOpportunityCards(oppLoop.running || !!oppLoop.inOtherTab);
  const startScanner = useStartOpportunity();
  const stopScanner = useStopAll();
  const autoStartedScannerRef = useRef<boolean>(false);

  const [tab, setTab] = useState<Tab>("CURRENT");
  const [editOpen, setEditOpen] = useState(false);
  const [chartCode, setChartCode] = useState<string | null>(null);
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

  // The finders scan the WHOLE market of this session's scope (every Research card of that type plus this session's
  // own codes), not only what this session trades: the Traders area and every session read the same scans, and a
  // session still picks only from its own underlyings (session_loop_service._codes). 18 Nov 2026.
  const marketCodes = useMemo(() => {
    if (!session) return [];
    const own = (session.scope === "INDEX" ? session.underlyings : session.commodityItems) ?? [];
    const type = session.scope === "INDEX" ? "INDEX" : "COMMODITY";
    return Array.from(new Set([...own, ...oppCards.filter((c) => c.type === type).map((c) => c.code)]));
  }, [session, oppCards]);
  const notScanning = useMemo(
    () => marketCodes.filter((code) => oppCards.find((c) => c.code === code)?.master?.state !== "RUNNING"),
    [marketCodes, oppCards],
  );

  // Resume the loop, and start a scanner for every market code that has none, when an ACTIVE session is opened.
  useEffect(() => {
    if (!session || session.sessionStatus !== "ACTIVE" || oppCardsLoading || marketCodes.length === 0) return;
    if (notScanning.length < marketCodes.length && !oppLoop.running) resumeOpportunityLoop();
    if (notScanning.length > 0 && !autoStartedScannerRef.current && hasResearch && !startScanner.isPending) {
      autoStartedScannerRef.current = true;
      startScanner.mutate({ underlyings: notScanning });
    }
  }, [session, marketCodes, notScanning, oppCardsLoading, oppLoop.running, hasResearch, startScanner]);

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
  const scanners = myCards.map((c) => ({
    code: c.code,
    note: c.master?.lastError ?? c.master?.lastNote?.toLowerCase() ?? `${c.master?.liveCount ?? 0} live`,
    error: Boolean(c.master?.lastError),
    on: c.master?.state === "RUNNING",
    scans: c.master?.iterationsCompleted ?? 0,
  }));
  const noResearchData =
    !hasResearch ||
    (startScanner.data && !startScanner.data.started && startScanner.data.reason === "NO_RESEARCH_DATA");
  const activeTraders = normalizeTraderCodes(session.traders);
  // the opportunity finders feeding this session (chosen by its scope); old sessions: the ones named in traders
  const sessionFinders = normalizeTraderCodes(session.finders?.length ? session.finders : session.traders);
  const managerCode: TraderCode | null = activeTraders.length === 1 ? activeTraders[0] : null;
  const manager = managerCode ? managerFor(managerCode) : null;
  const finders = sessionFinders.map((c) => TRADER_META[c]).filter(Boolean);
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
  const skippedCount = excluded.reduce((n, [, c]) => n + c, 0);
  const bestId = data?.manager?.pickId ?? null;

  const cap = data?.capital;
  const maxLoss = (session.capital * session.maxLossPercentage) / 100;
  const budgetLeft = cap?.remainingLossBudget ?? maxLoss;
  const budgetPct = maxLoss > 0 ? Math.min(100, (budgetLeft / maxLoss) * 100) : 0;
  const realized = cap?.realizedPnl ?? session.realizedPnl;
  const maxParallel = cap?.maxParallelTrades ?? 3;
  const stateMessage = !isActive
    ? "This session is closed."
    : (data?.message ?? (loop.connection === "connecting" ? "Connecting to the session loop…" : "Waiting for the first loop pass."));

  const update = (payload: Parameters<typeof updateMutation.mutate>[0]["payload"]) =>
    updateMutation.mutate({ id: session.id, payload });
  const handleEditSave = async (payload: Parameters<typeof updateMutation.mutateAsync>[0]["payload"]) => {
    await updateMutation.mutateAsync({ id: session.id, payload });
    setEditOpen(false);
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

  return (
    <div className="te-desk sd3">
      {/* LEFT 60%: Opportunities front and center */}
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
                      : "No open opportunity right now. Qualified setups matching 15m trend and 1m trigger will appear here."}
                </div>
              ) : (
                picks.map((p) => (
                  <div key={p.id} id={`pick-${p.id}`}>
                    <SuggestionCard
                      pick={p}
                      clockOffsetMs={loop.clockOffsetMs}
                      locking={lockMutation.isPending && lockMutation.variables === p.id}
                      best={bestId === p.id}
                      defaultExpanded={bestId === p.id}
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

      {/* RIGHT 40%: session details (read-only) with Edit button, session manager, active finders, trades */}
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

          <div className="sd-side-actions">
            <span className="sd2-underlyings">
              {underlyings.map((c) => (
                <button
                  key={c}
                  type="button"
                  className="sd2-ul sd2-ul--btn"
                  onClick={() => setChartCode(c)}
                  title={`Open ${c} live chart & agent diagnostics`}
                >
                  {c}
                </button>
              ))}
            </span>
            {isActive && (
              <div className="sd-side-actions__btns">
                <button
                  type="button"
                  className="te-btn te-btn--ghost te-btn--sm"
                  onClick={() => setEditOpen(true)}
                  title="Edit session manager, mode, risk, or capital"
                >
                  <Pencil size={12} /> Edit
                </button>
                <button
                  type="button"
                  className="te-btn te-btn--ghost te-btn--sm"
                  onClick={() => update({ sessionStatus: "CLOSED" })}
                  disabled={updateMutation.isPending || running.length > 0}
                  title={running.length > 0 ? "Exit the running trades first" : "Close this session"}
                >
                  <Power size={12} /> Close
                </button>
              </div>
            )}
          </div>

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

          {/* Read-only session configuration */}
          <div className="sd-ro-grid" aria-label="Session settings">
            <div className="sd-ro-item">
              <span className="sd-ro-item__label">Mode</span>
              <span className="sd-ro-item__val mono">{session.sessionType.replace("_", " ")}</span>
            </div>
            <div className="sd-ro-item">
              <span className="sd-ro-item__label">Risk</span>
              <span className={`badge ${RISK_META[riskLevel].badgeClass}`}>{RISK_META[riskLevel].label}</span>
            </div>
            <div className="sd-ro-item">
              <span className="sd-ro-item__label">Routing</span>
              <span className={`sd-ro-item__val ${session.routeThroughUpstox ? "text-green" : "text-secondary"}`}>
                <Zap size={11} /> {session.routeThroughUpstox ? "Upstox Live" : "Simulated"}
              </span>
            </div>
            <div className="sd-ro-item">
              <span className="sd-ro-item__label">Max loss</span>
              <span className="sd-ro-item__val mono">{session.maxLossPercentage}%</span>
            </div>
          </div>
        </section>

        {/* Session Manager (read-only) */}
        <section className="te-panel" aria-label="Session manager">
          <div className="te-panel__head">
            <span className="te-panel__title">
              <Bot size={14} /> Session Manager
            </span>
            <span className="micro text-muted">{manager ? manager.name : "Both traders"}</span>
          </div>
          <p className="micro text-secondary" style={{ margin: 0 }}>
            {stateMessage}
          </p>
        </section>

        {/* Active Opportunity Finders */}
        <section className="te-panel" aria-label="Active opportunity finders">
          <div className="te-panel__head">
            <span className="te-panel__title">
              <ScanSearch size={14} /> Active Opportunity Finders
            </span>
            {isActive &&
              (scannersRunning > 0 ? (
                <button type="button" className="te-btn te-btn--ghost te-btn--xs" onClick={() => stopScanner.mutate()} disabled={stopScanner.isPending}>
                  <Square size={10} /> Stop
                </button>
              ) : (
                <button
                  type="button"
                  className="te-btn te-btn--primary te-btn--xs"
                  onClick={() => startScanner.mutate({ underlyings: notScanning.length ? notScanning : marketCodes })}
                  disabled={startScanner.isPending || marketCodes.length === 0}
                >
                  <Play size={10} /> {startScanner.isPending ? "Starting…" : "Start"}
                </button>
              ))}
          </div>

          <div className="sd-finders-list">
            {finders.map((f) => (
              <div key={f.code} className="sd-finder-row">
                <span className={`badge ${f.badgeClass} mono`}>{f.tag}</span>
                <span className="micro text-primary" style={{ flex: 1 }}>{f.name}</span>
                <span className={`te-pill ${scannersRunning > 0 ? "te-pill--green" : ""}`}>
                  {scannersRunning > 0 ? "ACTIVE" : "IDLE"}
                </span>
              </div>
            ))}
          </div>

          <div className="sd-mgr-bar__scanners">
            <span className="micro text-muted">
              Scanners: <strong className="mono">{scannersRunning}/{scanners.length}</strong>
              {data ? ` · ${data.scanned.candidates} candidates` : ""}
              {skippedCount > 0 ? ` · ${skippedCount} filtered` : ""}
            </span>
            <div className="sd-mgr-bar__chips">
              {scanners.map((sc) => (
                <button
                  key={sc.code}
                  type="button"
                  className={`sd-scan-chip sd-scan-chip--btn ${sc.error ? "sd-scan-chip--err" : sc.on ? "sd-scan-chip--on" : ""}`}
                  title={`${sc.code}: ${sc.note} — click for live chart & diagnostics`}
                  onClick={() => setChartCode(sc.code)}
                >
                  <span className="mono">{sc.code}</span>
                  <span className="micro">{sc.error ? "err" : `${sc.scans}×`}</span>
                </button>
              ))}
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
      </aside>

      {editOpen && (
        <SessionEditModal
          session={session}
          saving={updateMutation.isPending}
          error={updateMutation.error instanceof Error ? updateMutation.error.message : null}
          onSave={handleEditSave}
          onClose={() => setEditOpen(false)}
        />
      )}
      {chartCode && <UnderlyingChartModal code={chartCode} finderCodes={sessionFinders} onClose={() => setChartCode(null)} />}
      {lockedPick && <TradeLockModal pick={lockedPick} onClose={() => setLockedPick(null)} />}
    </div>
  );
};
