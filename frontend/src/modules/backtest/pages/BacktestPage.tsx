import React from "react";
import { PlayCircle, Loader2, AlertTriangle } from "lucide-react";
import { BacktestCalendar } from "../components/BacktestCalendar";
import { IndexMultiSelect } from "../components/IndexMultiSelect";
import { BacktestResults } from "../components/BacktestResults";
import { useRunBacktest } from "../hooks/useBacktest";

export const BacktestPage: React.FC = () => {
  const [dates, setDates] = React.useState<string[]>([]);
  const [codes, setCodes] = React.useState<string[]>(["NIFTY", "SENSEX"]);
  const runMutation = useRunBacktest();

  const toggleDate = (d: string) =>
    setDates((prev) => (prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d].sort()));
  const toggleCode = (c: string) =>
    setCodes((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));

  const canRun = dates.length > 0 && codes.length > 0 && !runMutation.isPending;

  const handleRun = () => {
    if (!canRun) return;
    runMutation.mutate({ dates, codes });
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Backtest</h1>
          <p className="text-secondary micro">
            Replays the live engine's own rules over real Upstox candles for the dates and indices you pick.
          </p>
        </div>
        <div className="page-actions">
          <button type="button" className="btn btn--primary" disabled={!canRun} onClick={handleRun}>
            {runMutation.isPending ? <Loader2 size={16} className="spin" /> : <PlayCircle size={16} />}
            {runMutation.isPending ? "Running..." : "Run backtest"}
          </button>
        </div>
      </div>

      <div className="backtest-page-body">
        <div className="card backtest-picker-row">
          <div className="backtest-picker-col">
            <span className="section-title">Dates</span>
            <BacktestCalendar selected={dates} onToggle={toggleDate} />
            <span className="backtest-selected-summary">
              {dates.length === 0 ? "No dates picked yet" : `${dates.length} date(s) selected`}
            </span>
          </div>
          <div className="backtest-picker-col" style={{ flex: 1 }}>
            <span className="section-title">Indices</span>
            <IndexMultiSelect selected={codes} onToggle={toggleCode} />
            <span className="backtest-selected-summary">
              {codes.length === 0 ? "No indices picked yet" : `${codes.length} index(es) selected`}
            </span>
            <p className="text-muted micro" style={{ marginTop: "var(--space-2)", maxWidth: 480 }}>
              Premiums are a Black-Scholes estimate off the real underlying path (no historical option-chain
              feed exists) -- entries, exits and guardrails are the exact rules the live engine trades with.
              Needs a configured Upstox token; a date it can't fetch shows an error in that row instead of a
              made-up number.
            </p>
          </div>
        </div>

        {runMutation.isError && (
          <div className="card" style={{ borderColor: "var(--bearish-red)" }}>
            <AlertTriangle size={16} className="text-bearish" style={{ marginRight: 8, verticalAlign: "-3px" }} />
            <span className="text-bearish">
              {(runMutation.error as any)?.message ?? "Backtest run failed."}
            </span>
          </div>
        )}

        {runMutation.data && <BacktestResults result={runMutation.data} />}

        {!runMutation.data && !runMutation.isPending && !runMutation.isError && (
          <div className="empty-state">
            <PlayCircle className="empty-state__icon" />
            <div className="empty-state__title">Pick dates and indices, then run</div>
            <div className="empty-state__body">Results appear here: opportunities, wins, losses, win rate and net P&amp;L.</div>
          </div>
        )}
      </div>
    </div>
  );
};
