import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, Ban, Info, Radio } from "lucide-react";
import { useLockSessionPick, useSessionDetail, useSessionPicks } from "../hooks/useSessions";
import { useSessionLoop } from "../hooks/useSessionLoop";
import { sessionsQueryKeys } from "../queryKeys/sessionsQueryKeys";
import { SessionCapitalStrip } from "../components/SessionCapitalStrip";
import { SessionOpportunityTable } from "../components/SessionOpportunityTable";
import { SessionPickHistory } from "../components/SessionPickHistory";
import { TradeLockModal } from "../components/TradeLockModal";
import { UNDERLYING_NAMES } from "../../opportunities/components/underlyingNames";
import { SessionCapital, SessionLoopStateName, SessionPick, SessionPickSearchFilter, TradingSession } from "../types/sessions.types";

const HISTORY_FILTER: SessionPickSearchFilter = { page: 0, limit: 20, sortBy: "createdAt", sortDir: "desc" };
const LOCK_FAILURE_MS = 6000;

const hhmm = (iso: string): string =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });

function statusBadgeClass(status: TradingSession["sessionStatus"]): string {
  if (status === "ACTIVE") return "badge badge--green";
  if (status === "CLOSED") return "badge badge--slate";
  return "badge badge--amber"; // EXPIRED
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
  const isManual = session?.sessionType === "MANUAL";
  const loop = useSessionLoop(sessionId, !!session && isManual && session.sessionStatus === "ACTIVE");
  const history = useSessionPicks(sessionId, HISTORY_FILTER);
  const lockMutation = useLockSessionPick(sessionId);

  const [lockedPick, setLockedPick] = useState<SessionPick | null>(null); // drives the Trade Lock popup
  const [lockFailure, setLockFailure] = useState<string | null>(null);
  const failureTimer = useRef<number | undefined>(undefined);
  const pickIds = (loop.data?.picks ?? []).map((p) => p.id).join(",");

  // A new pick (or a state change) means the history changed.
  useEffect(() => {
    if (pickIds) queryClient.invalidateQueries({ queryKey: sessionsQueryKeys.picks(sessionId) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pickIds, sessionId]);

  useEffect(() => () => window.clearTimeout(failureTimer.current), []);

  const handleLock = (pid: number) => {
    lockMutation.mutate(pid, {
      onSuccess: (locked) => {
        setLockedPick(locked); // popup with the item's current price; the server pushes the next pick by itself
      },
      onError: (err) => {
        // The loop swaps in the next pick right away, so the reason must outlive the card it belonged to.
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
  };

  const loopBadge = loop.error
    ? { cls: "badge badge--red", label: "RECONNECTING" }
    : loop.running && data
      ? { cls: "badge badge--green", label: "LIVE" }
      : loop.connection === "connecting"
        ? { cls: "badge badge--amber", label: "CONNECTING" }
        : { cls: "badge badge--slate", label: "LOOP OFF" };

  const stateCopy = data && data.state !== "PICK_READY" ? STATE_COPY[data.state] : null;

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
            {session.tradeDate} · {hhmm(session.startAt)}–{hhmm(session.closeAt)} IST · {session.scope} · {session.sessionType} ·{" "}
            {session.routeThroughUpstox ? "Live (Upstox)" : "Simulated"} ·{" "}
            {underlyings.map((u) => `${u} (${UNDERLYING_NAMES[u] ?? u})`).join(", ") || "No underlyings"}
          </p>
        </div>
        <div className="page-actions">
          <span className={loopBadge.cls}>
            <Radio size={12} />
            <span>{loopBadge.label}</span>
          </span>
          <span className={statusBadgeClass(session.sessionStatus)}>{session.sessionStatus}</span>
        </div>
      </div>

      <div className="content-body sl-page">
        <SessionCapitalStrip capital={capital} maxLossPercentage={session.maxLossPercentage} />

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
              <span className="micro text-muted">Best first. A row can be locked until its opportunity expires.</span>
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
            ) : stateCopy?.tone === "info" || !isManual ? (
              <Info size={28} className="text-muted" />
            ) : (
              <span className="sl-scan__dot" />
            )}
            <div className="sl-wait__body">
              <span className="sl-wait__title">
                {!isManual
                  ? STATE_COPY.UNSUPPORTED_TYPE.title
                  : session.sessionStatus !== "ACTIVE"
                    ? STATE_COPY.SESSION_CLOSED.title
                    : (stateCopy?.title ?? "Connecting to the session loop")}
              </span>
              <span className="micro text-muted">
                {!isManual
                  ? `${session.sessionType} sessions are not defined yet; only MANUAL sessions run the loop.`
                  : (data?.message ?? "Waiting for the first update.")}
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
        <SessionPickHistory picks={history.data?.list ?? []} isLoading={history.isLoading} />
      </div>

      {lockedPick && <TradeLockModal pick={lockedPick} onClose={() => setLockedPick(null)} />}
    </div>
  );
};
