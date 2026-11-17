import React, { useEffect, useState } from "react";
import { Pencil, X, Zap } from "lucide-react";
import { RiskLevel, SessionType, TradingSession, TradingSessionUpdatePayload } from "../types/sessions.types";
import { RISK_LEVELS, RISK_META } from "./riskLevels";
import { managersFor, normalizeTraderCodes, TRADER_META } from "../../trade-history/components/traderMeta";
import { TraderCode } from "../../trade-history/types/trades.types";

interface Props {
  session: TradingSession;
  saving: boolean;
  error: string | null;
  onSave: (payload: TradingSessionUpdatePayload) => Promise<void>;
  onClose: () => void;
}

const MODES: { value: SessionType; label: string; desc: string }[] = [
  { value: "MANUAL", label: "Manual", desc: "Review & lock picks manually" },
  { value: "SEMI_AUTO", label: "Semi-Auto", desc: "Auto-lock #1 pick with live graph" },
  { value: "FULL_AUTO", label: "Full-Auto", desc: "Autonomous entry & trailing exit" },
];

export const SessionEditModal: React.FC<Props> = ({ session, saving, error, onSave, onClose }) => {
  const activeTraders = normalizeTraderCodes(session.traders);
  const initialManager: TraderCode = activeTraders[0] ?? "FLOW_MOMENTUM_TRADER";
  const managers = managersFor(session.scope);

  const [managerCode, setManagerCode] = useState<TraderCode>(initialManager);
  const [sessionType, setSessionType] = useState<SessionType>(session.sessionType);
  const [riskLevel, setRiskLevel] = useState<RiskLevel>(session.riskLevel ?? "HIGH");
  const [routeThroughUpstox, setRouteThroughUpstox] = useState<boolean>(session.routeThroughUpstox);
  const [capital, setCapital] = useState<string>(String(session.capital));
  const [maxLossPercentage, setMaxLossPercentage] = useState<string>(String(session.maxLossPercentage));

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const capNum = Number(capital);
    const lossNum = Number(maxLossPercentage);
    const payload: TradingSessionUpdatePayload = {
      traders: [managerCode],
      sessionType,
      riskLevel,
      routeThroughUpstox,
      ...(Number.isFinite(capNum) && capNum > 0 ? { capital: capNum } : {}),
      ...(Number.isFinite(lossNum) && lossNum > 0 ? { maxLossPercentage: lossNum } : {}),
    };
    await onSave(payload);
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Edit session details" onClick={onClose}>
      <form className="modal-card finder-modal" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
        <header className="finder-modal__head">
          <div className="finder-modal__title-wrap">
            <h2 className="finder-modal__title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Pencil size={15} /> Edit Session #{session.id}
            </h2>
            <span className="micro text-muted">
              Update session manager, execution mode, risk level, or capital parameters.
            </span>
          </div>
          <button type="button" className="ss-close" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </header>

        <div className="finder-modal__body">
          {error && <div className="card desk-alert desk-alert--red micro">{error}</div>}

          <section className="finder-modal__section">
            <span className="label">Session Manager</span>
            <div className="sd-edit-grid">
              {managers.map((m) => {
                const selected = managerCode === m.traderCode;
                const t = TRADER_META[m.traderCode];
                return (
                  <button
                    key={m.traderCode}
                    type="button"
                    className={`sd-edit-opt ${selected ? "sd-edit-opt--active" : ""}`}
                    onClick={() => setManagerCode(m.traderCode)}
                  >
                    <div className="sd-edit-opt__head">
                      <strong>{m.name}</strong>
                      <span className={`badge ${t.badgeClass} mono`}>{t.tag}</span>
                    </div>
                    <span className="micro text-secondary">{m.trades}</span>
                  </button>
                );
              })}
            </div>
          </section>

          <div className="finder-modal__cols">
            <section className="finder-modal__section">
              <span className="label">Execution Mode</span>
              <div className="sd-edit-stack">
                {MODES.map((m) => (
                  <button
                    key={m.value}
                    type="button"
                    className={`sd-edit-opt ${sessionType === m.value ? "sd-edit-opt--active" : ""}`}
                    onClick={() => setSessionType(m.value)}
                  >
                    <strong>{m.label}</strong>
                    <span className="micro text-secondary">{m.desc}</span>
                  </button>
                ))}
              </div>
            </section>

            <section className="finder-modal__section">
              <span className="label">Risk Level</span>
              <div className="sd-edit-stack">
                {RISK_LEVELS.map((lv) => (
                  <button
                    key={lv}
                    type="button"
                    className={`sd-edit-opt ${riskLevel === lv ? "sd-edit-opt--active" : ""}`}
                    onClick={() => setRiskLevel(lv)}
                  >
                    <strong>{RISK_META[lv].label}</strong>
                    <span className="micro text-secondary">{RISK_META[lv].takes}</span>
                  </button>
                ))}
              </div>
            </section>
          </div>

          <div className="finder-modal__cols">
            <label className="sd-edit-field">
              <span className="label">Capital (₹)</span>
              <input
                type="number"
                min={1000}
                step={1000}
                className="sd-edit-input mono"
                value={capital}
                onChange={(e) => setCapital(e.target.value)}
              />
            </label>
            <label className="sd-edit-field">
              <span className="label">Max Loss (%)</span>
              <input
                type="number"
                min={0.5}
                max={50}
                step={0.5}
                className="sd-edit-input mono"
                value={maxLossPercentage}
                onChange={(e) => setMaxLossPercentage(e.target.value)}
              />
            </label>
          </div>

          <section className="finder-modal__section">
            <span className="label">Broker Routing</span>
            <button
              type="button"
              className={`sd-edit-opt sd-edit-opt--row ${routeThroughUpstox ? "sd-edit-opt--active" : ""}`}
              onClick={() => setRouteThroughUpstox((v) => !v)}
            >
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Zap size={14} />
                <strong>{routeThroughUpstox ? "Upstox Live (Real Money)" : "Simulated (Paper Trades)"}</strong>
              </span>
              <span className="micro text-secondary">Click to toggle</span>
            </button>
          </section>
        </div>

        <footer className="finder-modal__foot">
          <button type="button" className="te-btn te-btn--ghost te-btn--sm" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="submit" className="te-btn te-btn--primary te-btn--sm" disabled={saving}>
            {saving ? "Saving…" : "Save changes"}
          </button>
        </footer>
      </form>
    </div>
  );
};
