import React, { useState } from "react";
import { Plus, X } from "lucide-react";
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

  return (
    <div className="sd-panel">
      <div className="sd-card">
        <div className="sd-card-header">
          <div>
            <span className="sd-card-title">
              Performance Snapshots ({snapshots.length})
            </span>
            <p className="sd-card-sub">
              Trade samples across Backtest, Paper, Live, and Legacy imports.
            </p>
          </div>
          <button
            type="button"
            className="sd-ctrl-btn sd-ctrl-btn--primary"
            onClick={() => setShowAddModal(true)}
          >
            <Plus size={13} />
            <span>Add Snapshot</span>
          </button>
        </div>

        {isLoading ? (
          <div className="sd-empty-inline">Loading performance snapshots…</div>
        ) : snapshots.length === 0 ? (
          <div className="sd-empty-inline">
            No performance snapshots recorded for this strategy yet.
          </div>
        ) : (
          <div className="table-scroll-container">
            <table className="data-table sd-compact-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Domain</th>
                  <th>Recorded Date</th>
                  <th>Trades</th>
                  <th>Win Rate</th>
                  <th>Net P&amp;L</th>
                  <th>Profit Factor</th>
                  <th>Max DD</th>
                  <th>Audit Status</th>
                </tr>
              </thead>
              <tbody>
                {snapshots.map((snap) => {
                  const hasFlags = snap.reliabilityFlags && snap.reliabilityFlags.length > 0;
                  return (
                    <tr key={snap.id}>
                      <td>
                        <span className="sd-tag mono">{snap.source}</span>
                      </td>
                      <td>
                        <span
                          className={`sd-tag mono ${
                            snap.domain === "LIVE"
                              ? "sd-tag--green"
                              : snap.domain === "PAPER"
                              ? "sd-tag--cyan"
                              : ""
                          }`}
                        >
                          {snap.domain}
                        </span>
                      </td>
                      <td className="mono text-muted">
                        {snap.createdAt ? new Date(snap.createdAt).toLocaleDateString("en-IN") : "—"}
                      </td>
                      <td className="mono">
                        {snap.totalTrades} ({snap.winningTrades}W / {snap.losingTrades}L)
                      </td>
                      <td className={`mono ${snap.winRatePct >= 50 ? "text-green" : "text-red"}`}>
                        {Number(snap.winRatePct).toFixed(1)}%
                      </td>
                      <td
                        className={`mono ${
                          snap.netPnl > 0 ? "text-green" : snap.netPnl < 0 ? "text-red" : ""
                        }`}
                      >
                        {snap.netPnl > 0 ? "+" : ""}₹{Number(snap.netPnl).toLocaleString("en-IN")}
                      </td>
                      <td className="mono text-amber">
                        {Number(snap.profitFactor).toFixed(2)}
                      </td>
                      <td className="mono text-red">
                        -₹{Number(snap.maxDrawdown).toLocaleString("en-IN")}
                      </td>
                      <td>
                        {hasFlags ? (
                          <div className="sd-summary-badges">
                            {snap.reliabilityFlags!.map((fl, idx) => (
                              <span key={idx} className="sd-tag sd-tag--amber mono">
                                {fl}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="sd-tag sd-tag--green">VERIFIED</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Snapshot Modal */}
      {showAddModal && (
        <div className="modal-backdrop" onClick={() => setShowAddModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="sd-card-header">
              <span className="sd-card-title">Record Performance Snapshot</span>
              <button
                type="button"
                className="sd-ctrl-btn"
                onClick={() => setShowAddModal(false)}
              >
                <X size={13} />
              </button>
            </div>
            <form onSubmit={handleAddSubmit}>
              <div className="sd-param-grid">
                <div className="form-group">
                  <label className="form-label">Data Source</label>
                  <select
                    className="select"
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
                  <label className="form-label">Execution Domain</label>
                  <select
                    className="select"
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
                  <label className="form-label">Total Trades</label>
                  <input
                    type="number"
                    className="input mono"
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
                  <label className="form-label">Winning Trades</label>
                  <input
                    type="number"
                    className="input mono"
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
                  <label className="form-label">Losing Trades</label>
                  <input
                    type="number"
                    className="input mono"
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
                  <label className="form-label">Win Rate (%)</label>
                  <input
                    type="number"
                    step="0.1"
                    className="input mono"
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
                  <label className="form-label">Net P&amp;L (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    className="input mono"
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
                  <label className="form-label">Profit Factor</label>
                  <input
                    type="number"
                    step="0.01"
                    className="input mono"
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
                <div className="form-group" style={{ gridColumn: "1 / -1" }}>
                  <label className="form-label">Max Drawdown (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    className="input mono"
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
                  className="sd-ctrl-btn"
                  onClick={() => setShowAddModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="sd-ctrl-btn sd-ctrl-btn--primary"
                  disabled={addSnapshotMutation.isPending}
                >
                  {addSnapshotMutation.isPending ? "Saving…" : "Save Snapshot"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
