import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, ArrowLeft, Ban, ExternalLink, Info, Play, Radio, Zap } from "lucide-react";
import { useLockSessionPick, useSessionDetail, useSessionPicks, useUpdateSession } from "../hooks/useSessions";
import { useSessionLoop } from "../hooks/useSessionLoop";
import { sessionsQueryKeys } from "../queryKeys/sessionsQueryKeys";
import { SessionCapitalStrip } from "../components/SessionCapitalStrip";
import { SessionOpportunityTable } from "../components/SessionOpportunityTable";
import { SessionPickHistory } from "../components/SessionPickHistory";
import { TradeLockModal } from "../components/TradeLockModal";
import { UNDERLYING_NAMES } from "../../opportunities/components/underlyingNames";
import { formatRupee } from "../../opportunities/components/formatters";
import { useTradeSearch } from "../../trades/hooks/useTrades";
import { tradesQueryKeys } from "../../trades/queryKeys/tradesQueryKeys";
import {
  SessionCapital,
  SessionLoopStateName,
  SessionPick,
  SessionPickSearchFilter,
  TradingSession,
} from "../types/sessions.types";

const HISTORY_FILTER: SessionPickSearchFilter = { page: 0, limit: 20, sortBy: "createdAt", sortDir: "desc" };
const LOCK_FAILURE_MS = 6000;

const hhmm = (iso: string): string =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });

function statusBadgeClass(status: TradingSession["sessionStatus"]): string {
  if (status === "ACTIVE") return "badge badge--green";
  if (status === "CLOSED") return "badge badge--slate";
  return "badge badge--amber";
}

const STATE_COPY: Record<Exclude<SessionLoopStateName, "PICK_READY">, { title: string; tone: "scan" | "stop" | "info" }> = {
  SCHEDULED: { title: "Waiting for the session start time", tone: "info" },
  WAITING: { title: "Scanning for the best trade", tone: "scan" },
  HALTED: { title: "Halted: loss limit reached", tone: "stop" },
  SESSION_CLOSED: { title: "This session is not tradable", tone: "stop" },
  UNSUPPORTED_TYPE: { title: "Loop not defined for this session type yet", tone: "info" },
};

export const SessionDetailPage: React.FC = () => {
  const { id } = useParams({ strict: false }) as { id: string };
  const navigate = useNavigate();
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

  const [lockedPick, setLockedPick] = useState<SessionPick | null>(null);
  const [lockFailure, setLockFailure] = useState<string | null>(null);
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
      <div className="page-container">
        <div className="empty-state">
          <div className="empty-state__title">Loading session...</div>
        </div>
      </div>
    );
  }

  const underlyings = session.scope === "INDEX" ? session.underlyings : session.commodityItems;
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

  const loopBadge = loop.error
    ? { cls: "badge badge--red", label: "RECONNECTING" }
    : loop.running && data
      ? { cls: "badge badge--green", label: "LIVE" }
      : loop.connection === "connecting"
        ? { cls: "badge badge--amber", label: "CONNECTING" }
        : { cls: "badge badge--slate", label: "LOOP OFF" };

  const stateCopy = data && data.state !== "PICK_READY" ? STATE_COPY[data.state] : null;
  const pendingLockedPicks = data?.lockedPicks ?? [];
  const activeTrades = (sessionTrades.data?.list ?? []).filter((t) => t.tradeState === "RUNNING");

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <button type="button" className="btn btn--ghost" onClick={() => navigate({ to: "/sessions" })}>
            <ArrowLeft size={14} />
            <span>Back</span>
          </button>
          <h1 className="page-title" style={{ marginTop: "var(--space-2)" }}>{session.name}</h1>
          <p className="text-secondary micro">
            {session.tradeDate} · {hhmm(session.startAt)}–{hhmm(session.closeAt)} IST · {session.scope} ·{" "}
            <strong>{session.sessionType}</strong> ·{" "}
            {session.routeThroughUpstox ? "Live (Upstox Orders)" : "Simulated"} ·{" "}
            {underlyings.map((u) => `${u} (${UNDERLYING_NAMES[u] ?? u})`).join(", ") || "No underlyings"}
          </p>
        </div>
        <div className="page-actions" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap" }}>
          <div style={{ display: "inline-flex", gap: 4 }}>
            {(["MANUAL", "SEMI_AUTO", "FULL_AUTO"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                className={`toggle-chip ${session.sessionType === mode ? "toggle-chip--active" : ""}`}
                onClick={() =>
                  updateMutation.mutate({ id: session.id, payload: { sessionType: mode } })
                }
                disabled={updateMutation.isPending}
                title={`Switch session mode to ${mode}`}
              >
                {mode}
              </button>
            ))}
          </div>
          <button
            type="button"
            className={`upstox-switch-btn ${session.routeThroughUpstox ? "upstox-switch-btn--live" : ""}`}
            onClick={() =>
              updateMutation.mutate({
                id: session.id,
                payload: { routeThroughUpstox: !session.routeThroughUpstox },
              })
            }
            disabled={updateMutation.isPending}
            title="Toggle direct Upstox order API execution for this session"
          >
            <div className={`upstox-switch-track ${session.routeThroughUpstox ? "upstox-switch-track--on" : ""}`}>
              <div className="upstox-switch-thumb" />
            </div>
            <Zap size={12} />
            <span>{session.routeThroughUpstox ? "UPSTOX LIVE" : "SIMULATED"}</span>
          </button>
          <span className={loopBadge.cls}>
            <Radio size={12} />
            <span>{loopBadge.label}</span>
          </span>
          <span className={statusBadgeClass(session.sessionStatus)}>{session.sessionStatus}</span>
        </div>
      </div>

      <div className="content-body sl-page">
        <SessionCapitalStrip capital={capital} maxLossPercentage={session.maxLossPercentage} />

        {/* Active Trader Loops Running in Parallel (max 3) */}
        {activeTrades.length > 0 && (
          <div className="card" style={{ padding: "var(--space-3) var(--space-4)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-2)" }}>
              <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
                <Activity size={15} className="text-green" />
                <span className="section-title" style={{ margin: 0 }}>
                  Active Trader Loops ({activeTrades.length} / {capital.maxParallelTrades ?? 3} Parallel)
                </span>
              </div>
              <button type="button" className="btn btn--ghost" onClick={() => navigate({ to: "/trades" })}>
                <span>View All Trades</span>
              </button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "var(--space-3)" }}>
              {activeTrades.map((t) => (
                <div
                  key={t.id}
                  className="card"
                  style={{ padding: "var(--space-3)", cursor: "pointer", borderColor: "var(--border-subtle)" }}
                  onClick={() => navigate({ to: "/trades/$tradeId", params: { tradeId: String(t.id) } })}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span className="mono text-primary">
                      #{t.id} · {t.underlyingCode} {t.strike} {t.optionType}
                    </span>
                    <span className="badge badge--green">LIVE</span>
                  </div>
                  <div className="micro text-secondary" style={{ marginTop: "var(--space-1)" }}>
                    Entry {formatRupee(t.entryAt)} → LTP {formatRupee(t.lastPrice)} · SL {formatRupee(t.currentStop)} · Target{" "}
                    {formatRupee(t.currentTarget)}
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "var(--space-2)" }}>
                    <span className={`mono ${t.netPnl >= 0 ? "text-green" : "text-red"}`}>
                      {formatRupee(t.netPnl)} ({t.pnlPct >= 0 ? "+" : ""}{t.pnlPct.toFixed(1)}%)
                    </span>
                    <span className="micro text-secondary" style={{ display: "flex", gap: "4px", alignItems: "center" }}>
                      <span>Open Cockpit</span>
                      <ExternalLink size={12} />
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Auto-locked picks in SEMI_AUTO (or locked picks awaiting entry) */}
        {pendingLockedPicks.length > 0 && (
          <div className="card" style={{ padding: "var(--space-3) var(--space-4)", borderColor: "var(--bullish-green)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-2)" }}>
              <span className="section-title" style={{ margin: 0 }}>
                Locked & Ready to Enter ({pendingLockedPicks.length})
              </span>
              <span className="micro text-muted">
                {session.sessionType === "SEMI_AUTO"
                  ? "Auto-selected best opportunity — confirm entry to start Trader loop"
                  : "Locked pick — click Start Trader to enter position"}
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
                      {lp.underlyingCode} {lp.strike} {lp.optionType} · {lp.lots} lot(s) ({lp.quantity} qty)
                    </div>
                    <div className="micro text-secondary">
                      Lock Price {formatRupee(lp.lockedPrice ?? lp.entry)} · SL {formatRupee(lp.stop)} · Target{" "}
                      {formatRupee(lp.target)} · {lp.winProbPct.toFixed(0)}% win
                    </div>
                  </div>
                  <button type="button" className="btn btn--primary" onClick={() => setLockedPick(lp)}>
                    <Play size={13} />
                    <span>Enter & Start Trader</span>
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {loop.error && (
          <div className="card" style={{ borderColor: "var(--bearish-red)" }}>
            <div className="micro text-red" style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
              <AlertTriangle size={14} />
              <span>{loop.error}</span>
            </div>
          </div>
        )}

        {lockFailure && (
          <div className="card" style={{ borderColor: "var(--bearish-red)" }}>
            <div className="micro text-red" style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
              <AlertTriangle size={14} />
              <span>Not locked: {lockFailure}</span>
            </div>
          </div>
        )}

        {data && data.picks.length > 0 ? (
          <>
            <div className="sl-table-head">
              <span className="section-title">Trades to take</span>
              <span className="badge badge--cyan">{data.picks.length} OPEN</span>
              <span className="micro text-muted">
                Best first. Locking opens the Enter Trade modal and launches a dedicated Trader loop.
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
                  : (stateCopy?.title ?? "Scanning for opportunities")}
              </span>
              <span className="micro text-muted">
                {data?.message ?? "Waiting for the first update."}
              </span>
            </div>
            {data && data.state === "WAITING" && (
              <div className="sl-wait__chips">
                <span className="badge badge--slate">{data.scanned.candidates} saved</span>
                {Object.entries(data.scanned.excluded).map(([reason, n]) => (
                  <span key={reason} className="badge badge--slate">
                    {n} {reason}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="section-title">Picks this session</div>
        <SessionPickHistory
          picks={history.data?.list ?? []}
          isLoading={history.isLoading}
          onEnterLockedPick={(p) => setLockedPick(p)}
        />
      </div>

      {lockedPick && <TradeLockModal pick={lockedPick} onClose={() => setLockedPick(null)} />}
    </div>
  );
};
