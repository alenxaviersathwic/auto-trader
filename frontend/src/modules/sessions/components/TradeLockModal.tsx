import React from "react";
import { AlertTriangle, CheckCircle2, Lock, X } from "lucide-react";
import { SessionPick } from "../types/sessions.types";
import { PriceLadder } from "./PriceLadder";
import { formatRupee } from "../../opportunities/components/formatters";

const hms = (iso: string | null): string =>
  iso ? new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false }) : "";

type Verdict = { tone: "ok" | "warn" | "none"; text: string };

function verdict(p: SessionPick): Verdict {
  if (p.lockedPrice == null) return { tone: "none", text: "Live price unavailable. Check it in your terminal before you buy." };
  if (p.lockedPrice > p.entryMax)
    return { tone: "warn", text: `Above the entry area (max ${formatRupee(p.entryMax)}). Reward no longer pays 1.2× the risk: do not chase.` };
  if (p.lockedPrice <= p.entry) return { tone: "ok", text: "At or below the planned entry." };
  return { tone: "ok", text: "Inside the entry area." };
}

/** Shown right after Trade Lock: the item's current price on the same scale as stop, entry area and target. */
export const TradeLockModal: React.FC<{ pick: SessionPick; onClose: () => void }> = ({ pick: p, onClose }) => {
  const v = verdict(p);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal sl-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <div className="sl-modal__head">
          <Lock size={16} />
          <h3 className="modal-title" style={{ margin: 0 }}>
            Trade locked: {p.underlyingCode} {p.strike} {p.optionType}
          </h3>
          <button type="button" className="btn btn--icon" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </div>

        <div className="sl-modal__body">
          <div className={`sl-modal__price sl-modal__price--${v.tone}`}>
            <span className="label">Current price</span>
            <span className="sl-modal__value">{p.lockedPrice != null ? formatRupee(p.lockedPrice) : "—"}</span>
            <span className={`micro ${v.tone === "warn" ? "text-amber" : "text-secondary"}`}>
              {v.tone === "warn" ? <AlertTriangle size={12} /> : v.tone === "ok" ? <CheckCircle2 size={12} /> : null} {v.text}
            </span>
          </div>

          <PriceLadder stop={p.stop} entry={p.entry} entryMax={p.entryMax} target={p.target} marker={p.lockedPrice} />

          <div className="sl-figs">
            <div className="sl-stat">
              <span className="label">Quantity</span>
              <span className="sl-stat__value">
                {p.lots} × {p.lotUnits} = {p.quantity}
              </span>
            </div>
            <div className="sl-stat">
              <span className="label">Capital used</span>
              <span className="sl-stat__value">{formatRupee(p.capitalRequired)}</span>
            </div>
            <div className="sl-stat">
              <span className="label">Locked at</span>
              <span className="sl-stat__value">{hms(p.lockedAt)}</span>
            </div>
          </div>
        </div>

        <div className="sl-modal__foot">
          <span className="micro text-muted">Order handling after the lock is defined next.</span>
          <div className="modal-actions">
            <button type="button" className="btn btn--primary" onClick={onClose} autoFocus>
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
