import React from "react";
import {
  AlertTriangle,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Cpu,
  Shield,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { Opportunity } from "../types/opportunities.types";
import { formatDateTime, formatExpiry, formatRupee, formatTime } from "./formatters";

const OUTCOME_BADGE: Record<Opportunity["outcome"], { label: string; cls: string }> = {
  PENDING: { label: "ACTIVE", cls: "badge--green" },
  TARGET_HIT: { label: "TARGET HIT", cls: "badge--blue" },
  STOP_HIT: { label: "STOP HIT", cls: "badge--red" },
  EXPIRED: { label: "EXPIRED", cls: "badge--slate" },
};

const RISK_BADGE: Record<Opportunity["riskLevel"], string> = {
  LOW: "badge--green",
  MEDIUM: "badge--amber",
  HIGH: "badge--red",
};

export const OpportunityCard: React.FC<{ opportunity: Opportunity }> = ({ opportunity: s }) => {
  const [collapsed, setCollapsed] = React.useState(false);
  const outcome =
    s.expired && s.outcome === "PENDING" ? OUTCOME_BADGE.EXPIRED : OUTCOME_BADGE[s.outcome];
  const range = s.target - s.stop || 1;
  const entryPct = Math.min(100, Math.max(0, ((s.entry - s.stop) / range) * 100));
  const stopPct = ((s.stop - s.entry) / s.entry) * 100;
  const targetPct = ((s.target - s.entry) / s.entry) * 100;
  const gain = s.target - s.entry;
  const isCall = s.optionType === "CE";

  return (
    <div className={`sugg-card ${isCall ? "sugg-card--call" : "sugg-card--put"} ${s.expired ? "sugg-card--expired" : ""}`}>
      {/* Card Header */}
      <div className="sugg-head">
        <div className="sugg-head-left">
          <span className="sugg-rank mono">#{s.rank}</span>

          <div className="sugg-contract-pill">
            <span className="sugg-underlying">{s.underlyingCode}</span>
            <span className="sugg-strike mono">
              {s.strike} {s.optionType}
            </span>
            <span className="sugg-spot mono">Spot {formatRupee(s.spot)}</span>
          </div>

          <span className={`badge ${isCall ? "badge--green" : "badge--red"}`}>
            {isCall ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
            {isCall ? "CALL" : "PUT"}
          </span>

          <span className="badge badge--amber">
            <Calendar size={11} /> EXP {formatExpiry(s.expiry)}
          </span>
        </div>

        <div className="sugg-head-right">
          <span className="sugg-score-pill mono">
            <Sparkles size={12} />
            <span>{s.confidence.toFixed(1)}</span>
            <span className="sugg-score-max">/100</span>
          </span>

          <span className={`badge ${outcome.cls}`}>{outcome.label}</span>

          <span className={`badge ${RISK_BADGE[s.riskLevel]}`}>
            <Shield size={11} /> {s.riskLevel}
          </span>

          {s.risks[0]?.startsWith("Against") && (
            <span className="badge badge--amber">AGAINST TREND</span>
          )}

          <button
            type="button"
            className="sugg-toggle-btn"
            onClick={() => setCollapsed((c) => !c)}
            title={collapsed ? "Expand contract details" : "Collapse contract details"}
          >
            {collapsed ? <ChevronDown size={15} /> : <ChevronUp size={15} />}
          </button>
        </div>
      </div>

      {!collapsed && (
        <>
          {/* Execution Price Levels & R:R Bar */}
          <div className="sugg-levels-panel">
            <div className="sugg-levels-grid">
              <div className="sugg-level-box sugg-level-box--stop">
                <div className="sugg-level-label">Stop Loss</div>
                <div className="sugg-level-val sugg-down">{formatRupee(s.stop)}</div>
                <div className="sugg-level-sub sugg-down mono">{stopPct.toFixed(1)}% risk</div>
              </div>

              <div className="sugg-level-box sugg-level-box--entry">
                <div className="sugg-level-label">Entry Premium</div>
                <div className="sugg-level-val sugg-entry">{formatRupee(s.entry)}</div>
                <div className="sugg-level-sub mono">
                  {s.strike} {s.optionType} · INTRADAY
                </div>
              </div>

              <div className="sugg-level-box sugg-level-box--target">
                <div className="sugg-level-label">Profit Target</div>
                <div className="sugg-level-val sugg-up">{formatRupee(s.target)}</div>
                <div className="sugg-level-sub sugg-up mono">
                  +{targetPct.toFixed(1)}% (+{formatRupee(gain)})
                </div>
              </div>
            </div>

            <div className="sugg-bar-wrap">
              <div className="sugg-bar">
                <div className="sugg-bar-risk" style={{ width: `${entryPct}%` }} />
                <div className="sugg-bar-target" style={{ width: `${100 - entryPct}%` }} />
              </div>
              <div
                className="sugg-bar-marker"
                style={{ left: `${entryPct}%` }}
                title={`Entry at ${formatRupee(s.entry)}`}
              />
            </div>

            <div className="sugg-bar-legend">
              <div className="sugg-legend-items">
                <span className="sugg-down">● Risk Zone</span>
                <span className="sugg-entry">● Entry Execution</span>
                <span className="sugg-up">● Target Zone</span>
              </div>
              <div className="sugg-legend-right">
                <span className="sugg-timestamp mono">{formatDateTime(s.createdAt)}</span>
                <span className="badge badge--blue sugg-rr">1 : {s.rewardRisk.toFixed(2)} R:R</span>
              </div>
            </div>
          </div>

          {/* 4-Column Contract Metadata Strip */}
          <div className="sugg-specs-grid">
            <div className="sugg-spec-cell">
              <div className="sugg-spec-label">Potential Gain</div>
              <div className="sugg-spec-value sugg-up mono">
                +{s.profitMarginPct.toFixed(1)}%{" "}
                <span className="sugg-gain-chip">+{formatRupee(gain)}</span>
              </div>
            </div>

            <div className="sugg-spec-cell">
              <div className="sugg-spec-label">
                <Clock size={11} /> Entry Window
              </div>
              <div className="sugg-spec-value mono">
                {s.expired ? (
                  <span className="sugg-down">Window closed</span>
                ) : (
                  `Until ${formatTime(s.validUntil)} IST`
                )}
              </div>
            </div>

            <div className="sugg-spec-cell">
              <div className="sugg-spec-label">Strategy Regime</div>
              <div className="sugg-spec-value">{s.strategy ?? "Momentum Setup"}</div>
            </div>

            <div className="sugg-spec-cell">
              <div className="sugg-spec-label">
                <Cpu size={11} /> {s.source === "AI" ? "AI" : "Baseline"} Snapshot
              </div>
              <div className="sugg-spec-value mono sugg-muted">#{s.ref}</div>
            </div>
          </div>

          {/* Rationale & Risk Factors */}
          {(s.reasons.length > 0 || s.risks.length > 0) && (
            <div className="sugg-rationale">
              {s.reasons.length > 0 && (
                <div className="sugg-reasons-block">
                  <div className="sugg-rationale-title">
                    <CheckCircle2 size={12} className="sugg-up" />
                    <span>Setup Rationale &amp; Drivers</span>
                  </div>
                  <ul className="sugg-reasons-list">
                    {s.reasons.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {s.risks.length > 0 && (
                <div className="sugg-risks-bar">
                  <AlertTriangle size={13} className="sugg-risks-icon" />
                  <div>
                    <span className="sugg-risks-label">Risk Factors: </span>
                    <span>{s.risks.join(" · ")}</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};

