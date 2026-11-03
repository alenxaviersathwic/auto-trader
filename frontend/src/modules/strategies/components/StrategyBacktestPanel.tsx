import React, { useState } from "react";
import { Play, AlertCircle } from "lucide-react";
import { useBacktestStrategy } from "../hooks/useStrategies";
import { BacktestResult } from "../types/strategies.types";

interface StrategyBacktestPanelProps {
  strategyId: number;
  markets: string[];
}

const INDEX_CODES = new Set(["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "BANKEX"]);

export const StrategyBacktestPanel: React.FC<StrategyBacktestPanelProps> = ({ strategyId, markets }) => {
  const indexMarkets = markets.filter((m) => INDEX_CODES.has(m.toUpperCase()));
  const [underlyingCode, setUnderlyingCode] = useState<string>(indexMarkets[0] || "");
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const backtestMutation = useBacktestStrategy();

  const handleRun = () => {
    setErrorMsg(null);
    backtestMutation.mutate(
      { id: strategyId, underlyingCode: underlyingCode || null, years: 20 },
      {
        onSuccess: (data) => setResult(data),
        onError: (err: any) => setErrorMsg(err?.response?.data?.message || err?.message || "Backtest failed"),
      }
    );
  };

  return (
    <div className="sd-panel">
      <div className="sd-card">
        <div className="sd-card-header">
          <div>
            <span className="sd-card-title">Historical Backtest (20-Year Daily Bars)</span>
            <span className="sd-card-sub">
              Replays entry/exit rules against daily bars of the underlying index to test directional edge.
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {indexMarkets.length > 0 ? (
              <select
                className="sd-ctrl-select"
                value={underlyingCode}
                onChange={(e) => setUnderlyingCode(e.target.value)}
              >
                {indexMarkets.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            ) : (
              <span className="sd-tag sd-tag--red">
                No index underlying ({markets.join(", ") || "none"})
              </span>
            )}
            <button
              type="button"
              className="sd-ctrl-btn sd-ctrl-btn--primary"
              onClick={handleRun}
              disabled={backtestMutation.isPending || indexMarkets.length === 0}
            >
              <Play size={12} />
              <span>{backtestMutation.isPending ? "Running..." : "Run 20-Year Backtest"}</span>
            </button>
          </div>
        </div>

        {errorMsg && (
          <div className="sd-error-line">
            <AlertCircle size={13} />
            <span>{errorMsg}</span>
          </div>
        )}
      </div>

      {result && (
        <div className="sd-panel">
          {result.note && <p className="sd-bt-note">{result.note}</p>}

          <div className="sd-bt-stat-grid">
            <div className="sd-bt-stat">
              <span className="sd-bt-stat-label">Trades</span>
              <span className="sd-bt-stat-value">{result.totalTrades}</span>
            </div>
            <div className={`sd-bt-stat ${result.winRatePct >= 50 ? "pos" : "neg"}`}>
              <span className="sd-bt-stat-label">Win Rate</span>
              <span className="sd-bt-stat-value">{result.winRatePct}%</span>
            </div>
            <div className={`sd-bt-stat ${result.expectancyPct >= 0 ? "pos" : "neg"}`}>
              <span className="sd-bt-stat-label">Expectancy</span>
              <span className="sd-bt-stat-value">{result.expectancyPct >= 0 ? "+" : ""}{result.expectancyPct}%</span>
            </div>
            <div className="sd-bt-stat">
              <span className="sd-bt-stat-label">Profit Factor</span>
              <span className="sd-bt-stat-value">{result.profitFactor ?? "—"}</span>
            </div>
            <div className="sd-bt-stat pos">
              <span className="sd-bt-stat-label">Avg Win</span>
              <span className="sd-bt-stat-value">+{result.avgWinPct}%</span>
            </div>
            <div className="sd-bt-stat neg">
              <span className="sd-bt-stat-label">Avg Loss</span>
              <span className="sd-bt-stat-value">{result.avgLossPct}%</span>
            </div>
            <div className={`sd-bt-stat ${result.totalReturnPct >= 0 ? "pos" : "neg"}`}>
              <span className="sd-bt-stat-label">Total Return</span>
              <span className="sd-bt-stat-value">{result.totalReturnPct >= 0 ? "+" : ""}{result.totalReturnPct}%</span>
            </div>
            <div className="sd-bt-stat neg">
              <span className="sd-bt-stat-label">Max Drawdown</span>
              <span className="sd-bt-stat-value">-{result.maxDrawdownPct}%</span>
            </div>
          </div>

          {result.trades.length > 0 && (
            <div className="sd-card">
              <div className="sd-card-header">
                <span className="sd-card-title">Simulated Trades ({result.trades.length})</span>
              </div>
              <div className="table-wrap" style={{ border: "none", maxHeight: 340, overflowY: "auto" }}>
                <table className="table sd-compact-table">
                  <thead>
                    <tr>
                      <th>Side</th>
                      <th>Entry Date</th>
                      <th>Exit Date</th>
                      <th>Outcome</th>
                      <th className="text-right">Return</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.trades.map((t, i) => (
                      <tr key={i}>
                        <td>
                          <span className={`sd-tag ${t.side === "UP" ? "sd-tag--green" : "sd-tag--red"}`}>
                            {t.side}
                          </span>
                        </td>
                        <td className="font-mono">{t.entryDate}</td>
                        <td className="font-mono">{t.exitDate}</td>
                        <td>
                          <span className="sd-tag">{t.outcome}</span>
                        </td>
                        <td
                          className="text-right font-mono"
                          style={{
                            fontWeight: 700,
                            color: t.pnlPct >= 0 ? "var(--bullish-green)" : "var(--bearish-red)",
                          }}
                        >
                          {t.pnlPct >= 0 ? "+" : ""}{t.pnlPct}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
