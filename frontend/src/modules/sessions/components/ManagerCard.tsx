import React from "react";
import { AlertTriangle, Bot, CheckCircle2, Layers3, Lock, Radio, ShieldCheck } from "lucide-react";
import { RiskLevel, SessionManagerAdvice } from "../types/sessions.types";

interface Props {
  advice: SessionManagerAdvice | null | undefined;
  stateTitle: string;
  stateMessage: string;
  openCount: number;
  candidates: number;
  riskLevel: RiskLevel;
  locking: boolean;
  canLock: boolean;
  onLock: (pickId: number) => void;
  onShow: (pickId: number) => void;
}

/** The session manager: which open setup to take now and why, from capital, loss budget, risk level and track record. */
export const ManagerCard: React.FC<Props> = ({
  advice,
  stateTitle,
  stateMessage,
  openCount,
  candidates,
  riskLevel,
  locking,
  canLock,
  onLock,
  onShow,
}) => (
  <section className={`te-workspace ${advice ? "te-workspace--best" : ""}`} aria-label="Session manager">
    <div className="te-workspace__top">
      <div className="te-workspace__copy">
        <span className="te-workspace__icon">
          <Bot size={18} />
        </span>
        <div>
          <span className="te-eyebrow">Session manager · best suggestion</span>
          <h2>{advice ? advice.headline : stateTitle}</h2>
          <p>{advice ? "Ranked on expected rupees after charges, then confidence, then reward:risk." : stateMessage}</p>
        </div>
      </div>
      <div className="te-chips">
        <span className="te-chip">
          <Radio size={13} />
          <strong>{openCount}</strong> open
        </span>
        <span className="te-chip">
          <Layers3 size={13} />
          <strong>{candidates}</strong> scanned
        </span>
        <span className="te-chip">
          <ShieldCheck size={13} />
          <strong>{riskLevel}</strong> risk
        </span>
      </div>
    </div>

    {advice && (
      <>
        <div className="te-why">
          <ul>
            {advice.reasons.map((r) => (
              <li key={r}>
                <CheckCircle2 size={13} className="text-green" />
                <span>{r}</span>
              </li>
            ))}
          </ul>
          <ul>
            {advice.cautions.map((c) => (
              <li key={c}>
                <AlertTriangle size={13} className="text-amber" />
                <span>{c}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="te-workspace__actions">
          {advice.alternatives > 0 && (
            <span className="micro text-muted">
              {advice.alternatives} other setup{advice.alternatives === 1 ? "" : "s"} below
            </span>
          )}
          <button type="button" className="te-btn te-btn--ghost" onClick={() => onShow(advice.pickId)}>
            Show details
          </button>
          <button
            type="button"
            className="te-btn te-btn--primary"
            disabled={!canLock || locking}
            onClick={() => onLock(advice.pickId)}
          >
            <Lock size={13} /> {locking ? "Locking…" : "Lock this trade"}
          </button>
        </div>
      </>
    )}
  </section>
);
