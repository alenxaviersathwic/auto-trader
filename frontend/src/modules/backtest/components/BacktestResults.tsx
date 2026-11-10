import React from "react";
import { ChevronDown, ChevronRight, AlertTriangle } from "lucide-react";
import { BacktestDayResult, BacktestRunResult } from "../types/backtest.types";

function pnlClass(v: number | null | undefined): string {
  if (v === null || v === undefined) return "text-secondary";
  return v > 0 ? "text-bullish" : v < 0 ? "text-bearish" : "text-secondary";
}

function fmtRs(v: number | null | undefined): string {
  if (v === null || v === undefined) return "--";
  return `${v >= 0 ? "+" : ""}${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

const StatTile: React.FC<{ label: string; value: React.ReactNode; valueClassName?: string }> = ({
  label,
  value,
  valueClassName,
}) => (
  <div className="backtest-stat">
    <span className="label text-muted">{label}</span>
    <span className={`mono backtest-stat__value ${valueClassName ?? ""}`}>{value}</span>
  </div>
);

const DayRow: React.FC<{ run: BacktestDayResult }> = ({ run }) => {
  const [open, setOpen] = React.useState(false);
  if (run.error) {
    return (
      <tr>
        <td className="mono">{run.date}</td>
        <td className="ticker">{run.code}</td>
        <td colSpan={6} className="text-bearish">
          <AlertTriangle size={13} style={{ marginRight: 6, verticalAlign: "-2px" }} />
          {run.error}
        </td>
      </tr>
    );
  }
  return (
    <>
      <tr className="backtest-run-row" onClick={() => setOpen((o) => !o)}>
        <td className="mono">{run.date}</td>
        <td className="ticker">{run.code}</td>
        <td className="mono">{run.opportunities}</td>
        <td className="mono text-bullish">{run.wins}</td>
        <td className="mono text-bearish">{run.losses}</td>
        <td className="mono">{run.winRatePct !== null && run.winRatePct !== undefined ? `${run.winRatePct}%` : "--"}</td>
        <td className={`mono ${pnlClass(run.netPnl)}`}>Rs {fmtRs(run.netPnl)}</td>
        <td>{run.trades && run.trades.length > 0 ? (open ? <ChevronDown size={14} /> : <ChevronRight size={14} />) : null}</td>
      </tr>
      {open && run.trades && run.trades.length > 0 && (
        <tr>
          <td colSpan={8} style={{ padding: 0 }}>
            <table className="data-table backtest-trades-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Setup</th>
                  <th>Side</th>
                  <th>Day type</th>
                  <th>Strike</th>
                  <th>Mode</th>
                  <th>Entry</th>
                  <th>Exit</th>
                  <th>Move</th>
                  <th>Outcome</th>
                  <th>Hold</th>
                  <th>Net P&amp;L</th>
                </tr>
              </thead>
              <tbody>
                {run.trades.map((t, i) => (
                  <tr key={i}>
                    <td className="mono">{t.time}</td>
                    <td>{t.setup}</td>
                    <td>
                      <span className={`badge ${t.side === "CE" ? "badge--green" : "badge--red"}`}>{t.side}</span>
                    </td>
                    <td className="text-secondary micro">{t.dayType ?? "--"}</td>
                    <td className="mono">{t.strike}</td>
                    <td className="micro text-secondary">{t.mode}</td>
                    <td className="mono">{t.entryPremium.toFixed(2)}</td>
                    <td className="mono">{t.exitPremium.toFixed(2)}</td>
                    <td className={`mono ${pnlClass(t.pctMove)}`}>{t.pctMove.toFixed(0)}%</td>
                    <td>
                      <span className="badge badge--slate">{t.outcome}</span>
                    </td>
                    <td className="mono">{t.holdMinutes}m</td>
                    <td className={`mono ${pnlClass(t.netPnl)}`}>Rs {fmtRs(t.netPnl)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </td>
        </tr>
      )}
    </>
  );
};

export const BacktestResults: React.FC<{ result: BacktestRunResult }> = ({ result }) => {
  const { totals, perIndex, runs } = result;
  return (
    <div className="backtest-results">
      <div className="backtest-stats-row">
        <StatTile label="Dates x indices" value={`${totals.datesRun} x ${totals.indicesRun}`} />
        <StatTile label="Opportunities" value={totals.opportunities} />
        <StatTile label="Wins" value={totals.wins} valueClassName="text-bullish" />
        <StatTile label="Losses" value={totals.losses} valueClassName="text-bearish" />
        <StatTile label="Win rate" value={totals.winRatePct !== null ? `${totals.winRatePct}%` : "--"} />
        <StatTile label="Net P&L (1 lot each)" value={`Rs ${fmtRs(totals.netPnl)}`} valueClassName={pnlClass(totals.netPnl)} />
        {totals.errors > 0 && (
          <StatTile label="Could not fetch" value={totals.errors} valueClassName="text-bearish" />
        )}
      </div>

      {perIndex.length > 1 && (
        <>
          <div className="section-title backtest-section-title">Per index</div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Index</th>
                <th>Days run</th>
                <th>Opportunities</th>
                <th>Wins</th>
                <th>Losses</th>
                <th>Win rate</th>
                <th>Net P&amp;L</th>
              </tr>
            </thead>
            <tbody>
              {perIndex.map((p) => (
                <tr key={p.code}>
                  <td className="ticker">{p.code}</td>
                  <td className="mono">{p.daysRun}</td>
                  <td className="mono">{p.opportunities}</td>
                  <td className="mono text-bullish">{p.wins}</td>
                  <td className="mono text-bearish">{p.losses}</td>
                  <td className="mono">{p.winRatePct !== null ? `${p.winRatePct}%` : "--"}</td>
                  <td className={`mono ${pnlClass(p.netPnl)}`}>Rs {fmtRs(p.netPnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <div className="section-title backtest-section-title">Per date x index (click a row for the trade log)</div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Index</th>
            <th>Opportunities</th>
            <th>Wins</th>
            <th>Losses</th>
            <th>Win rate</th>
            <th>Net P&amp;L</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {runs.map((r, i) => (
            <DayRow key={`${r.date}-${r.code}-${i}`} run={r} />
          ))}
        </tbody>
      </table>
    </div>
  );
};
