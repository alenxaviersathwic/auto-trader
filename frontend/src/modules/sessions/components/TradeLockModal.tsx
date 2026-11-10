import React, { useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { AlertTriangle, CheckCircle2, Lock, Play, X } from "lucide-react";
import { SessionPick } from "../types/sessions.types";
import { PriceLadder } from "./PriceLadder";
import { formatRupee } from "../../opportunities/components/formatters";
import { useCreateTrade, usePreviewTradeSizing } from "../../trades/hooks/useTrades";

type Verdict = { tone: "ok" | "warn" | "none"; text: string };

function verdict(entryAt: number, p: SessionPick): Verdict {
  if (entryAt > p.entryMax) {
    return {
      tone: "warn",
      text: `Above entry ceiling (max ${formatRupee(p.entryMax)}). Reward drops below 1.2× risk: caution when chasing.`,
    };
  }
  if (entryAt <= p.entry) return { tone: "ok", text: "At or below the planned entry." };
  return { tone: "ok", text: "Inside the planned entry area." };
}

/**
 * Interactive Lock & Enter Trade Modal:
 * - Pre-fills `entryAt` with the live price at the second of lock (`lockedPrice ?? entry`)
 * - Dynamically suggests `lots` from session free capital & remaining loss budget
 * - Enforces max 3 parallel active trades per session
 * - Starts the dedicated Trader pilot (`POST /api/v1/trades`) and navigates to `/trades/$tradeId`
 */
export const TradeLockModal: React.FC<{ pick: SessionPick; onClose: () => void }> = ({ pick: p, onClose }) => {
  const navigate = useNavigate();
  const defaultEntry = Number((p.lockedPrice ?? p.entry).toFixed(2));
  const [entryAtInput, setEntryAtInput] = useState<string>(String(defaultEntry));
  const [lotsInput, setLotsInput] = useState<number>(p.lots);
  const [userEditedLots, setUserEditedLots] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const numericEntry = Number(entryAtInput);
  const validEntry = Number.isFinite(numericEntry) && numericEntry > 0 ? numericEntry : defaultEntry;

  const { data: sizing } = usePreviewTradeSizing(p.sessionId, p.id, validEntry, true);
  const createTradeMutation = useCreateTrade();

  useEffect(() => {
    if (sizing && !userEditedLots) {
      setLotsInput(sizing.suggestedLots);
    }
  }, [sizing, userEditedLots]);

  const v = verdict(validEntry, p);
  const lotUnits = sizing?.lotUnits ?? p.lotUnits;
  const activeStop = sizing?.stop ?? p.stop;
  const activeTarget = sizing?.target ?? p.target;
  const quantity = Math.max(1, lotsInput) * lotUnits;
  const capitalReq = quantity * validEntry;
  const riskAmt = quantity * Math.max(0, validEntry - activeStop);
  const rewardAmt = quantity * Math.max(0, activeTarget - validEntry);

  const handleStartTrader = () => {
    setErrorMsg(null);
    createTradeMutation.mutate(
      {
        sessionId: p.sessionId,
        pickId: p.id,
        entryAt: validEntry,
        lots: Math.max(1, lotsInput),
      },
      {
        onSuccess: (created) => {
          onClose();
          navigate({ to: "/trades/$tradeId", params: { tradeId: String(created.id) } });
        },
        onError: (err) => {
          setErrorMsg(err instanceof Error ? err.message : "Failed to start Trader");
        },
      }
    );
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal sl-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <div className="sl-modal__head">
          <Lock size={16} />
          <h3 className="modal-title" style={{ margin: 0 }}>
            Enter Trade & Start Trader: {p.underlyingCode} {p.strike} {p.optionType}
          </h3>
          <button type="button" className="btn btn--icon" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </div>

        <div className="sl-modal__body">
          <div className={`sl-modal__price sl-modal__price--${v.tone}`}>
            <span className="label">Live Lock Price</span>
            <span className="sl-modal__value">{formatRupee(p.lockedPrice ?? p.entry)}</span>
            <span className={`micro ${v.tone === "warn" ? "text-amber" : "text-secondary"}`}>
              {v.tone === "warn" ? <AlertTriangle size={12} /> : <CheckCircle2 size={12} />} {v.text}
            </span>
          </div>

          <PriceLadder stop={activeStop} entry={p.entry} entryMax={p.entryMax} target={activeTarget} marker={validEntry} />

          {/* Interactive Entry Price & Risk-Suggested Lots */}
          <div className="form-grid" style={{ marginTop: "var(--space-3)" }}>
            <div className="form-group">
              <label className="form-label" htmlFor="trade-entry-at">
                Entry At (₹) <span className="micro text-muted">(default live price)</span>
              </label>
              <input
                id="trade-entry-at"
                type="number"
                step="0.05"
                className="input mono"
                value={entryAtInput}
                onChange={(e) => setEntryAtInput(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="trade-lots">
                Lots to Take{" "}
                <span className="micro text-green">
                  (Suggested: {sizing?.suggestedLots ?? p.lots} · Max: {sizing?.maxAffordableLots ?? p.lots})
                </span>
              </label>
              <input
                id="trade-lots"
                type="number"
                min={1}
                max={Math.max(1, sizing?.maxAffordableLots ?? 50)}
                className="input mono"
                value={lotsInput}
                onChange={(e) => {
                  setUserEditedLots(true);
                  setLotsInput(Math.max(1, Number(e.target.value) || 1));
                }}
              />
            </div>
          </div>

          <div className="sl-figs" style={{ marginTop: "var(--space-3)" }}>
            <div className="sl-stat">
              <span className="label">Quantity</span>
              <span className="sl-stat__value mono">
                {lotsInput} × {lotUnits} = {quantity}
              </span>
            </div>
            <div className="sl-stat">
              <span className="label">Capital Required</span>
              <span className="sl-stat__value mono">{formatRupee(capitalReq)}</span>
              {sizing && (
                <span className="micro text-muted">Free: {formatRupee(sizing.availableCapital)}</span>
              )}
            </div>
            <div className="sl-stat">
              <span className="label">Risk / Initial Reward</span>
              <span className="sl-stat__value mono">
                <span className="text-red">−{formatRupee(riskAmt)}</span>{" "}
                <span className="text-green">+{formatRupee(rewardAmt)}</span>
              </span>
              {sizing && (
                <span className="micro text-muted">
                  Loss budget left: {formatRupee(sizing.remainingLossBudget)} · Parallel:{" "}
                  {sizing.activeTradesCount}/{sizing.maxParallelTrades}
                </span>
              )}
            </div>
          </div>

          {(errorMsg || sizing?.blockReason) && (
            <div className="form-error" style={{ marginTop: "var(--space-3)" }}>
              {errorMsg || sizing?.blockReason}
            </div>
          )}
        </div>

        <div className="sl-modal__foot">
          <span className="micro text-muted">
            Starts a dedicated 1s Trader loop (`/trades/$tradeId`) with dynamic SL & Target trailing.
          </span>
          <div className="modal-actions" style={{ display: "flex", gap: "var(--space-2)" }}>
            <button type="button" className="btn btn--ghost" onClick={onClose}>
              Later
            </button>
            <button
              type="button"
              className="btn btn--primary"
              onClick={handleStartTrader}
              disabled={createTradeMutation.isPending || (sizing ? !sizing.canEnter : false)}
              autoFocus
            >
              <Play size={14} />
              <span>
                {createTradeMutation.isPending
                  ? "Starting Trader…"
                  : `Start Trader (${lotsInput} lot${lotsInput === 1 ? "" : "s"} @ ₹${validEntry.toFixed(2)})`}
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
