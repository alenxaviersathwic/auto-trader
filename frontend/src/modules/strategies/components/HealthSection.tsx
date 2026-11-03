import React, { useState } from "react";
import { useOverrideStrategyHealth, useStrategyHealth } from "../hooks/useStrategies";

interface HealthSectionProps {
  strategyId: number;
}

export const HealthSection: React.FC<HealthSectionProps> = ({ strategyId }) => {
  const { data: healthData, isLoading } = useStrategyHealth(strategyId);
  const overrideMutation = useOverrideStrategyHealth();

  const [overrideHealth, setOverrideHealth] = useState<string>("HEALTHY");
  const [overrideReason, setOverrideReason] = useState<string>("");
  const [overrideUntil, setOverrideUntil] = useState<string>("");

  const handleOverrideSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!overrideReason.trim()) return;

    overrideMutation.mutate({
      strategyId,
      payload: {
        health: overrideHealth,
        reason: overrideReason.trim(),
        until: overrideUntil ? new Date(overrideUntil).toISOString() : undefined,
      },
    });
  };

  if (isLoading) {
    return (
      <div className="sd-card">
        <div className="sd-empty-inline">Loading strategy health telemetry…</div>
      </div>
    );
  }

  const effective = healthData?.effectiveHealth || "UNKNOWN";
  const policy = healthData?.policyUsed;
  const events = healthData?.recentEvents || [];

  return (
    <div className="sd-panel">
      <div className="sd-overview-cols">
        {/* Effective Health Card */}
        <div className="sd-card">
          <div className="sd-card-header">
            <span className="sd-card-title">Effective Health &amp; Policy Thresholds</span>
            <span
              className={`sd-tag ${
                effective === "HEALTHY"
                  ? "sd-tag--green"
                  : effective === "DEGRADED"
                  ? "sd-tag--amber"
                  : effective === "SUSPENDED"
                  ? "sd-tag--red"
                  : ""
              }`}
            >
              {effective}
            </span>
          </div>

          <div className="sd-spec-list">
            <div className="sd-spec-row">
              <span className="sd-spec-key">Active Policy</span>
              <span className="sd-spec-val mono">{policy?.name || policy?.code || "Default"}</span>
            </div>
            <div className="sd-spec-row">
              <span className="sd-spec-key">Min Trade Sample</span>
              <span className="sd-spec-val mono">{policy?.params?.minTrades ?? 30} Trades</span>
            </div>
            <div className="sd-spec-row">
              <span className="sd-spec-key">Degrade Threshold</span>
              <span className="sd-spec-val mono text-amber">
                Profit Factor &lt; {policy?.params?.degradeIfProfitFactorBelow ?? 1.0}
              </span>
            </div>
            <div className="sd-spec-row">
              <span className="sd-spec-key">Suspend Threshold</span>
              <span className="sd-spec-val mono text-red">
                Profit Factor &lt; {policy?.params?.suspendIfProfitFactorBelow ?? 0.8}
              </span>
            </div>
            <div className="sd-spec-row">
              <span className="sd-spec-key">Max Consecutive Losses</span>
              <span className="sd-spec-val mono text-red">
                {policy?.params?.suspendAfterConsecutiveLosses ?? 5} Losses
              </span>
            </div>
            {healthData?.healthOverride && (
              <div className="sd-spec-row">
                <span className="sd-spec-key">Manual Override</span>
                <span className="sd-spec-val mono text-amber">
                  {healthData.healthOverride} ({healthData.healthOverrideReason || "Manual"})
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Manual Override Form */}
        <div className="sd-card">
          <div className="sd-card-header">
            <span className="sd-card-title">Manual Health Override</span>
            <span className="sd-tag mono">ADMIN</span>
          </div>

          <form onSubmit={handleOverrideSubmit} className="sd-panel" style={{ gap: 10 }}>
            <div className="form-group">
              <label className="form-label">Target Health State</label>
              <select
                className="select"
                value={overrideHealth}
                onChange={(e) => setOverrideHealth(e.target.value)}
              >
                <option value="HEALTHY">HEALTHY</option>
                <option value="DEGRADED">DEGRADED</option>
                <option value="SUSPENDED">SUSPENDED</option>
                <option value="UNKNOWN">UNKNOWN</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Justification (Required)</label>
              <input
                type="text"
                className="input"
                placeholder="Reason for manual health override…"
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Active Until (Optional)</label>
              <input
                type="datetime-local"
                className="input mono"
                value={overrideUntil}
                onChange={(e) => setOverrideUntil(e.target.value)}
              />
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 4 }}>
              <button
                type="submit"
                className="sd-ctrl-btn sd-ctrl-btn--primary"
                disabled={overrideMutation.isPending || !overrideReason.trim()}
              >
                {overrideMutation.isPending ? "Applying…" : "Apply Health Override"}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Health Event Log */}
      <div className="sd-card">
        <div className="sd-card-header">
          <span className="sd-card-title">Health Transition Log ({events.length})</span>
        </div>
        {events.length === 0 ? (
          <div className="sd-empty-inline">
            No historical health state transitions recorded.
          </div>
        ) : (
          <div className="table-scroll-container">
            <table className="data-table sd-compact-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Transition</th>
                  <th>Triggered By</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {events.map((ev) => (
                  <tr key={ev.id}>
                    <td className="mono text-muted">
                      {ev.createdAt ? new Date(ev.createdAt).toLocaleString("en-IN") : "—"}
                    </td>
                    <td className="mono">
                      <span className="text-muted">{ev.fromHealth}</span>
                      {" → "}
                      <span
                        className={
                          ev.toHealth === "HEALTHY"
                            ? "text-green"
                            : ev.toHealth === "DEGRADED"
                            ? "text-amber"
                            : "text-red"
                        }
                      >
                        {ev.toHealth}
                      </span>
                    </td>
                    <td>
                      <span className="sd-tag mono">{ev.triggeredBy}</span>
                    </td>
                    <td>{ev.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
