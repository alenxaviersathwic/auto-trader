import React, { useState } from "react";
import { Activity, AlertTriangle, Clock, Settings } from "lucide-react";
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
    return <div className="p-4 text-center text-muted">Loading health state...</div>;
  }

  const effective = healthData?.effectiveHealth || "UNKNOWN";
  const policy = healthData?.policyUsed;
  const events = healthData?.recentEvents || [];

  return (
    <div className="health-section">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {/* Effective Health Card */}
        <div className="card-surface p-4 border border-subtle rounded">
          <div className="flex items-center gap-2 mb-3">
            <Activity size={18} className="text-cyan" />
            <h4 className="font-semibold text-primary">Effective Health Status</h4>
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`badge-pill text-sm px-3 py-1 font-bold ${
                effective === "HEALTHY"
                  ? "bg-emerald text-white"
                  : effective === "DEGRADED"
                  ? "bg-amber text-black"
                  : effective === "SUSPENDED"
                  ? "bg-rose text-white"
                  : "bg-surface text-muted"
              }`}
            >
              {effective}
            </span>
            {healthData?.healthOverride && (
              <span className="text-xs text-amber flex items-center gap-1">
                <AlertTriangle size={12} />
                Manually Overridden (Until: {healthData.healthOverrideUntil || "Indefinite"})
              </span>
            )}
          </div>
          {healthData?.healthOverrideReason && (
            <p className="text-xs text-muted mt-2 italic">
              Override reason: "{healthData.healthOverrideReason}"
            </p>
          )}

          {policy && (
            <div className="mt-4 pt-3 border-t border-subtle">
              <span className="text-xs text-muted block mb-1">
                Evaluating Policy: <strong>{policy.name || policy.code}</strong>
              </span>
              <div className="text-xs text-secondary grid grid-cols-2 gap-2 mt-2 font-mono">
                <div>Min Trades: {policy.params?.minTrades ?? 30}</div>
                <div>PF Suspend &lt; {policy.params?.suspendIfProfitFactorBelow ?? 0.8}</div>
                <div>PF Degrade &lt; {policy.params?.degradeIfProfitFactorBelow ?? 1.0}</div>
                <div>Max Loss Streak: {policy.params?.suspendAfterConsecutiveLosses ?? 5}</div>
              </div>
            </div>
          )}
        </div>

        {/* Manual Override Form */}
        <div className="card-surface p-4 border border-subtle rounded">
          <div className="flex items-center gap-2 mb-3">
            <Settings size={18} className="text-amber" />
            <h4 className="font-semibold text-primary">Apply Manual Health Override</h4>
          </div>
          <form onSubmit={handleOverrideSubmit} className="space-y-3">
            <div>
              <label className="text-xs text-muted block mb-1">Target Health</label>
              <select
                className="select w-full"
                value={overrideHealth}
                onChange={(e) => setOverrideHealth(e.target.value)}
              >
                <option value="HEALTHY">HEALTHY</option>
                <option value="DEGRADED">DEGRADED</option>
                <option value="SUSPENDED">SUSPENDED</option>
                <option value="UNKNOWN">UNKNOWN</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-muted block mb-1">Override Reason (Mandatory)</label>
              <input
                type="text"
                className="input w-full text-xs"
                placeholder="e.g. Market regime shift, under manual live review"
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="text-xs text-muted block mb-1">Active Until (Optional)</label>
              <input
                type="datetime-local"
                className="input w-full text-xs"
                value={overrideUntil}
                onChange={(e) => setOverrideUntil(e.target.value)}
              />
            </div>
            <button
              type="submit"
              className="btn-kite-primary text-xs w-full mt-2"
              disabled={overrideMutation.isPending || !overrideReason.trim()}
            >
              {overrideMutation.isPending ? "Applying Override..." : "Save Health Override"}
            </button>
          </form>
        </div>
      </div>

      {/* Health Event Log */}
      <div className="health-events-container">
        <h4 className="text-sm font-semibold text-primary mb-2 flex items-center gap-1.5">
          <Clock size={16} className="text-cyan" />
          Health Transition Events
        </h4>
        {events.length === 0 ? (
          <p className="text-xs text-muted">No historical health transition events logged.</p>
        ) : (
          <div className="table-responsive">
            <table className="data-table text-xs">
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
                    <td className="text-muted">
                      {ev.createdAt ? new Date(ev.createdAt).toLocaleString() : "—"}
                    </td>
                    <td>
                      <span className="font-mono text-muted">{ev.fromHealth}</span>{" "}
                      <span className="text-cyan">→</span>{" "}
                      <span
                        className={`badge-pill font-bold ${
                          ev.toHealth === "HEALTHY"
                            ? "text-emerald"
                            : ev.toHealth === "DEGRADED"
                            ? "text-amber"
                            : "text-rose"
                        }`}
                      >
                        {ev.toHealth}
                      </span>
                    </td>
                    <td>
                      <span className="badge-pill bg-elevated font-mono">
                        {ev.triggeredBy}
                      </span>
                    </td>
                    <td className="text-secondary">{ev.reason}</td>
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
