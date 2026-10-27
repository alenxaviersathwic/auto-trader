import React from "react";
import { Calendar, ChevronDown, ChevronUp, Clock, Cpu, Shield, Sparkles, TrendingDown, TrendingUp } from "lucide-react";
import { Suggestion } from "../types/suggestion.types";
import { formatDateTime, formatExpiry, formatRupee, formatTime } from "./formatters";

const OUTCOME_BADGE: Record<Suggestion["outcome"], { label: string; cls: string }> = {
  PENDING: { label: "ACTIVE", cls: "badge--green" },
  TARGET_HIT: { label: "TARGET HIT", cls: "badge--blue" },
  STOP_HIT: { label: "STOP HIT", cls: "badge--red" },
  EXPIRED: { label: "EXPIRED", cls: "badge--slate" },
};

const RISK_BADGE: Record<Suggestion["riskLevel"], string> = {
  LOW: "badge--green",
  MEDIUM: "badge--amber",
  HIGH: "badge--red",
};

export const SuggestionCard: React.FC<{ suggestion: Suggestion }> = ({ suggestion: s }) => {
  const [collapsed, setCollapsed] = React.useState(false);
  const outcome = s.expired && s.outcome === "PENDING" ? OUTCOME_BADGE.EXPIRED : OUTCOME_BADGE[s.outcome];
  const range = s.target - s.stop || 1;
  const entryPct = Math.min(100, Math.max(0, ((s.entry - s.stop) / range) * 100));
  const stopPct = ((s.stop - s.entry) / s.entry) * 100;
  const targetPct = ((s.target - s.entry) / s.entry) * 100;
  const gain = s.target - s.entry;
  const isCall = s.optionType === "CE";

  return (
    <div className="card sugg-card">
      <div className="sugg-head">
        <div className="sugg-chips">
          <span className="sugg-title">
            <span className="ticker">{s.underlyingCode}</span>
            <span className="mono">{formatRupee(s.spot)}</span>
          </span>
          <span className={`badge ${isCall ? "badge--green" : "badge--red"}`}>
            {isCall ? <TrendingUp size={11} /> : <TrendingDown size={11} />} {isCall ? "CALL" : "PUT"}
          </span>
          <span className="badge badge--amber">
            <Calendar size={11} /> EXP {formatExpiry(s.expiry)}
          </span>
          <span className={`badge ${outcome.cls}`}>{outcome.label}</span>
          <span className={`badge ${RISK_BADGE[s.riskLevel]}`}>
            <Shield size={11} /> {s.riskLevel} RISK
          </span>
          <span className="badge badge--slate">INTRADAY</span>
          {s.risks[0]?.startsWith("Against") && <span className="badge badge--amber">AGAINST TREND</span>}
        </div>
        <button type="button" className="btn btn-secondary" onClick={() => setCollapsed((c) => !c)}>
          {collapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />} {collapsed ? "Expand" : "Collapse"}
        </button>
      </div>

      <div className="sugg-score">
        <Sparkles size={13} /> SETUP SCORE: <strong>{s.confidence.toFixed(1)}/100</strong>
        <span className="micro sugg-muted">· {formatDateTime(s.createdAt)}</span>
      </div>

      {!collapsed && (
        <>
          <div className="sugg-panel">
            <div className="sugg-levels">
              <div>
                <div className="section-title">Stop loss</div>
                <div className="sugg-value sugg-down">{formatRupee(s.stop)}</div>
                <div className="micro sugg-down">({stopPct.toFixed(1)}%)</div>
              </div>
              <div className="sugg-center">
                <div className="section-title">Entry price</div>
                <div className="sugg-value sugg-entry">{formatRupee(s.entry)}</div>
              </div>
              <div className="sugg-right">
                <div className="section-title">Profit target</div>
                <div className="sugg-value sugg-up">{formatRupee(s.target)}</div>
                <div className="micro sugg-up">(+{targetPct.toFixed(1)}%)</div>
              </div>
            </div>
            <div className="sugg-bar">
              <div className="sugg-bar-risk" style={{ width: `${entryPct}%` }} />
              <div className="sugg-bar-target" style={{ width: `${100 - entryPct}%` }} />
            </div>
            <div className="sugg-bar-legend micro">
              <span className="sugg-down">● Risk Zone</span>
              <span className="sugg-entry">● Execution</span>
              <span className="sugg-up">● Target Zone</span>
              <span className="badge badge--blue sugg-rr">1 : {s.rewardRisk.toFixed(2)} R:R</span>
            </div>
          </div>

          <div className="sugg-grid-2">
            <div className="sugg-panel">
              <div className="section-title">Option premium · exp {formatExpiry(s.expiry)}</div>
              <div className="sugg-value">{formatRupee(s.entry)}</div>
              <div className="micro sugg-muted">
                {s.strike} {s.optionType}
              </div>
            </div>
            <div className="sugg-panel">
              <div className="section-title">Potential gain</div>
              <div className="sugg-value sugg-up">
                +{s.profitMarginPct.toFixed(1)}% <span className="badge badge--green">+{formatRupee(gain)}</span>
              </div>
            </div>
            <div className="sugg-panel">
              <div className="section-title">Stop loss protection</div>
              <div className="sugg-value sugg-down">
                {formatRupee(s.stop)} ({stopPct.toFixed(1)}%)
              </div>
            </div>
            <div className="sugg-panel">
              <div className="section-title">
                <Cpu size={12} /> {s.source === "AI" ? "AI" : "Code"} decision snapshot
              </div>
              <div className="mono sugg-muted">#{s.ref}</div>
            </div>
          </div>

          <div className="sugg-grid-3">
            <div className="sugg-panel">
              <div className="section-title">
                <Clock size={12} /> Entry window
              </div>
              <div className="sugg-text">
                {s.expired ? "Window closed" : `Immediate · until ${formatTime(s.validUntil)} IST`}
              </div>
            </div>
            <div className="sugg-panel">
              <div className="section-title">Expected exit window</div>
              <div className="sugg-text">Target / SL / {formatTime(s.validUntil)} IST</div>
            </div>
            <div className="sugg-panel">
              <div className="section-title">Strategy</div>
              <div className="sugg-text">{s.strategy ?? "—"}</div>
            </div>
          </div>

          {s.reasons.length > 0 && (
            <div className="sugg-panel">
              <div className="section-title">Why</div>
              <ul className="sugg-list label">
                {s.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
              {s.risks.length > 0 && <div className="micro sugg-muted">Risks: {s.risks.join(" · ")}</div>}
            </div>
          )}
        </>
      )}
    </div>
  );
};
