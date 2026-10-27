import React, { useState } from "react";
import { AlertCircle, Plus, Info, ShieldCheck, TrendingUp, TrendingDown } from "lucide-react";
import { PerformanceSnapshot } from "../types/strategies.types";
import { useAddPerformanceSnapshot, useStrategyPerformance } from "../hooks/useStrategies";

interface PerformanceSectionProps {
  strategyId: number;
}

export const PerformanceSection: React.FC<PerformanceSectionProps> = ({
  strategyId,
}) => {
  const [showAddModal, setShowAddModal] = useState(false);
  const { data: snapshotsData, isLoading } = useStrategyPerformance(strategyId);
  const addSnapshotMutation = useAddPerformanceSnapshot();

  const [newSnapshot, setNewSnapshot] = useState({
    source: "PAPER",
    domain: "PAPER",
    totalTrades: 35,
    winningTrades: 22,
    losingTrades: 13,
    winRatePct: 62.8,
    netPnl: 4500.0,
    profitFactor: 1.85,
    maxDrawdown: 1200.0,
  });

  const handleAddSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    addSnapshotMutation.mutate(
      {
        strategyId,
        payload: {
          ...newSnapshot,
          totalTrades: Number(newSnapshot.totalTrades),
          winningTrades: Number(newSnapshot.winningTrades),
          losingTrades: Number(newSnapshot.losingTrades),
          winRatePct: Number(newSnapshot.winRatePct),
          netPnl: Number(newSnapshot.netPnl),
          profitFactor: Number(newSnapshot.profitFactor),
          maxDrawdown: Number(newSnapshot.maxDrawdown),
        },
      },
      {
        onSuccess: () => {
          setShowAddModal(false);
        },
      }
    );
  };

  const snapshots: PerformanceSnapshot[] = snapshotsData?.list || [];

  const getBadgeDescription = (flag: string) => {
    switch (flag) {
      case "LOW_SAMPLE":
        return "Sample size < 30 trades. Statistically unreliable.";
      case "PF_PNL_INCONSISTENT":
        return "Profit factor contradicts net P&L figure. Numbers require verification.";
      case "DRAWDOWN_PLACEHOLDER":
        return "Max drawdown is exactly 450.00 (placeholder value from legacy system).";
      case "PERFECT_RECORD_TINY_SAMPLE":
        return "100% win rate from fewer than 5 trades. Not statistically meaningful.";
      default:
        return flag;
    }
  };

  return (
    <div className="performance-section">
      <div className="section-toolbar mb-4 flex justify-between items-center">
        <div>
          <h3 className="section-heading text-lg font-semibold text-primary">
            Performance Snapshots & Reliability
          </h3>
          <p className="text-xs text-muted">
            Tracked trade samples across Backtest, Paper, Live, and Legacy imports. Flagged snapshots are automatically excluded from health policies.
          </p>
        </div>
        <button
          type="button"
          className="btn-kite-primary flex items-center gap-1.5 text-xs"
          onClick={() => setShowAddModal(true)}
        >
          <Plus size={14} />
          <span>Add Snapshot</span>
        </button>
      </div>

      {isLoading ? (
        <div className="p-4 text-center text-muted text-sm">Loading performance history...</div>
      ) : snapshots.length === 0 ? (
        <div className="card-surface p-6 text-center text-muted">
          <Info size={24} className="mx-auto mb-2 text-cyan opacity-80" />
          <p>No performance snapshots recorded for this strategy yet.</p>
        </div>
      ) : (
        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Domain</th>
                <th>Recorded At</th>
                <th>Total Trades</th>
                <th>Win Rate</th>
                <th>Net P&L</th>
                <th>Profit Factor</th>
                <th>Max DD</th>
                <th>Reliability Flags</th>
              </tr>
            </thead>
            <tbody>
              {snapshots.map((snap) => {
                const hasFlags = snap.reliabilityFlags && snap.reliabilityFlags.length > 0;
                return (
                  <tr key={snap.id} className={hasFlags ? "flagged-row" : ""}>
                    <td>
                      <span className="badge-pill bg-elevated font-mono">
                        {snap.source}
                      </span>
                    </td>
                    <td>
                      <span
                        className={`badge-pill ${
                          snap.domain === "LIVE"
                            ? "bg-rose"
                            : snap.domain === "PAPER"
                            ? "bg-cyan"
                            : "bg-surface"
                        }`}
                      >
                        {snap.domain}
                      </span>
                    </td>
                    <td className="text-xs text-muted">
                      {snap.createdAt ? new Date(snap.createdAt).toLocaleDateString() : "—"}
                    </td>
                    <td className="font-mono">
                      {snap.totalTrades} ({snap.winningTrades}W / {snap.losingTrades}L)
                    </td>
                    <td className="font-mono">
                      <span
                        className={snap.winRatePct >= 50 ? "text-emerald" : "text-rose"}
                      >
                        {Number(snap.winRatePct).toFixed(1)}%
                      </span>
                    </td>
                    <td className="font-mono font-semibold">
                      <span
                        className={`flex items-center gap-1 ${
                          snap.netPnl > 0
                            ? "text-emerald"
                            : snap.netPnl < 0
                            ? "text-rose"
                            : "text-muted"
                        }`}
                      >
                        {snap.netPnl > 0 ? (
                          <TrendingUp size={12} />
                        ) : snap.netPnl < 0 ? (
                          <TrendingDown size={12} />
                        ) : null}
                        ₹{Number(snap.netPnl).toLocaleString()}
                      </span>
                    </td>
                    <td className="font-mono">
                      {Number(snap.profitFactor).toFixed(2)}
                    </td>
                    <td className="font-mono text-rose">
                      ₹{Number(snap.maxDrawdown).toLocaleString()}
                    </td>
                    <td>
                      {hasFlags ? (
                        <div className="flex flex-wrap gap-1">
                          {snap.reliabilityFlags!.map((fl, idx) => (
                            <span
                              key={idx}
                              className="badge-reliability-flag"
                              title={getBadgeDescription(fl)}
                            >
                              <AlertCircle size={10} />
                              {fl}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="flex items-center gap-1 text-emerald text-xs font-medium">
                          <ShieldCheck size={13} />
                          Verified
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Snapshot Modal */}
      {showAddModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <div className="modal-header">
              <h3 className="modal-title font-semibold text-primary">
                Record Performance Snapshot
              </h3>
              <button
                type="button"
                className="btn-modal-close"
                onClick={() => setShowAddModal(false)}
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleAddSubmit}>
              <div className="modal-body grid grid-cols-2 gap-4">
                <div className="form-group">
                  <label>Data Source</label>
                  <select
                    className="select w-full"
                    value={newSnapshot.source}
                    onChange={(e) =>
                      setNewSnapshot({ ...newSnapshot, source: e.target.value })
                    }
                  >
                    <option value="PAPER">PAPER</option>
                    <option value="LIVE">LIVE</option>
                    <option value="BACKTEST">BACKTEST</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Execution Domain</label>
                  <select
                    className="select w-full"
                    value={newSnapshot.domain}
                    onChange={(e) =>
                      setNewSnapshot({ ...newSnapshot, domain: e.target.value as any })
                    }
                  >
                    <option value="PAPER">PAPER</option>
                    <option value="LIVE">LIVE</option>
                    <option value="UNKNOWN">UNKNOWN</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Total Trades</label>
                  <input
                    type="number"
                    className="input w-full"
                    value={newSnapshot.totalTrades}
                    onChange={(e) =>
                      setNewSnapshot({
                        ...newSnapshot,
                        totalTrades: Number(e.target.value),
                      })
                    }
                    min={0}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Winning Trades</label>
                  <input
                    type="number"
                    className="input w-full"
                    value={newSnapshot.winningTrades}
                    onChange={(e) =>
                      setNewSnapshot({
                        ...newSnapshot,
                        winningTrades: Number(e.target.value),
                      })
                    }
                    min={0}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Losing Trades</label>
                  <input
                    type="number"
                    className="input w-full"
                    value={newSnapshot.losingTrades}
                    onChange={(e) =>
                      setNewSnapshot({
                        ...newSnapshot,
                        losingTrades: Number(e.target.value),
                      })
                    }
                    min={0}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Win Rate %</label>
                  <input
                    type="number"
                    step="0.1"
                    className="input w-full"
                    value={newSnapshot.winRatePct}
                    onChange={(e) =>
                      setNewSnapshot({
                        ...newSnapshot,
                        winRatePct: Number(e.target.value),
                      })
                    }
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Net P&L (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    className="input w-full"
                    value={newSnapshot.netPnl}
                    onChange={(e) =>
                      setNewSnapshot({
                        ...newSnapshot,
                        netPnl: Number(e.target.value),
                      })
                    }
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Profit Factor</label>
                  <input
                    type="number"
                    step="0.01"
                    className="input w-full"
                    value={newSnapshot.profitFactor}
                    onChange={(e) =>
                      setNewSnapshot({
                        ...newSnapshot,
                        profitFactor: Number(e.target.value),
                      })
                    }
                    required
                  />
                </div>
                <div className="form-group col-span-2">
                  <label>Max Drawdown (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    className="input w-full"
                    value={newSnapshot.maxDrawdown}
                    onChange={(e) =>
                      setNewSnapshot({
                        ...newSnapshot,
                        maxDrawdown: Number(e.target.value),
                      })
                    }
                    required
                  />
                </div>
              </div>
              <div className="modal-actions">
                <button
                  type="button"
                  className="btn-outline text-xs"
                  onClick={() => setShowAddModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-kite-primary text-xs"
                  disabled={addSnapshotMutation.isPending}
                >
                  {addSnapshotMutation.isPending ? "Saving..." : "Save Snapshot"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
