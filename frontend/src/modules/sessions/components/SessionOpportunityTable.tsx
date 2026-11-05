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

interface RowProps {
  pick: SessionPick;
  clockOffsetMs: number;
  locking: boolean;
  onLock: (pickId: number) => void;
}

const OpportunityRow: React.FC<RowProps> = ({ pick: p, clockOffsetMs, locking, onLock }) => {
  const [open, setOpen] = useState(false);
  const left = useCountdown(p.expiresAt, clockOffsetMs);
  const live = p.pickState === "OFFERED" && left > 0;
  const ce = p.optionType === "CE";
  const now = Date.now() + clockOffsetMs;
  const signalAge = Math.max(0, Math.round((now - Date.parse(p.signalAt)) / 1000));
  const holdMinutes = Math.max(0, Math.round((Date.parse(p.holdUntil) - now) / 60000));

  return (
    <>
      <tr className={`sl-row ${live ? "" : "sl-row--dead"}`} onClick={() => setOpen((o) => !o)}>
        <td>
          <div className="sl-trade">
            {open ? <ChevronDown size={14} className="text-muted" /> : <ChevronRight size={14} className="text-muted" />}
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
          </div>
        </td>
        <td>
          <div className="sl-win">
            <span className="mono">{p.winProbPct.toFixed(0)}%</span>
            <span className="sl-win__track">
              <span
                className={`sl-win__fill ${p.winProbPct >= 85 ? "sl-win__fill--high" : p.winProbPct <= 55 ? "sl-win__fill--low" : ""}`}
                style={{ width: `${p.winProbPct}%` }}
              />
            </span>
          </div>
        </td>
        <td className="mono">
          {px(p.entry)} – {px(p.entryMax)}
        </td>
        <td>
          <span className="mono text-red">{px(p.stop)}</span>
          <div className="micro text-muted">−{p.stopPct.toFixed(1)}%</div>
        </td>
        <td>
          <span className="mono text-green">{px(p.target)}</span>
          <div className="micro text-muted">+{p.targetPct.toFixed(1)}% · R:R {p.rewardRisk.toFixed(2)}</div>
        </td>
        <td>
          <span className="mono">
            {p.lots} × {p.lotUnits} = {p.quantity}
          </span>
          <div className="micro text-muted">
            {inr(p.capitalRequired)} · {p.usagePct.toFixed(0)}% of free
          </div>
        </td>
        <td>
          <span className="mono text-red">−{inr(p.riskAmount)}</span>
          <span className="mono text-green sl-pnl-gap">+{inr(p.rewardAmount)}</span>
        </td>
        <td className="sl-col-lock" onClick={(e) => e.stopPropagation()}>
          <button
            type="button"
            className="sl-lock sl-lock--sm"
            disabled={!live || locking}
            onClick={() => onLock(p.id)}
          >
            <span className="sl-lock__label">
              <Lock size={13} />
              <span>{locking ? "LOCKING…" : live ? "LOCK" : "CLOSED"}</span>
            </span>
          </button>
        </td>
      </tr>
      {open && (
        <tr className="sl-row-detail">
          <td colSpan={8}>
            <div className="sl-detail">
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
          </td>
        </tr>
      )}
    </>
  );
};

interface Props {
  picks: SessionPick[];
  clockOffsetMs: number;
  lockingId: number | null;
  onLock: (pickId: number) => void;
}

/** The trades this session can take right now, best first. Every row has its own Trade Lock and stays open until its opportunity expires. */
export const SessionOpportunityTable: React.FC<Props> = ({ picks, clockOffsetMs, lockingId, onLock }) => (
  <div className="card sl-table-card">
    <div className="sl-table-scroll">
      <table className="data-table sl-table">
        <thead>
          <tr>
            <th>Trade</th>
            <th>Win chance</th>
            <th>Entry area ₹</th>
            <th>Stop loss ₹</th>
            <th>Target ₹</th>
            <th>Quantity · capital</th>
            <th>Stopped / target</th>
            <th className="sl-col-lock" />
          </tr>
        </thead>
        <tbody>
          {picks.map((p) => (
            <OpportunityRow
              key={p.id}
              pick={p}
              clockOffsetMs={clockOffsetMs}
              locking={lockingId === p.id}
              onLock={onLock}
            />
          ))}
        </tbody>
      </table>
    </div>
  </div>
);
