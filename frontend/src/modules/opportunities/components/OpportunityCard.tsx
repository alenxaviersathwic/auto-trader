import React from "react";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Loader2,
  Shield,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { Opportunity, OpportunityCheckItem } from "../types/opportunities.types";
import { OpportunityCheckChart } from "./OpportunityCheckChart";
import {
  formatCompactRupee,
  formatDateTime,
  formatExpiry,
  formatRupee,
  formatTime,
  getMoneyness,
} from "./formatters";
import { LOT_SIZES } from "./underlyingNames";

const OUTCOME_CONFIG: Record<
  Opportunity["outcome"],
  { label: string; cls: string; dot: string }
> = {
  PENDING: { label: "LIVE", cls: "oc-badge--active", dot: "var(--bullish-green)" },
  TARGET_HIT: { label: "TARGET HIT", cls: "oc-badge--target", dot: "var(--kite-blue)" },
  STOP_HIT: { label: "STOP HIT", cls: "oc-badge--stop", dot: "var(--bearish-red)" },
  EXPIRED: { label: "CLOSED", cls: "oc-badge--expired", dot: "var(--text-muted)" },
};

const RISK_CONFIG: Record<Opportunity["riskLevel"], { label: string; cls: string }> = {
  LOW: { label: "LOW RISK", cls: "oc-risk--low" },
  MEDIUM: { label: "MED RISK", cls: "oc-risk--med" },
  HIGH: { label: "HIGH RISK", cls: "oc-risk--high" },
};

export const OpportunityCard: React.FC<{
  opportunity: Opportunity;
  checkResult?: OpportunityCheckItem;
  isChecking?: boolean;
  onCheck?: (opportunityId: number) => void;
  defaultExpanded?: boolean;
}> = ({ opportunity: s, checkResult, isChecking = false, onCheck, defaultExpanded = true }) => {
  const [collapsed, setCollapsed] = React.useState(!defaultExpanded);

  const isCall = s.optionType === "CE";
  const outcomeKey = s.expired && s.outcome === "PENDING" ? "EXPIRED" : s.outcome;
  const outcome = OUTCOME_CONFIG[outcomeKey];
  const risk = RISK_CONFIG[s.riskLevel] ?? RISK_CONFIG.MEDIUM;

  const lotSize = LOT_SIZES[s.underlyingCode] ?? 25;
  const entryCapital = s.entry * lotSize;
  const maxRiskPoints = Math.max(0, s.entry - s.stop);
  const maxRiskPerLot = maxRiskPoints * lotSize;
  const targetGainPoints = Math.max(0, s.target - s.entry);
  const targetGainPerLot = targetGainPoints * lotSize;

  const stopPct = s.entry > 0 ? ((s.stop - s.entry) / s.entry) * 100 : 0;
  const targetPct = s.entry > 0 ? ((s.target - s.entry) / s.entry) * 100 : 0;

  const moneyness = getMoneyness(s.spot, s.strike, s.optionType);

  return (
    <div
      className={`oc-card ${isCall ? "oc-card--call" : "oc-card--put"} ${
        s.expired ? "oc-card--expired" : ""
      }`}
    >
      {/* ── 1. Compact Header Bar ── */}
      <div className="oc-head">
        <div className="oc-head-left">
          <div className="oc-rank-badge" title={`Ranked #${s.rank}`}>
            #{s.rank}
          </div>

          <div className={`oc-action-badge ${isCall ? "is-call" : "is-put"}`}>
            {isCall ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
            <span>BUY {isCall ? "CE" : "PE"}</span>
          </div>

          <div className="oc-contract-block">
            <span className="oc-strike-val mono">
              {s.underlyingCode} {s.strike.toLocaleString("en-IN")} {s.optionType}
            </span>
            <span
              className={`oc-moneyness-tag ${
                moneyness.label === "ATM"
                  ? "is-atm"
                  : moneyness.label === "ITM"
                  ? "is-itm"
                  : "is-otm"
              }`}
            >
              {moneyness.diffFormatted}
            </span>
          </div>

          <div className="oc-expiry-tag mono">
            <Calendar size={11} />
            <span>{formatExpiry(s.expiry)}</span>
          </div>

          {s.spot > 0 && (
            <div className="oc-spot-ref mono">
              <span>Spot</span>
              <span className="oc-spot-val">{formatRupee(s.spot)}</span>
            </div>
          )}
        </div>

        <div className="oc-head-right">
          {/* Edge Score */}
          <div className="oc-edge-chip mono" title="Confidence Score">
            <Sparkles size={11} />
            <span className="oc-edge-val">{s.confidence.toFixed(0)}%</span>
          </div>

          {/* Risk Level */}
          <div className={`oc-risk-pill ${risk.cls}`}>
            <Shield size={11} />
            <span>{risk.label}</span>
          </div>

          {/* Outcome Status */}
          <div className={`oc-status-pill ${outcome.cls}`}>
            <span className="oc-status-dot" style={{ background: outcome.dot }} />
            <span>{outcome.label}</span>
          </div>

          {/* Tested Achieved % Pill (if checked) */}
          {checkResult && (
            <span
              className={`badge mono ${
                checkResult.achievedPct >= 100
                  ? "badge--green"
                  : checkResult.achievedPct >= 0
                  ? "badge--blue"
                  : "badge--red"
              }`}
              title={`Checked over ${formatTime(checkResult.createdAt)} → ${formatTime(checkResult.validUntil)} IST`}
            >
              {checkResult.achievedPct >= 100
                ? "100% HIT"
                : checkResult.achievedPct > 0
                ? `+${checkResult.achievedPct.toFixed(1)}%`
                : `${checkResult.achievedPct.toFixed(1)}%`}
            </span>
          )}

          {/* Dedicated Terminal Action Button: Check Outcome */}
          {onCheck && (
            <button
              type="button"
              className={`oc-check-btn ${checkResult ? "oc-check-btn--done" : ""}`}
              onClick={() => {
                setCollapsed(false);
                onCheck(s.id);
              }}
              disabled={isChecking}
              title="Verify actual option price path from entry time to validUntil window"
            >
              {isChecking ? (
                <Loader2 size={11} className="sp-spin" />
              ) : (
                <Activity size={11} />
              )}
              <span>{checkResult ? "Re-check" : "Check Result"}</span>
            </button>
          )}

          {/* Expand/Collapse Toggle */}
          <button
            type="button"
            className="oc-collapse-btn"
            onClick={() => setCollapsed((c) => !c)}
            title={collapsed ? "Expand details" : "Collapse details"}
            aria-label={collapsed ? "Expand details" : "Collapse details"}
          >
            {collapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
          </button>
        </div>
      </div>

      {!collapsed && (
        <div className="oc-body">
          {/* ── 2. Compact 4-Cell Trade Plan Strip (Entry / Target / Stop / R:R & Lot) ── */}
          <div className="oc-compact-strip">
            <div className="oc-compact-cell oc-compact-cell--entry">
              <div className="oc-compact-top">
                <span>ENTRY PREMIUM</span>
                <span className="mono entry">1 Lot = {lotSize}</span>
              </div>
              <div className="oc-compact-val entry">{formatRupee(s.entry)}</div>
              <div className="oc-compact-sub">Cap: {formatCompactRupee(entryCapital)} / lot</div>
            </div>

            <div className="oc-compact-cell oc-compact-cell--target">
              <div className="oc-compact-top">
                <span>TARGET</span>
                <span className="mono pos">
                  <ArrowUpRight size={11} />+{targetPct.toFixed(1)}%
                </span>
              </div>
              <div className="oc-compact-val pos">{formatRupee(s.target)}</div>
              <div className="oc-compact-sub">Gain: +{formatCompactRupee(targetGainPerLot)} / lot</div>
            </div>

            <div className="oc-compact-cell oc-compact-cell--stop">
              <div className="oc-compact-top">
                <span>STOP LOSS</span>
                <span className="mono neg">
                  <ArrowDownRight size={11} />
                  {stopPct.toFixed(1)}%
                </span>
              </div>
              <div className="oc-compact-val neg">{formatRupee(s.stop)}</div>
              <div className="oc-compact-sub">Risk: -{formatCompactRupee(maxRiskPerLot)} / lot</div>
            </div>

            <div className="oc-compact-cell oc-compact-cell--rr">
              <div className="oc-compact-top">
                <span>REWARD : RISK</span>
                <span className="mono" style={{ color: "var(--cyan)" }}>
                  {s.source}
                </span>
              </div>
              <div className="oc-compact-val">1 : {s.rewardRisk.toFixed(2)}</div>
              <div className="oc-compact-sub">
                {s.expired ? "Window Closed" : `Valid → ${formatTime(s.validUntil)}`}
              </div>
            </div>
          </div>

          {/* ── 3. Tested Result Graph + Sub-Table (Shown when Check Result is clicked) ── */}
          {checkResult && (
            <div className="oc-test-panel">
              <div className="oc-test-head">
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Activity size={13} style={{ color: "var(--cyan)" }} />
                  <span className="mono font-bold" style={{ color: "var(--text-heading)" }}>
                    TESTED RESULT · {formatTime(checkResult.createdAt)} → {formatTime(checkResult.validUntil)} IST
                  </span>
                  <span
                    className={`badge mono ${
                      checkResult.targetAchieved
                        ? "badge--green"
                        : checkResult.outcome === "STOP_HIT" || checkResult.achievedPct < 0
                        ? "badge--red"
                        : "badge--blue"
                    }`}
                  >
                    {checkResult.targetAchieved
                      ? "TARGET ACHIEVED (100%)"
                      : checkResult.outcome === "STOP_HIT"
                      ? `STOP HIT (${checkResult.achievedPct.toFixed(1)}%)`
                      : `${checkResult.achievedPct > 0 ? "+" : ""}${checkResult.achievedPct.toFixed(1)}% OF TARGET`}
                  </span>
                </div>
                <span className="mono" style={{ color: "var(--text-muted)" }}>
                  {checkResult.candlesChecked}×1m bars
                  {checkResult.hitAt
                    ? ` · Hit at ${formatTime(checkResult.hitAt)}`
                    : checkResult.windowEnded
                    ? " · Window Ended"
                    : " · Live In-Market"}
                </span>
              </div>

              {/* Graph View with Entry / Target / Stop / Actual Trajectory */}
              <OpportunityCheckChart checkResult={checkResult} />

              {/* Compact 6-Column Tested Sub-Table Strip */}
              <div className="oc-test-kpis">
                <div className="oc-test-kpi">
                  <span className="oc-test-kpi-lbl">Entry Mark</span>
                  <span className="oc-test-kpi-val">{formatRupee(checkResult.entry)}</span>
                </div>
                <div className="oc-test-kpi">
                  <span className="oc-test-kpi-lbl">Target / Stop</span>
                  <span className="oc-test-kpi-val">
                    <span className="pos">{formatRupee(checkResult.target)}</span>
                    <span style={{ color: "var(--text-muted)" }}> / </span>
                    <span className="neg">{formatRupee(checkResult.stop)}</span>
                  </span>
                </div>
                <div className="oc-test-kpi">
                  <span className="oc-test-kpi-lbl">Peak / Low</span>
                  <span className="oc-test-kpi-val">
                    <span className="pos">{formatRupee(checkResult.peakPrice)}</span>
                    <span style={{ color: "var(--text-muted)" }}> / </span>
                    <span className="neg">{formatRupee(checkResult.troughPrice)}</span>
                  </span>
                </div>
                <div className="oc-test-kpi">
                  <span className="oc-test-kpi-lbl">Actual Exit / Mark</span>
                  <span className="oc-test-kpi-val">{formatRupee(checkResult.exitPrice)}</span>
                </div>
                <div className="oc-test-kpi">
                  <span className="oc-test-kpi-lbl">Option P&amp;L %</span>
                  <span
                    className={`oc-test-kpi-val ${
                      checkResult.pnlPct >= 0 ? "pos" : "neg"
                    }`}
                  >
                    {checkResult.pnlPct > 0 ? `+${checkResult.pnlPct.toFixed(2)}%` : `${checkResult.pnlPct.toFixed(2)}%`}
                  </span>
                </div>
                <div className="oc-test-kpi">
                  <span className="oc-test-kpi-lbl">Target Achieved %</span>
                  <span
                    className={`oc-test-kpi-val ${
                      checkResult.achievedPct >= 100
                        ? "pos"
                        : checkResult.achievedPct < 0
                        ? "neg"
                        : ""
                    }`}
                  >
                    {checkResult.achievedPct >= 100
                      ? "100%"
                      : checkResult.achievedPct > 0
                      ? `+${checkResult.achievedPct.toFixed(1)}%`
                      : `${checkResult.achievedPct.toFixed(1)}%`}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* ── 4. Compact Single-Line Meta + Rationale & Watchouts ── */}
          <div className="oc-meta-inline">
            <div className="oc-meta-inline-group">
              <span className="oc-meta-kv">
                <span className="oc-meta-k">Setup:</span>
                <strong className="mono" style={{ color: "var(--text-heading)" }}>
                  {s.strategy || "Intraday Momentum"}
                </strong>
              </span>
              <span className="oc-meta-kv mono">
                <Clock size={11} />
                <span>
                  {formatDateTime(s.createdAt)} → {formatTime(s.validUntil)} IST
                </span>
              </span>
            </div>
            <span className="mono" style={{ color: "var(--text-muted)", fontSize: "0.66rem" }}>
              Ref #{s.ref.slice(-11)}
            </span>
          </div>

          {(s.reasons.length > 0 || s.risks.length > 0) && (
            <div className="oc-insights-row">
              {s.reasons.length > 0 && (
                <div className="oc-reasons-card">
                  <div className="oc-insights-title pos">
                    <CheckCircle2 size={11} />
                    <span>Why This Setup</span>
                  </div>
                  <ul className="oc-reasons-list">
                    {s.reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {s.risks.length > 0 && (
                <div className="oc-risks-card">
                  <div className="oc-insights-title warn">
                    <AlertTriangle size={11} />
                    <span>Watchouts</span>
                  </div>
                  <ul className="oc-risks-list">
                    {s.risks.map((rk, i) => (
                      <li key={i}>{rk}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
