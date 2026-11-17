import React from "react";
import { Brain, CheckCircle2, Lightbulb, XCircle } from "lucide-react";
import { useTradeAutopsy } from "../../autopsy/hooks/useLearning";
import { TAG_LABEL, VERDICT_META } from "../../autopsy/types/learningMeta";
import { formatSignedRupee } from "../../opportunity-finder/components/formatters";

/** Autopsy agent's verdict on a finished trade, and what it changed (scorecard status, proposed rules). */
export const TradeAutopsyCard: React.FC<{ tradeId: number; exited: boolean }> = ({ tradeId, exited }) => {
  const { data: a, isLoading, isError } = useTradeAutopsy(tradeId, exited);

  if (!exited) {
    return (
      <div className="te-desk">
        <div className="te-empty">
          <Brain size={14} /> The autopsy agent analyses this trade as soon as it exits.
        </div>
      </div>
    );
  }
  if (isLoading) return <div className="te-desk"><div className="te-empty">Loading autopsy…</div></div>;
  if (isError || !a) {
    return (
      <div className="te-desk">
        <div className="te-empty">No autopsy for this trade (trades closed before the autopsy agent existed have none).</div>
      </div>
    );
  }
  const meta = VERDICT_META[a.verdict];
  const l = a.learning;

  return (
    <section className="te-desk" aria-label="Trade autopsy">
      <div className="te-panel">
        <div className="te-panel__head">
          <span className="te-panel__title">
            <Brain size={15} className="text-muted" /> Autopsy · {a.setup.replace(/_/g, " ")}
          </span>
          <span className={`te-pill te-pill--${meta.tone}`}>{meta.label}</span>
        </div>
        <div className="te-metrics" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
          <div className="te-stat">
            <div className="te-stat__label">Result</div>
            <div className={`te-tiny-val ${a.rMultiple >= 0 ? "text-green" : "text-red"}`}>
              {a.rMultiple >= 0 ? "+" : ""}
              {a.rMultiple.toFixed(2)}R · {formatSignedRupee(a.netPnl, true)}
            </div>
          </div>
          <div className="te-stat">
            <div className="te-stat__label">Best (MFE)</div>
            <div className="te-tiny-val">{a.mfeR.toFixed(2)}R</div>
          </div>
          <div className="te-stat">
            <div className="te-stat__label">Worst (MAE)</div>
            <div className="te-tiny-val">{a.maeR.toFixed(2)}R</div>
          </div>
          <div className="te-stat">
            <div className="te-stat__label">Gave back</div>
            <div className="te-tiny-val">{a.givebackPct !== null ? `${a.givebackPct.toFixed(0)}%` : "—"}</div>
          </div>
        </div>
        <div className="te-autopsy">
          <div className="te-autopsy__col te-autopsy__col--right">
            <span className="label">What went right</span>
            {a.wentRight.length === 0 ? (
              <span className="micro text-muted">Nothing stood out.</span>
            ) : (
              <ul className="te-points">
                {a.wentRight.map((x) => (
                  <li key={x}>
                    <CheckCircle2 size={13} className="text-green" />
                    <span>{x}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="te-autopsy__col te-autopsy__col--wrong">
            <span className="label">What went wrong</span>
            {a.wentWrong.length === 0 ? (
              <span className="micro text-muted">Nothing went wrong.</span>
            ) : (
              <ul className="te-points">
                {a.wentWrong.map((x) => (
                  <li key={x}>
                    <XCircle size={13} className="text-red" />
                    <span>{x}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
        {a.lessons.length > 0 && (
          <ul className="te-points">
            {a.lessons.map((x) => (
              <li key={x}>
                <Lightbulb size={13} className="text-amber" />
                <span>{x}</span>
              </li>
            ))}
          </ul>
        )}
        <div className="te-notice">
          <span>
            {a.setup.replace(/_/g, " ")} scorecard: {l.closedTrades ?? 0} trades, {formatSignedRupee(l.netPnl ?? 0, true)}, avg{" "}
            {(l.avgR ?? 0) >= 0 ? "+" : ""}
            {(l.avgR ?? 0).toFixed(2)}R ·{" "}
            {l.scorecardBefore !== l.scorecardAfter
              ? `${l.scorecardBefore} → ${l.scorecardAfter}${l.statusReason ? ` (${l.statusReason})` : ""}`
              : `${l.scorecardAfter ?? "ACTIVE"}`}
            {a.tags.length > 0 && ` · tagged: ${a.tags.map((t) => TAG_LABEL[t] ?? t).join(", ")}`}
            {(l.guardsProposed ?? []).length > 0 &&
              ` · proposed rule: ${(l.guardsProposed ?? []).map((g) => g.text).join(" ")}`}
          </span>
        </div>
      </div>
    </section>
  );
};
