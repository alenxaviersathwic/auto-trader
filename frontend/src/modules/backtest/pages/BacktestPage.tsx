import React from "react";
import { PlayCircle, Loader2, AlertTriangle } from "lucide-react";
import { IndexMultiSelect } from "../components/IndexMultiSelect";
import { RangeBacktestResults } from "../components/RangeBacktestResults";
import { useRangeBacktestJob, useStartRangeBacktest } from "../hooks/useBacktest";

const MAX_RANGE_DAYS = 95;

function isoDaysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

export const BacktestPage: React.FC = () => {
  const today = isoDaysAgo(0);
  const [fromDate, setFromDate] = React.useState(isoDaysAgo(30));
  const [toDate, setToDate] = React.useState(today);
  const [codes, setCodes] = React.useState<string[]>(["NIFTY", "BANKNIFTY", "SENSEX"]);
  const [capital, setCapital] = React.useState(50000);
  const [maxLossPct, setMaxLossPct] = React.useState(4);
  const [sizing, setSizing] = React.useState<"MAX_LOTS" | "RISK">("MAX_LOTS");
  const [jobId, setJobId] = React.useState<string | null>(null);
  const start = useStartRangeBacktest();
  const job = useRangeBacktestJob(jobId);

  const toggleCode = (c: string) =>
    setCodes((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));

  const spanDays = (new Date(toDate).getTime() - new Date(fromDate).getTime()) / 86400000;
  const rangeError =
    !fromDate || !toDate
      ? "Pick both dates"
      : spanDays < 0
        ? "To date is before from date"
        : spanDays > MAX_RANGE_DAYS
          ? `Max ${MAX_RANGE_DAYS} days per run`
          : null;
  const running = start.isPending || job.data?.state === "RUNNING";
  const canRun = !rangeError && codes.length > 0 && capital > 0 && !running;

  const handleRun = () => {
    if (!canRun) return;
    start.mutate({ fromDate, toDate, codes, capital, maxLossPct, sizing }, { onSuccess: (j) => setJobId(j.jobId) });
  };

  const err = (start.error as any)?.message ?? (job.error as any)?.message ?? (job.data?.state === "FAILED" ? job.data.error : null);

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Backtest</h1>
          <p className="text-secondary micro">
            Fetches Upstox candles for the range and replays today's live strategies and rules: trades, P&amp;L, the
            weakest strategy and what each rule saved or cost.
          </p>
        </div>
        <div className="page-actions">
          <button type="button" className="btn btn--primary" disabled={!canRun} onClick={handleRun}>
            {running ? <Loader2 size={16} className="spin" /> : <PlayCircle size={16} />}
            {running ? "Running..." : "Run backtest"}
          </button>
        </div>
      </div>

      <div className="backtest-page-body">
        <div className="card backtest-picker-row">
          <div className="form-group">
            <label className="form-label" htmlFor="bt-from">From</label>
            <input id="bt-from" type="date" className="input" value={fromDate} max={toDate || today}
              onChange={(e) => setFromDate(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="bt-to">To</label>
            <input id="bt-to" type="date" className="input" value={toDate} min={fromDate} max={today}
              onChange={(e) => setToDate(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="bt-capital">Capital (Rs)</label>
            <input id="bt-capital" type="number" className="input mono" min={1000} step={1000} value={capital}
              onChange={(e) => setCapital(Number(e.target.value))} />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="bt-maxloss">Daily max loss %</label>
            <input id="bt-maxloss" type="number" className="input mono" min={0.5} max={100} step={0.5} value={maxLossPct}
              onChange={(e) => setMaxLossPct(Number(e.target.value))} />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="bt-sizing">Lots per trade</label>
            <select id="bt-sizing" className="select" value={sizing}
              onChange={(e) => setSizing(e.target.value as "MAX_LOTS" | "RISK")}>
              <option value="MAX_LOTS">Max lots the capital buys</option>
              <option value="RISK">Live risk sizer (1 lot)</option>
            </select>
          </div>
          <div className="backtest-picker-col" style={{ flex: 1 }}>
            <span className="form-label">Indices</span>
            <IndexMultiSelect selected={codes} onToggle={toggleCode} />
            {rangeError && <span className="form-error">{rangeError}</span>}
          </div>
        </div>

        {running && (
          <div className="card">
            <div className="backtest-progress">
              <div className="backtest-progress__fill" style={{ width: `${job.data?.progressPct ?? 0}%` }} />
            </div>
            <p className="text-muted micro" style={{ marginTop: "var(--space-2)" }}>
              {job.data?.stage ?? "starting"} · {(job.data?.progressPct ?? 0).toFixed(0)}%
            </p>
          </div>
        )}

        {err && !running && (
          <div className="card" style={{ borderColor: "var(--bearish-red)" }}>
            <AlertTriangle size={16} className="text-bearish" style={{ marginRight: 8, verticalAlign: "-3px" }} />
            <span className="text-bearish">{err}</span>
          </div>
        )}

        {job.data?.state === "DONE" && job.data.result && <RangeBacktestResults result={job.data.result} />}

        {!jobId && !start.isPending && !start.isError && (
          <div className="empty-state">
            <PlayCircle className="empty-state__icon" />
            <div className="empty-state__title">Pick a date range and indices, then run</div>
            <div className="empty-state__body">
              Results: trades, win rate, P&amp;L per index, strategy and day, rule impact, and the result with your capital.
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
