import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Ban,
  Cpu,
  ExternalLink,
  Info,
  Loader2,
  Play,
  Plus,
  Radio,
  Sparkles,
  Square,
  Zap,
} from "lucide-react";
import {
  useLockSessionPick,
  useSessionDetail,
  useSessionPicks,
  useUpdateSession,
} from "../hooks/useSessions";
import { useSessionLoop } from "../hooks/useSessionLoop";
import { sessionsQueryKeys } from "../queryKeys/sessionsQueryKeys";
import { SessionCapitalStrip } from "../components/SessionCapitalStrip";
import { SessionOpportunityTable } from "../components/SessionOpportunityTable";
import { SessionPickHistory } from "../components/SessionPickHistory";
import { TradeLockModal } from "../components/TradeLockModal";
import { UNDERLYING_NAMES } from "../../opportunities/components/underlyingNames";
import { formatRupee } from "../../opportunities/components/formatters";
import { useTradeSearch, useTraderPresets } from "../../trades/hooks/useTrades";
import { tradesQueryKeys } from "../../trades/queryKeys/tradesQueryKeys";
import { SideSheetMode, TraderSideSheet } from "../../trades/components/TraderSideSheet";
import {
  resumeOpportunityLoop,
  useOpportunityCards,
  useOpportunityLoop,
  useStartOpportunity,
  useStopAll,
} from "../../opportunities/hooks/useOpportunities";
import {
  SessionCapital,
  SessionLoopStateName,
  SessionPick,
  SessionPickSearchFilter,
  TradingSession,
} from "../types/sessions.types";

const HISTORY_FILTER: SessionPickSearchFilter = {
  page: 0,
  limit: 20,
  sortBy: "createdAt",
  sortDir: "desc",
};
const LOCK_FAILURE_MS = 6000;

const TRADER_META: Record<string, { label: string; tag: string; cls: string }> = {
  FIB_GOLDEN_TRADER: {
    label: "Fib Golden 0.618",
    tag: "0.618 → 1.618 EXT",
    cls: "sd-tag sd-tag--cyan",
  },
  ORB_WAVE_TRADER: {
    label: "ORB Wave Runner",
    tag: "STEP 100→120→150",
    cls: "sd-tag sd-tag--green",
  },
  FLOW_VWAP_TRADER: {
    label: "VWAP + OI Flow",
    tag: "OI UNWIND + VWAP",
    cls: "sd-tag sd-tag--amber",
  },
};

const hhmm = (iso: string): string =>
  new Date(iso).toLocaleTimeString("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

function statusPillClass(status: TradingSession["sessionStatus"]): string {
  if (status === "ACTIVE") return "sd-status-pill is-green";
  if (status === "CLOSED") return "sd-status-pill";
  return "sd-status-pill is-amber";
}

const STATE_COPY: Record<
  Exclude<SessionLoopStateName, "PICK_READY">,
  { title: string; tone: "scan" | "stop" | "info" }
> = {
  SCHEDULED: { title: "Waiting for the session start time", tone: "info" },
  WAITING: { title: "Preset Traders scanning for the highest-conviction setup", tone: "scan" },
  HALTED: { title: "Halted: session max loss limit reached", tone: "stop" },
  SESSION_CLOSED: { title: "This session is closed", tone: "stop" },
  UNSUPPORTED_TYPE: { title: "Loop not defined for this session type yet", tone: "info" },
};

export const SessionDetailPage: React.FC = () => {
  const { id } = useParams({ strict: false }) as { id: string };
  const navigate = useNavigate({ from: "/sessions/$id" });
  const search = useSearch({ from: "/sessions/$id" }) as {
    sheet?: SideSheetMode;
    trader?: string;
    tradeId?: number;
  };
  const queryClient = useQueryClient();
  const sessionId = Number(id);

  const { data: session, isLoading } = useSessionDetail(sessionId);
  const loop = useSessionLoop(sessionId, !!session && session.sessionStatus === "ACTIVE");
  const history = useSessionPicks(sessionId, HISTORY_FILTER);
  const sessionTrades = useTradeSearch({
    page: 0,
    limit: 10,
    sortBy: "createdAt",
    sortDir: "desc",
    sessionId,
  });
  const lockMutation = useLockSessionPick(sessionId);
  const updateMutation = useUpdateSession();
  const { data: presetsData } = useTraderPresets();

  // Underlying Scanner Engine (drives TradeOpportunity generation for this session)
  const oppLoop = useOpportunityLoop();
  const { cards: oppCards, hasResearch, isLoading: oppCardsLoading } = useOpportunityCards(oppLoop.running);
  const startScanner = useStartOpportunity();
  const stopScanner = useStopAll();
  const autoStartedScannerRef = useRef<boolean>(false);

  const [lockedPick, setLockedPick] = useState<SessionPick | null>(null);
  const [lockFailure, setLockFailure] = useState<string | null>(null);
  const sheetOpen = Boolean(search.sheet);
  const sheetMode: SideSheetMode = search.sheet ?? "SUGGESTIONS";
  const sheetPresetCode = search.trader ?? "FIB_GOLDEN_TRADER";
  const inspectedTradeId = search.tradeId ?? null;

  const updateSheetSearch = (patch: {
    sheet?: SideSheetMode;
    trader?: string;
    tradeId?: number;
  }) => {
    navigate({
      search: (prev: Record<string, unknown>) => ({
        ...prev,
        ...patch,
      }),
    });
  };
  const failureTimer = useRef<number | undefined>(undefined);
  const seenAutoTradesRef = useRef<Set<number> | null>(null);

  const pickIds = (loop.data?.picks ?? []).map((p) => p.id).join(",");
  const activeTradeIdsKey = (loop.data?.capital.activeTradeIds ?? []).join(",");
  const lockedPicksKey = (loop.data?.lockedPicks ?? []).map((p) => p.id).join(",");

  useEffect(() => {
    if (pickIds || activeTradeIdsKey || lockedPicksKey) {
      queryClient.invalidateQueries({ queryKey: sessionsQueryKeys.picks(sessionId) });
      queryClient.invalidateQueries({ queryKey: tradesQueryKeys.lists() });
    }
  }, [pickIds, activeTradeIdsKey, lockedPicksKey, sessionId, queryClient]);

  // In SEMI_AUTO / FULL_AUTO, when the session loop automatically locks & enters a trade,
  // navigate directly to its live Trader Graph page (/trades/$tradeId).
  useEffect(() => {
    const ids = loop.data?.capital.activeTradeIds ?? [];
    if (!session || !loop.data) return;
    if (seenAutoTradesRef.current === null) {
      seenAutoTradesRef.current = new Set(ids);
      if (
        (session.sessionType === "SEMI_AUTO" || session.sessionType === "FULL_AUTO") &&
        ids.length === 1
      ) {
        navigate({ to: "/trades/$tradeId", params: { tradeId: String(ids[0]) } });
      }
      return;
    }
    const newest = ids.find((tid) => !seenAutoTradesRef.current!.has(tid));
    ids.forEach((tid) => seenAutoTradesRef.current!.add(tid));
    if (newest && (session.sessionType === "SEMI_AUTO" || session.sessionType === "FULL_AUTO")) {
      navigate({ to: "/trades/$tradeId", params: { tradeId: String(newest) } });
    }
  }, [activeTradeIdsKey, session, loop.data, navigate]);

  useEffect(() => () => window.clearTimeout(failureTimer.current), []);

  // Automatically resume or start the underlying scanner loop when viewing an ACTIVE session
  useEffect(() => {
    if (!session || session.sessionStatus !== "ACTIVE" || oppCardsLoading) return;
    const targetCodes = session.scope === "INDEX" ? session.underlyings : session.commodityItems;
    if (!targetCodes || targetCodes.length === 0) return;

    const matchingRunning = oppCards.filter(
      (c) => targetCodes.includes(c.code) && c.master?.state === "RUNNING",
    );
    if (matchingRunning.length > 0) {
      if (!oppLoop.running) {
        resumeOpportunityLoop();
      }
      return;
    }

    if (!autoStartedScannerRef.current && hasResearch && !startScanner.isPending) {
      autoStartedScannerRef.current = true;
      startScanner.mutate({ underlyings: targetCodes });
    }
  }, [
    session,
    oppCards,
    oppCardsLoading,
    oppLoop.running,
    hasResearch,
    startScanner,
  ]);

  const handleLock = (pid: number) => {
    lockMutation.mutate(pid, {
      onSuccess: (locked) => {
        setLockedPick(locked);
      },
      onError: (err) => {
        setLockFailure(err instanceof Error ? err.message : "Trade lock failed");
        window.clearTimeout(failureTimer.current);
        failureTimer.current = window.setTimeout(() => setLockFailure(null), LOCK_FAILURE_MS);
      },
    });
  };

  if (isLoading || !session) {
    return (
      <div className="sd-page">
        <div className="sd-loading-box">Loading trading session #{id}…</div>
      </div>
    );
  }

  const underlyings = session.scope === "INDEX" ? session.underlyings : session.commodityItems;
  const runningScannersForSession = oppCards.filter(
    (c) => underlyings.includes(c.code) && c.master?.state === "RUNNING",
  ).length;
  const noResearchData =
    !hasResearch ||
    (startScanner.data && !startScanner.data.started && startScanner.data.reason === "NO_RESEARCH_DATA");
  const presets = presetsData ?? [];
  const activeSheetPreset = presets.find((p) => p.code === sheetPresetCode) ?? presets[0];

  const activeTraders =
    session.traders && session.traders.length > 0
      ? session.traders
      : ["FIB_GOLDEN_TRADER", "ORB_WAVE_TRADER", "FLOW_VWAP_TRADER"];
  const data = loop.data;
  const capital: SessionCapital = data?.capital ?? {
    capital: session.capital,
    realizedPnl: session.realizedPnl,
    currentCapital: session.currentCapital,
    committedPremium: 0,
    availableCapital: session.currentCapital,
    maxLossAmount: (session.capital * session.maxLossPercentage) / 100,
    lossUsed: Math.max(0, -session.realizedPnl),
    committedRisk: 0,
    remainingLossBudget: (session.capital * session.maxLossPercentage) / 100,
    lockedTrades: 0,
    activeTradesCount: 0,
    maxParallelTrades: 3,
    activeTradeIds: [],
  };

  const loopPill = loop.error
    ? { cls: "sd-status-pill is-red", label: "RECONNECTING" }
    : loop.running && data
      ? { cls: "sd-status-pill is-green", label: "LOOP LIVE" }
      : loop.connection === "connecting"
        ? { cls: "sd-status-pill is-amber", label: "CONNECTING" }
        : { cls: "sd-status-pill", label: "LOOP OFF" };

  const stateCopy = data && data.state !== "PICK_READY" ? STATE_COPY[data.state] : null;
  const pendingLockedPicks = data?.lockedPicks ?? [];
  const activeTrades = (sessionTrades.data?.list ?? []).filter((t) => t.tradeState === "RUNNING");

  const handleToggleTrader = (code: string) => {
    const exists = activeTraders.includes(code);
    if (exists && activeTraders.length <= 1) return; // keep at least 1 trader active
    const next = exists ? activeTraders.filter((c) => c !== code) : [...activeTraders, code];
    updateMutation.mutate({ id: session.id, payload: { traders: next } });
  };

  return (
    <div className="sd-page">
      {/* 1. Compact Top Bar matching StrategyDetailPage (.sd-topbar) */}
      <div className="sd-topbar">
        <div className="sd-topbar-left">
          <button
            type="button"
            className="sd-ctrl-btn"
            onClick={() => navigate({ to: "/sessions" })}
          >
            <ArrowLeft size={13} />
            <span>Sessions</span>
          </button>
          <span className="sd-topbar-sep" />
          <span className="sd-code-tag">{session.scope}</span>
          <span className="sd-ver-tag">
            {session.tradeDate} · {hhmm(session.startAt)}–{hhmm(session.closeAt)} IST
          </span>
          <span className={loopPill.cls}>
            <span className="sd-status-dot" />
            {loopPill.label}
          </span>
          <span className={statusPillClass(session.sessionStatus)}>
            <span className="sd-status-dot" />
            {session.sessionStatus}
          </span>
        </div>

        <div className="sd-topbar-right">
          {/* Segmented Mode Switcher: MANUAL / SEMI_AUTO / FULL_AUTO */}
          <div className="sd-seg-group" title="Switch session automation mode">
            {(["MANUAL", "SEMI_AUTO", "FULL_AUTO"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                className={`sd-seg-btn ${session.sessionType === mode ? "active" : ""}`}
                onClick={() =>
                  updateMutation.mutate({ id: session.id, payload: { sessionType: mode } })
                }
                disabled={updateMutation.isPending}
              >
                {mode}
              </button>
            ))}
          </div>

          {/* Upstox Live Order Toggle Switch */}
          <button
            type="button"
            className={`upstox-switch-btn ${
              session.routeThroughUpstox ? "upstox-switch-btn--live" : ""
            }`}
            onClick={() =>
              updateMutation.mutate({
                id: session.id,
                payload: { routeThroughUpstox: !session.routeThroughUpstox },
              })
            }
            disabled={updateMutation.isPending}
            title="Toggle direct Upstox order API execution for this session"
          >
            <div
              className={`upstox-switch-track ${
                session.routeThroughUpstox ? "upstox-switch-track--on" : ""
              }`}
            >
              <div className="upstox-switch-thumb" />
            </div>
            <Zap size={12} />
            <span>{session.routeThroughUpstox ? "UPSTOX LIVE" : "SIMULATED"}</span>
          </button>

          <button
            type="button"
            className="sd-ctrl-btn"
            onClick={() =>
              updateSheetSearch({
                sheet: "SUGGESTIONS",
                trader: activeTraders[0] ?? "FIB_GOLDEN_TRADER",
                tradeId: undefined,
              })
            }
          >
            <Sparkles size={13} />
            <span>Suggestions &amp; Fib+OA</span>
          </button>

          {session.sessionStatus === "ACTIVE" &&
            (runningScannersForSession > 0 ? (
              <button
                type="button"
                className="sd-ctrl-btn sd-ctrl-btn--danger"
                onClick={() => stopScanner.mutate()}
                disabled={stopScanner.isPending}
                title="Stop live underlying scanner"
              >
                <Square size={11} />
                <span>
                  {oppLoop.running && oppLoop.currentCode
                    ? `Scanning ${oppLoop.currentCode}… (Stop)`
                    : `Stop Scanner (${runningScannersForSession})`}
                </span>
              </button>
            ) : (
              <button
                type="button"
                className="sd-ctrl-btn sd-ctrl-btn--primary"
                onClick={() => startScanner.mutate({ underlyings })}
                disabled={startScanner.isPending || underlyings.length === 0}
                title="Start scanning underlyings for Trader setups"
              >
                {startScanner.isPending ? (
                  <Loader2 size={12} className="sp-spin" />
                ) : (
                  <Play size={12} />
                )}
                <span>{startScanner.isPending ? "Starting Scan…" : "Scan Live Setups"}</span>
              </button>
            ))}

          <button
            type="button"
            className="sd-ctrl-btn"
            onClick={() => navigate({ to: "/trades" })}
          >
            <Cpu size={13} />
            <span>Traders Desk</span>
          </button>
        </div>
      </div>

      {/* Research Engine Missing Alert (Why scanner cannot generate setups yet) */}
      {noResearchData && (
        <div
          className="card"
          style={{
            borderColor: "var(--warning-amber)",
            background: "var(--warning-amber-tint)",
            padding: "var(--space-3) var(--space-4)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "var(--space-3)",
            flexWrap: "wrap",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <AlertTriangle size={15} className="text-amber" />
            <span className="micro" style={{ color: "var(--warning-amber)" }}>
              <strong>Research Engine has no data for today yet.</strong> Run the Research Engine first so your Preset Traders can scan live option setups for {underlyings.join(", ")}.
            </span>
          </div>
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => navigate({ to: "/research" })}
          >
            <Sparkles size={13} />
            <span>Run Research Engine</span>
          </button>
        </div>
      )}

      {oppLoop.lastError && (
        <div className="card" style={{ borderColor: "var(--warning-amber)", padding: "var(--space-3)" }}>
          <div className="micro text-amber" style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
            <AlertTriangle size={14} />
            <span>Scanner Notice: {oppLoop.lastError}</span>
          </div>
        </div>
      )}

      {/* 2. Unified Session Summary & Assigned Traders Card (.sd-summary-card) */}
      <div className="sd-summary-card">
        <div className="sd-summary-head">
          <div className="sd-summary-title-block">
            <h1 className="sd-title">{session.name}</h1>
            <p className="sd-desc">
              {session.sessionType === "FULL_AUTO"
                ? "FULL_AUTO — Automatically selects, sizes, locks & enters the #1 setup from your assigned Preset Traders, steps SL/Target (e.g. 100→120→150), and auto-exits."
                : session.sessionType === "SEMI_AUTO"
                  ? "SEMI_AUTO — Automatically selects, sizes & locks the #1 setup into its Trader loop and opens the live trade graph with exit marks for your square-off."
                  : "MANUAL — Ranks top 4 setups from your assigned Preset Traders. Click Lock Trade to confirm entry price & lots."}
            </p>
          </div>

          <div className="sd-summary-badges">
            {underlyings.map((u) => (
              <span key={u} className="sd-tag sd-tag--cyan mono" title={UNDERLYING_NAMES[u] ?? u}>
                {u}
              </span>
            ))}
          </div>
        </div>

        {/* Assigned Preset Traders Strip (Interactive Toggle Pills) */}
        <div className="sd-notices-row">
          <div
            className="sd-compact-notice sd-compact-notice--cyan"
            style={{ justifyContent: "space-between", flexWrap: "wrap" }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
              <Cpu size={13} />
              <span>
                <strong>Assigned Preset Traders ({activeTraders.length}/3):</strong> Click to toggle which specialist Traders scan and manage positions in this session:
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
              {(["FIB_GOLDEN_TRADER", "ORB_WAVE_TRADER", "FLOW_VWAP_TRADER"] as const).map(
                (code) => {
                  const active = activeTraders.includes(code);
                  const meta = TRADER_META[code];
                  return (
                    <button
                      key={code}
                      type="button"
                      className={active ? meta.cls : "sd-tag"}
                      style={{
                        cursor: "pointer",
                        opacity: active ? 1 : 0.45,
                      }}
                      onClick={() => handleToggleTrader(code)}
                      disabled={updateMutation.isPending}
                      title={`${active ? "Active" : "Inactive"} — Click to toggle ${meta.label}`}
                    >
                      {active ? "● " : "○ "}
                      {meta.label} ({meta.tag})
                    </button>
                  );
                },
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 3. Capital, Risk Budget & Parallel Open Trades Strip */}
      <SessionCapitalStrip capital={capital} maxLossPercentage={session.maxLossPercentage} />

      {/* 4. Active Trader Loops Running in Parallel (max 3 open at once, unlimited total) */}
      {activeTrades.length > 0 && (
        <div className="card" style={{ padding: "var(--space-3) var(--space-4)" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "var(--space-2)",
            }}
          >
            <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
              <Activity size={15} className="text-green" />
              <span className="section-title" style={{ margin: 0 }}>
                Open Parallel Trader Loops ({activeTrades.length} / {capital.maxParallelTrades ?? 3}{" "}
                Max Open at Once)
              </span>
            </div>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => navigate({ to: "/trades" })}
            >
              <span>Open Traders Desk</span>
            </button>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: "var(--space-3)",
            }}
          >
            {activeTrades.map((t) => {
              const traderCode = t.marketTelemetry?.traderCode || t.traderProfile;
              const meta = TRADER_META[traderCode];
              return (
                <div
                  key={t.id}
                  className="sp-card sp-card--iterating"
                  onClick={() =>
                    updateSheetSearch({
                      sheet: "TRADE_INSPECT",
                      trader: traderCode,
                      tradeId: t.id,
                    })
                  }
                >
                  <div className="sp-card-top">
                    <span className="mono text-primary" style={{ fontWeight: 700 }}>
                      #{t.id} · {t.underlyingCode} {t.strike} {t.optionType}
                    </span>
                    <span className="badge badge--green">
                      <Radio size={10} /> LIVE 1s
                    </span>
                  </div>
                  {meta && (
                    <div>
                      <span className={meta.cls}>
                        {meta.label} · {meta.tag}
                      </span>
                    </div>
                  )}
                  <div className="micro text-secondary">
                    Entry {formatRupee(t.entryAt)} → LTP {formatRupee(t.lastPrice)} · SL{" "}
                    <span className="text-red">{formatRupee(t.currentStop)}</span> · Target{" "}
                    <span className="text-green">{formatRupee(t.currentTarget)}</span>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <span className={`mono ${t.netPnl >= 0 ? "text-green" : "text-red"}`}>
                      {formatRupee(t.netPnl)} ({t.pnlPct >= 0 ? "+" : ""}
                      {t.pnlPct.toFixed(1)}%)
                    </span>
                    <div
                      style={{ display: "inline-flex", gap: "10px", alignItems: "center" }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        type="button"
                        className="sd-link-btn"
                        onClick={() =>
                          updateSheetSearch({
                            sheet: "TRADE_INSPECT",
                            trader: traderCode,
                            tradeId: t.id,
                          })
                        }
                      >
                        Fib+OA Sidebar
                      </button>
                      <button
                        type="button"
                        className="sp-inspect-link"
                        onClick={() =>
                          navigate({ to: "/trades/$tradeId", params: { tradeId: String(t.id) } })
                        }
                      >
                        <span>Cockpit</span>
                        <ExternalLink size={12} />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Pending Locked Picks */}
      {pendingLockedPicks.length > 0 && (
        <div
          className="card"
          style={{
            padding: "var(--space-3) var(--space-4)",
            borderColor: "var(--bullish-green)",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "var(--space-2)",
            }}
          >
            <span className="section-title" style={{ margin: 0 }}>
              Locked &amp; Ready to Enter ({pendingLockedPicks.length})
            </span>
            <span className="micro text-muted">
              Click Enter &amp; Start Trader to launch the 1-second Trader loop
            </span>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-3)" }}>
            {pendingLockedPicks.map((lp) => (
              <div
                key={lp.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "var(--space-4)",
                  padding: "var(--space-2) var(--space-3)",
                  background: "var(--bg-elevated)",
                  borderRadius: "4px",
                  flex: "1 1 320px",
                }}
              >
                <div>
                  <div className="mono text-primary">
                    {lp.underlyingCode} {lp.strike} {lp.optionType} · {lp.lots} lot(s) ({lp.quantity}{" "}
                    qty)
                  </div>
                  <div className="micro text-secondary">
                    Lock Price {formatRupee(lp.lockedPrice ?? lp.entry)} · SL {formatRupee(lp.stop)}{" "}
                    · Target {formatRupee(lp.target)} · {lp.winProbPct.toFixed(0)}% win
                  </div>
                </div>
                <button
                  type="button"
                  className="btn btn--primary"
                  onClick={() => setLockedPick(lp)}
                >
                  <Play size={13} />
                  <span>Enter &amp; Start Trader</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {loop.error && (
        <div className="card" style={{ borderColor: "var(--bearish-red)" }}>
          <div
            className="micro text-red"
            style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}
          >
            <AlertTriangle size={14} />
            <span>{loop.error}</span>
          </div>
        </div>
      )}

      {lockFailure && (
        <div className="card" style={{ borderColor: "var(--bearish-red)" }}>
          <div
            className="micro text-red"
            style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}
          >
            <AlertTriangle size={14} />
            <span>Not locked: {lockFailure}</span>
          </div>
        </div>
      )}

      {data && data.picks.length > 0 ? (
        <>
          <div className="sl-table-head">
            <span className="section-title">Setups Discovered by Assigned Traders</span>
            <span className="badge badge--cyan">{data.picks.length} OPEN</span>
            <span className="micro text-muted">
              Best first. Locking opens the Enter Trade modal and launches a dedicated 1s Trader loop.
            </span>
          </div>
          <SessionOpportunityTable
            picks={data.picks}
            clockOffsetMs={loop.clockOffsetMs}
            lockingId={lockMutation.isPending ? (lockMutation.variables ?? null) : null}
            onLock={handleLock}
          />
        </>
      ) : (
        <div className="sl-wait">
          {stateCopy?.tone === "stop" ? (
            <Ban size={28} className="text-red" />
          ) : stateCopy?.tone === "info" ? (
            <Info size={28} className="text-muted" />
          ) : (
            <span className="sl-scan__dot" />
          )}
          <div className="sl-wait__body">
            <span className="sl-wait__title">
              {session.sessionStatus !== "ACTIVE"
                ? STATE_COPY.SESSION_CLOSED.title
                : (stateCopy?.title ?? "Preset Traders scanning for setups")}
            </span>
            <span className="micro text-muted">
              {data?.message ?? "Waiting for the next loop evaluation."}
            </span>
          </div>
          {data && data.state === "WAITING" && (
            <div className="sl-wait__chips">
              {oppLoop.running && (
                <span className="badge badge--cyan">
                  <Loader2 size={11} className="sp-spin" />{" "}
                  {oppLoop.currentCode
                    ? `Scanning ${oppLoop.currentCode} (R${oppLoop.round})`
                    : `Scanner Round #${oppLoop.round}`}
                </span>
              )}
              <span className="badge badge--slate">{data.scanned.candidates} candidates</span>
              {Object.entries(data.scanned.excluded).map(([reason, n]) => (
                <span key={reason} className="badge badge--slate">
                  {n} {reason}
                </span>
              ))}
              {runningScannersForSession === 0 && session.sessionStatus === "ACTIVE" && (
                <button
                  type="button"
                  className="btn btn--primary"
                  onClick={() => startScanner.mutate({ underlyings })}
                  disabled={startScanner.isPending}
                >
                  <Play size={12} />
                  <span>Scan Live Setups</span>
                </button>
              )}
              <button
                type="button"
                className="btn btn--ghost"
                onClick={() =>
                  updateSheetSearch({
                    sheet: "INSERT_TRADE",
                    trader: activeTraders[0] ?? "FIB_GOLDEN_TRADER",
                    tradeId: undefined,
                  })
                }
              >
                <Plus size={12} />
                <span>Insert Fib + OA Trade</span>
              </button>
            </div>
          )}

          {/* Per-Underlying Live Scanner Diagnostics (shows why 0 setups were found if market closed / no setup) */}
          {oppCards.filter((c) => underlyings.includes(c.code) && c.master).length > 0 && (
            <div
              style={{
                width: "100%",
                marginTop: "var(--space-2)",
                paddingTop: "var(--space-2)",
                borderTop: "1px solid var(--border-subtle)",
                display: "flex",
                gap: "var(--space-2)",
                flexWrap: "wrap",
              }}
            >
              {oppCards
                .filter((c) => underlyings.includes(c.code) && c.master)
                .map((c) => (
                  <span
                    key={c.code}
                    className={`badge ${c.master?.lastError ? "badge--red" : "badge--slate"} mono`}
                  >
                    {c.code}: Batch #{c.master?.iterationsCompleted ?? 0} ·{" "}
                    {c.master?.lastError
                      ? c.master.lastError
                      : c.master?.lastNote || `${c.master?.liveCount ?? 0} live setups`}
                  </span>
                ))}
            </div>
          )}
        </div>
      )}

      <div className="section-title">Session Pick &amp; Trade History</div>
      <SessionPickHistory
        picks={history.data?.list ?? []}
        isLoading={history.isLoading}
        onEnterLockedPick={(p) => setLockedPick(p)}
      />

      {lockedPick && <TradeLockModal pick={lockedPick} onClose={() => setLockedPick(null)} />}

      {sheetOpen && activeSheetPreset && (
        <TraderSideSheet
          mode={sheetMode}
          preset={activeSheetPreset}
          allPresets={presets}
          selectedTradeId={inspectedTradeId}
          defaultSessionId={session.id}
          onChangeMode={(m) => updateSheetSearch({ sheet: m })}
          onSelectPreset={(code) => updateSheetSearch({ trader: code })}
          onSelectTrade={(tid) => updateSheetSearch({ tradeId: tid })}
          onClose={() =>
            updateSheetSearch({ sheet: undefined, trader: undefined, tradeId: undefined })
          }
        />
      )}
    </div>
  );
};
