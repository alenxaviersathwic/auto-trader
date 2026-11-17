import React from "react";
import { AlertTriangle, ArrowRightLeft, Bot, CheckCircle2, Filter, Lock, ScanSearch, Sparkles, Trophy } from "lucide-react";
import { TRADER_META, managerFor, managersFor } from "../../../trade-history/components/traderMeta";
import { TraderCode } from "../../../trade-history/types/trades.types";
import { SessionLoopStateName, SessionManagerAdvice } from "../../types/sessions.types";
import { AgentAvatar, AgentTone } from "./AgentAvatar";
import { FinderRadar, FinderStatus } from "./FinderRadar";

export type ScannerStatus = FinderStatus;

interface Props {
  managerCode: TraderCode | null; // null: an old session that still runs both traders
  /** The session's scope (managers are the same for every scope). */
  scope?: string | null;
  /** The opportunity finders feeding the session (their optionTypes cover its scope). */
  finderCodes?: TraderCode[];
  state: SessionLoopStateName | null;
  message: string;
  isActive: boolean;
  scanners: ScannerStatus[];
  scannersRunning: number;
  /** The index the scan loop is on right now (null when it does not say). */
  scanningCode: string | null;
  candidates: number;
  excluded: [string, number][];
  openCount: number;
  advice: SessionManagerAdvice | null | undefined;
  locking: boolean;
  switching: boolean;
  onLock: (pickId: number) => void;
  onShow: (pickId: number) => void;
  onSwitch: (code: TraderCode) => void;
  /** The manager's sub-agents, drawn under it. */
  children?: React.ReactNode;
}

type StepState = "done" | "active" | "idle" | "warn";

const STATUS: Record<SessionLoopStateName, { label: string; tone: AgentTone }> = {
  SCHEDULED: { label: "Scheduled", tone: "idle" },
  WAITING: { label: "Watching", tone: "live" },
  PICK_READY: { label: "Suggestion ready", tone: "ready" },
  HALTED: { label: "Halted", tone: "alert" },
  SESSION_CLOSED: { label: "Session closed", tone: "idle" },
  UNSUPPORTED_TYPE: { label: "No loop", tone: "idle" },
};

const Step: React.FC<{ state: StepState; icon: React.ReactNode; title: string; detail?: React.ReactNode;
  children?: React.ReactNode }> = ({ state, icon, title, detail, children }) => (
  <li className={`ag-step ag-step--${state}`}>
    <span className="ag-step__node" aria-hidden="true">
      {state === "done" ? <CheckCircle2 size={13} /> : icon}
    </span>
    <div className="ag-step__body">
      <div className="ag-step__title">
        {title}
        {detail && <span className="ag-step__detail">{detail}</span>}
      </div>
      {children}
    </div>
  </li>
);

/**
 * The session manager as an agent: who it is, what it is doing now, and the trace of its last pass (scan -> filter
 * -> rank -> decide), with the decision's Lock button. Its sub-agents (the autopsy) are rendered under it.
 */
export const ManagerAgentPanel: React.FC<Props> = (p) => {
  const manager = p.managerCode ? managerFor(p.managerCode) : null;
  const finders = (p.finderCodes ?? []).map((c) => TRADER_META[c]).filter(Boolean);
  const other = managersFor(p.scope).filter((m) => m.traderCode !== p.managerCode);
  const status = p.state ? STATUS[p.state] : { label: p.isActive ? "Connecting" : "Session closed", tone: "idle" as AgentTone };
  const skipped = p.excluded.reduce((n, [, c]) => n + c, 0);
  const scanned = p.candidates > 0 || p.scannersRunning > 0;

  return (
    <section className={`ag-panel ag-panel--${status.tone}`} aria-label="Session manager agent">
      <header className="ag-panel__head">
        <AgentAvatar icon={<Bot size={18} />} tone={status.tone} label={`Session manager: ${status.label}`} />
        <div className="ag-panel__id">
          <span className="ag-eyebrow">Session manager agent</span>
          <h2 className="ag-panel__name">
            {manager ? manager.name : "Both traders (older session)"}
            {finders.map((f) => (
              <span key={f.code} className={`badge ${f.badgeClass} mono`} title={`Finder: ${f.name}`}>
                {f.tag}
              </span>
            ))}
          </h2>
          <span className="ag-panel__status">
            <span className={`ag-status ag-status--${status.tone}`}>{status.label}</span>
            <span className="text-muted">{p.message}</span>
          </span>
        </div>
        {p.isActive && (
          <div className="ag-panel__switch">
            {other.map((m) => (
              <button
                key={m.traderCode}
                type="button"
                className="te-btn te-btn--ghost te-btn--xs"
                disabled={p.switching}
                onClick={() => p.onSwitch(m.traderCode)}
                title={`Hand this session to ${m.name}; the finders stay the same`}
              >
                <ArrowRightLeft size={11} /> {p.managerCode ? `Switch to ${m.name}` : `Use ${m.name}`}
              </button>
            ))}
          </div>
        )}
      </header>

      <ol className="ag-trace" aria-label="Last pass">
        <Step
          state={!p.isActive ? "idle" : p.scannersRunning > 0 ? (p.candidates > 0 ? "done" : "active") : "warn"}
          icon={<ScanSearch size={13} />}
          title="Scan"
          detail={
            p.scannersRunning > 0
              ? `${p.scannersRunning}/${p.scanners.length} scanners · ${p.candidates} candidate${p.candidates === 1 ? "" : "s"}`
              : "scanner stopped"
          }
        >
          {p.scanners.length > 0 && (
            <FinderRadar
              finders={p.scanners}
              currentCode={p.scanningCode}
              traderName={finders.length ? finders.map((f) => f.name).join(" + ") : "Both traders"}
              active={p.isActive}
            />
          )}
        </Step>
        <Step
          state={!scanned ? "idle" : "done"}
          icon={<Filter size={13} />}
          title="Filter"
          detail={skipped > 0 ? `${skipped} skipped` : scanned ? "nothing skipped" : undefined}
        >
          {skipped > 0 && (
            <div className="ag-reasons">
              {p.excluded.slice(0, 4).map(([reason, n]) => (
                <span key={reason} className="ag-reason">
                  <span className="mono">{n}×</span> {reason}
                </span>
              ))}
            </div>
          )}
        </Step>
        <Step
          state={p.openCount > 0 ? "done" : "idle"}
          icon={<Trophy size={13} />}
          title="Rank"
          detail={p.openCount > 0 ? `${p.openCount} open · by expected net after charges` : "no setup passed"}
        />
        <Step
          state={p.advice ? "active" : "idle"}
          icon={<Sparkles size={13} />}
          title="Decide"
          detail={p.advice ? undefined : "no suggestion yet"}
        >
          {p.advice && (
            <div className="ag-decision">
              <div className="ag-decision__headline">{p.advice.headline}</div>
              <ul className="ag-decision__why">
                {p.advice.reasons.map((r) => (
                  <li key={r}>
                    <CheckCircle2 size={12} className="text-green" /> {r}
                  </li>
                ))}
                {p.advice.cautions.map((c) => (
                  <li key={c}>
                    <AlertTriangle size={12} className="text-amber" /> {c}
                  </li>
                ))}
              </ul>
              <div className="ag-decision__actions">
                {p.advice.alternatives > 0 && (
                  <span className="micro text-muted">+{p.advice.alternatives} other</span>
                )}
                <button type="button" className="te-btn te-btn--ghost te-btn--sm" onClick={() => p.onShow(p.advice!.pickId)}>
                  Details
                </button>
                <button
                  type="button"
                  className="te-btn te-btn--primary te-btn--sm"
                  disabled={!p.isActive || p.locking}
                  onClick={() => p.onLock(p.advice!.pickId)}
                >
                  <Lock size={12} /> {p.locking ? "Locking…" : "Lock this trade"}
                </button>
              </div>
            </div>
          )}
        </Step>
      </ol>

      {p.children && <div className="ag-subs">{p.children}</div>}
    </section>
  );
};
