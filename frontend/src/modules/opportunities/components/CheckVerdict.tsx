import React from "react";
import { Activity } from "lucide-react";
import { OpportunityCheckItem } from "../types/opportunities.types";
import { formatRupee, formatTime } from "./formatters";

function pct(value: number, digits = 1): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}%`;
}

/** The answer to "did this signal work?": outcome, how far it got, and the P&L on the candles. */
export const CheckVerdict: React.FC<{ result: OpportunityCheckItem }> = ({ result }) => {
  const stopped = result.outcome === "STOP_HIT";
  const tone = result.targetAchieved ? "pos" : stopped || result.achievedPct < 0 ? "neg" : "";
  const badgeCls = result.targetAchieved ? "badge--green" : stopped || result.achievedPct < 0 ? "badge--red" : "badge--blue";
  const verdict = result.targetAchieved
    ? "TARGET HIT"
    : stopped
    ? "STOP HIT"
    : `${pct(result.achievedPct)} OF TARGET`;

  return (
    <div className="oc-test-panel">
      <div className="oc-test-head">
        <div className="oc-test-title">
          <Activity size={13} />
          <span className="mono font-bold">
            TESTED · {formatTime(result.createdAt)} → {formatTime(result.validUntil)} IST
          </span>
          <span className={`badge mono ${badgeCls}`}>{verdict}</span>
        </div>
        <span className="mono oc-test-note">
          {result.candlesChecked}×1m bars
          {result.hitAt ? ` · at ${formatTime(result.hitAt)}` : result.windowEnded ? " · window ended" : " · still live"}
        </span>
      </div>

      <div className="oc-test-kpis">
        <div className="oc-test-kpi">
          <span className="oc-test-kpi-lbl">Entry</span>
          <span className="oc-test-kpi-val">{formatRupee(result.entry)}</span>
        </div>
        <div className="oc-test-kpi">
          <span className="oc-test-kpi-lbl">Target / Stop</span>
          <span className="oc-test-kpi-val">
            <span className="pos">{formatRupee(result.target)}</span>
            <span className="oc-test-sep"> / </span>
            <span className="neg">{formatRupee(result.stop)}</span>
          </span>
        </div>
        <div className="oc-test-kpi">
          <span className="oc-test-kpi-lbl">Peak / Low</span>
          <span className="oc-test-kpi-val">
            <span className="pos">{formatRupee(result.peakPrice)}</span>
            <span className="oc-test-sep"> / </span>
            <span className="neg">{formatRupee(result.troughPrice)}</span>
          </span>
        </div>
        <div className="oc-test-kpi">
          <span className="oc-test-kpi-lbl">Exit / Mark</span>
          <span className="oc-test-kpi-val">{formatRupee(result.exitPrice)}</span>
        </div>
        <div className="oc-test-kpi">
          <span className="oc-test-kpi-lbl">Option P&amp;L</span>
          <span className={`oc-test-kpi-val ${result.pnlPct >= 0 ? "pos" : "neg"}`}>{pct(result.pnlPct, 2)}</span>
        </div>
        <div className="oc-test-kpi">
          <span className="oc-test-kpi-lbl">Target achieved</span>
          <span className={`oc-test-kpi-val ${tone}`}>
            {result.achievedPct >= 100 ? "100%" : pct(result.achievedPct)}
          </span>
        </div>
      </div>
    </div>
  );
};
