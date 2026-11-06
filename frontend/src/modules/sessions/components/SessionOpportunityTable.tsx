import React, { useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Lock, TrendingDown, TrendingUp } from "lucide-react";
import { SessionPick } from "../types/sessions.types";
import { useCountdown } from "../hooks/useSessionLoop";
import { PriceLadder } from "./PriceLadder";
import { formatExpiry, formatRupee } from "../../opportunities/components/formatters";

const px = (n: number): string => n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const inr = (n: number): string => `₹${Math.round(n).toLocaleString("en-IN")}`;
const hms = (iso: string | null): string =>
  iso ? new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false }) : "";

interface CardProps {
  pick: SessionPick;
  clockOffsetMs: number;
  locking: boolean;
  onLock: (pickId: number) => void;
}

const OpportunityCard: React.FC<CardProps> = ({ pick: p, clockOffsetMs, locking, onLock }) => {
  const [open, setOpen] = useState(false);
  const left = useCountdown(p.expiresAt, clockOffsetMs);
  const live = p.pickState === "OFFERED" && left > 0;
  const ce = p.optionType === "CE";
  const now = Date.now() + clockOffsetMs;
  const signalAge = Math.max(0, Math.round((now - Date.parse(p.signalAt)) / 1000));
  const holdMinutes = Math.max(0, Math.round((Date.parse(p.holdUntil) - now) / 60000));

  return (
    <div className={`card sl-card ${live ? "" : "sl-card--dead"}`}>
      <div className="sl-card__head">
        <span className={`sl-dir ${ce ? "sl-dir--ce" : "sl-dir--pe"}`} title={ce ? "Buy call" : "Buy put"}>
          {ce ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
        </span>
        <div className="sl-trade__name">
          <span className="mono text-heading">
            {p.underlyingCode} {p.strike} {p.optionType}
          </span>
          <span className="micro text-muted">
            {formatExpiry(p.expiry)}
            {p.strategy ? ` · ${p.strategy}` : ""}
          </span>
        </div>
        <div className="sl-win sl-card__win">
          <span className="mono">{p.winProbPct.toFixed(0)}% win</span>
          <span className="sl-win__track">
            <span
              className={`sl-win__fill ${p.winProbPct >= 85 ? "sl-win__fill--high" : p.winProbPct <= 55 ? "sl-win__fill--low" : ""}`}
              style={{ width: `${p.winProbPct}%` }}
            />
          </span>
        </div>
      </div>

      <div className="sl-card__grid">
        <div className="sl-stat">
          <span className="label">Entry area ₹</span>
          <span className="sl-stat__value">{px(p.entry)} – {px(p.entryMax)}</span>
        </div>
        <div className="sl-stat">
          <span className="label">Stop loss ₹</span>
          <span className="sl-stat__value text-red">{px(p.stop)} <span className="micro text-muted">−{p.stopPct.toFixed(1)}%</span></span>
        </div>
        <div className="sl-stat">
          <span className="label">Target ₹</span>
          <span className="sl-stat__value text-green">{px(p.target)} <span className="micro text-muted">+{p.targetPct.toFixed(1)}%</span></span>
        </div>
        <div className="sl-stat">
          <span className="label">Quantity</span>
          <span className="sl-stat__value">{p.lots} × {p.lotUnits} = {p.quantity}</span>
        </div>
        <div className="sl-stat">
          <span className="label">Capital · R:R</span>
          <span className="sl-stat__value">{inr(p.capitalRequired)} <span className="micro text-muted">{p.usagePct.toFixed(0)}% · {p.rewardRisk.toFixed(2)}</span></span>
        </div>
        <div className="sl-stat">
          <span className="label">Stopped / target</span>
          <span className="sl-stat__value">
            <span className="text-red">−{inr(p.riskAmount)}</span> <span className="text-green">+{inr(p.rewardAmount)}</span>
          </span>
        </div>
      </div>

      <div className="sl-card__foot">
        <button type="button" className="btn btn--ghost" onClick={() => setOpen((o) => !o)}>
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <span>{open ? "Hide details" : "Details"}</span>
        </button>
        <button type="button" className="sl-lock sl-lock--sm" disabled={!live || locking} onClick={() => onLock(p.id)}>
          <span className="sl-lock__label">
            <Lock size={13} />
            <span>{locking ? "LOCKING…" : live ? "LOCK TRADE" : "CLOSED"}</span>
          </span>
        </button>
      </div>

      {open && (
        <div className="sl-detail sl-card__detail">
          <PriceLadder stop={p.stop} entry={p.entry} entryMax={p.entryMax} target={p.target} stopPct={p.stopPct} targetPct={p.targetPct} />
          <div className="sl-detail__why">
            <ul className="sl-points">
              {p.reasons.slice(0, 4).map((r, i) => (
                <li key={`r${i}`}>
                  <CheckCircle2 size={14} className="text-green" />
                  <span>{r}</span>
                </li>
              ))}
              {p.risks.slice(0, 3).map((r, i) => (
                <li key={`k${i}`}>
                  <AlertTriangle size={14} className="text-amber" />
                  <span>{r}</span>
                </li>
              ))}
            </ul>
            <span className="micro text-muted">
              Expected {inr(p.expectedNet)} after charges. Signal {signalAge}s old. Valid until {hms(p.holdUntil)} IST, hold up to {holdMinutes} min. Do not buy above{" "}
              {formatRupee(p.entryMax)}: reward drops below 1.2× risk.
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

interface Props {
  picks: SessionPick[];
  clockOffsetMs: number;
  lockingId: number | null;
  onLock: (pickId: number) => void;
}

/** Open trades grouped per underlying, two cards per row. Each card has its own Lock Trade button. */
export const SessionOpportunityTable: React.FC<Props> = ({ picks, clockOffsetMs, lockingId, onLock }) => {
  const groups = new Map<string, SessionPick[]>();
  picks.forEach((p) => groups.set(p.underlyingCode, [...(groups.get(p.underlyingCode) ?? []), p]));

  return (
    <div className="sl-groups">
      {[...groups.entries()].map(([code, list]) => (
        <section key={code} className="sl-group">
          <div className="sl-table-head">
            <span className="section-title">{code}</span>
            <span className="badge badge--cyan">{list.length} OPEN</span>
          </div>
          <div className="sl-card-grid">
            {list.map((p) => (
              <OpportunityCard key={p.id} pick={p} clockOffsetMs={clockOffsetMs} locking={lockingId === p.id} onLock={onLock} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
};
