import React, { useEffect } from "react";
import { ListChecks, ScanSearch, Settings2, Workflow, X } from "lucide-react";
import { TRADER_META } from "../../trade-history/components/traderMeta";
import { TraderCode } from "../../trade-history/types/trades.types";
import { OpportunityFinder } from "../types/opportunityFinder.types";
import { SetupScorecard } from "../../autopsy/types/learning.types";
import { formatSignedRupee } from "../../opportunity-finder/components/formatters";

interface Props {
  code: TraderCode;
  finder?: OpportunityFinder;
  scorecards: SetupScorecard[];
  onClose: () => void;
  onOpenToday: () => void;
  children?: React.ReactNode;
}

/** Popup explaining how a specific opportunity finder works: its unique pipeline, entry checks, trade management,
 *  and recent setup performance. */
export const FinderHowItWorksModal: React.FC<Props> = ({
  code,
  finder,
  scorecards,
  onClose,
  onOpenToday,
  children,
}) => {
  const meta = TRADER_META[code];

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label={`${meta.name} — How it works`} onClick={onClose}>
      <div className="modal-card finder-modal" onClick={(e) => e.stopPropagation()}>
        <header className="finder-modal__head">
          <div className="finder-modal__title-wrap">
            <span className={`badge ${meta.badgeClass} mono`}>{meta.tag}</span>
            <h2 className="finder-modal__title">{meta.name}</h2>
            <p className="micro text-secondary" style={{ margin: 0 }}>
              {meta.tagline}
            </p>
          </div>
          <button type="button" className="ss-close" onClick={onClose} aria-label="Close popup">
            <X size={16} />
          </button>
        </header>

        <div className="finder-modal__body">
          {finder?.drivers && (
            <div className="finder-modal__drivers micro text-secondary">
              <strong>Active markets & drivers:</strong> {finder.drivers}
            </div>
          )}

          <section className="finder-modal__section">
            <span className="label">
              <Workflow size={12} /> How this finder works
            </span>
            <div className="finder-flow">
              {meta.workflow.map((step) => (
                <div key={step.title} className="finder-flow__step">
                  <div className="finder-flow__title">{step.title}</div>
                  <div className="micro text-secondary">{step.detail}</div>
                </div>
              ))}
            </div>
          </section>

          <div className="finder-modal__cols">
            <section className="finder-modal__section">
              <span className="label">
                <ListChecks size={12} /> Checks before it enters
              </span>
              <ol className="tr-list">
                {meta.checks.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ol>
            </section>

            <section className="finder-modal__section">
              <span className="label">
                <Settings2 size={12} /> How it manages the trade
              </span>
              <p className="micro text-secondary tr-text">{meta.manages}</p>
            </section>
          </div>

          {children && <div className="finder-modal__extra">{children}</div>}

          <section className="finder-modal__section">
            <span className="label">Its setups (last 14 days)</span>
            {scorecards.length === 0 ? (
              <span className="micro text-muted">No closed trades on its setups yet.</span>
            ) : (
              scorecards.map((c) => (
                <div key={c.setup} className="te-row">
                  <span className="te-row__main">
                    <span className="te-row__title">
                      {c.setup.replace(/_/g, " ")}
                      <span className={`te-pill ${c.scoreStatus === "PAUSED" ? "te-pill--red" : "te-pill--green"}`}>
                        {c.scoreStatus}
                      </span>
                    </span>
                    <span className="te-row__sub">
                      {c.closedTrades} trades · {c.wins}W/{c.losses}L · avg {c.avgR >= 0 ? "+" : ""}
                      {c.avgR.toFixed(2)}R{c.statusReason ? ` · ${c.statusReason}` : ""}
                    </span>
                  </span>
                  <span className={`mono micro tr-amt ${c.netPnl >= 0 ? "text-green" : "text-red"}`}>
                    {formatSignedRupee(c.netPnl, true)}
                  </span>
                </div>
              ))
            )}
          </section>
        </div>

        <footer className="finder-modal__foot">
          <button
            type="button"
            className="te-btn te-btn--ghost te-btn--sm"
            onClick={() => {
              onClose();
              onOpenToday();
            }}
          >
            <ScanSearch size={13} /> View today&apos;s live scans
          </button>
          <button type="button" className="te-btn te-btn--primary te-btn--sm" onClick={onClose}>
            Done
          </button>
        </footer>
      </div>
    </div>
  );
};
