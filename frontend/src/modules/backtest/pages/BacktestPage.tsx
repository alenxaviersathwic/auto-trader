import React from "react";
import { PlayCircle, Loader2, AlertTriangle, Cpu } from "lucide-react";
import { IndexMultiSelect } from "../components/IndexMultiSelect";
import { RangeBacktestResults } from "../components/RangeBacktestResults";
import { useRangeBacktestJob, useStartRangeBacktest } from "../hooks/useBacktest";
import { TRADER_CODES, TRADER_META } from "../../trades/components/traderMeta";

type ManagerId = "MY_VIEW" | "AI_VIEW";
interface BacktestManagerCfg {
  activeManager: ManagerId;
  llmMode: Record<ManagerId, "AUTO_LOCK" | "ASSIST_ONLY">;
  maxParallel: Record<ManagerId, 1 | 2 | 3>;
  guardEnabled: Record<ManagerId, boolean>;
}

const MANAGER_CFG_KEY = "ordergrid.sessionManagersConfig";
const DEFAULT_MGR_CFG: BacktestManagerCfg = {
  activeManager: "MY_VIEW",
  llmMode: { MY_VIEW: "AUTO_LOCK", AI_VIEW: "AUTO_LOCK" },
  maxParallel: { MY_VIEW: 2, AI_VIEW: 3 },
  guardEnabled: { MY_VIEW: true, AI_VIEW: true },
};

function loadBacktestManagerCfg(): BacktestManagerCfg {
  try {
    const raw = localStorage.getItem(MANAGER_CFG_KEY);
    return raw ? { ...DEFAULT_MGR_CFG, ...JSON.parse(raw) } : DEFAULT_MGR_CFG;
  } catch {
    return DEFAULT_MGR_CFG;
  }
}

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
  const [traderFilter, setTraderFilter] = React.useState<string>("ALL");
  const [sideFilter, setSideFilter] = React.useState<"ALL" | "CE" | "PE">("ALL");
  const [mgrCfg, setMgrCfg] = React.useState<BacktestManagerCfg>(() => loadBacktestManagerCfg());
  const [jobId, setJobId] = React.useState<string | null>(null);
  const start = useStartRangeBacktest();
  const job = useRangeBacktestJob(jobId);

  const updateMgrCfg = (updater: (prev: BacktestManagerCfg) => BacktestManagerCfg) => {
    setMgrCfg((prev) => {
      const next = updater(prev);
      try {
        localStorage.setItem(MANAGER_CFG_KEY, JSON.stringify(next));
      } catch {
        // ignore storage errors
      }
      return next;
    });
  };
  const activeMgr = mgrCfg.activeManager;

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
    start.mutate(
      {
        fromDate,
        toDate,
        codes,
        capital,
        maxLossPct,
        sizing,
        managerView: activeMgr,
        traderFilter: traderFilter as "ALL" | "FIB_GOLDEN_TRADER" | "FLOW_MOMENTUM_TRADER",
        sideFilter,
        maxParallel: mgrCfg.maxParallel[activeMgr],
        guardEnabled: mgrCfg.guardEnabled[activeMgr],
      },
      { onSuccess: (j) => setJobId(j.jobId) },
    );
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
            <label className="form-label" htmlFor="bt-maxloss">Session max loss (% of capital)</label>
            <input
              id="bt-maxloss"
              type="number"
              className="input font-mono"
              min={0.5}
              max={20}
              step={0.5}
              value={maxLossPct}
              onChange={(e) => setMaxLossPct(Number(e.target.value))}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="bt-trader">Opportunities Trader</label>
            <select
              id="bt-trader"
              className="select"
              value={traderFilter}
              onChange={(e) => setTraderFilter(e.target.value)}
            >
              <option value="ALL">All Opportunities Traders (Select All)</option>
              {TRADER_CODES.map((code) => (
                <option key={code} value={code}>
                  {TRADER_META[code].name} ({TRADER_META[code].tag})
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="bt-side">Option Side</label>
            <select
              id="bt-side"
              className="select"
              value={sideFilter}
              onChange={(e) => setSideFilter(e.target.value as "ALL" | "CE" | "PE")}
            >
              <option value="ALL">Both CE &amp; PE</option>
              <option value="CE">Calls Only (CE)</option>
              <option value="PE">Puts Only (PE)</option>
            </select>
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

        {/* Compact Session Manager Config Strip (Synced with /trades?tab=sessions) */}
        <div
          className="card"
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            padding: "10px 14px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span className="form-label" style={{ margin: 0, display: "inline-flex", alignItems: "center", gap: 5 }}>
              <Cpu size={13} className="text-blue" /> Session Manager:
            </span>
            <button
              type="button"
              className={`toggle-chip ${activeMgr === "MY_VIEW" ? "toggle-chip--active" : ""}`}
              onClick={() => updateMgrCfg((p) => ({ ...p, activeManager: "MY_VIEW" }))}
            >
              Session Manager 1 · My Experience
            </button>
            <button
              type="button"
              className={`toggle-chip ${activeMgr === "AI_VIEW" ? "toggle-chip--active" : ""}`}
              onClick={() => updateMgrCfg((p) => ({ ...p, activeManager: "AI_VIEW" }))}
            >
              Session Manager 2 · Indian Quant Desk
            </button>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <div style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <span className="micro text-muted">LLM:</span>
              {(["AUTO_LOCK", "ASSIST_ONLY"] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  className={`toggle-chip ${mgrCfg.llmMode[activeMgr] === mode ? "toggle-chip--active" : ""}`}
                  style={{ padding: "2px 7px", fontSize: "0.7rem" }}
                  onClick={() =>
                    updateMgrCfg((p) => ({ ...p, llmMode: { ...p.llmMode, [activeMgr]: mode } }))
                  }
                >
                  {mode === "AUTO_LOCK" ? "Auto Lock" : "Assist"}
                </button>
              ))}
            </div>

            <div style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <span className="micro text-muted">Max Parallel:</span>
              {([1, 2, 3] as const).map((cnt) => (
                <button
                  key={cnt}
                  type="button"
                  className={`toggle-chip ${mgrCfg.maxParallel[activeMgr] === cnt ? "toggle-chip--active" : ""}`}
                  style={{ padding: "2px 7px", fontSize: "0.7rem" }}
                  onClick={() =>
                    updateMgrCfg((p) => ({ ...p, maxParallel: { ...p.maxParallel, [activeMgr]: cnt } }))
                  }
                >
                  {cnt}
                </button>
              ))}
            </div>

            <button
              type="button"
              className={`toggle-chip ${mgrCfg.guardEnabled[activeMgr] ? "toggle-chip--active" : ""}`}
              style={{ padding: "2px 8px", fontSize: "0.7rem" }}
              onClick={() =>
                updateMgrCfg((p) => ({
                  ...p,
                  guardEnabled: { ...p.guardEnabled, [activeMgr]: !p.guardEnabled[activeMgr] },
                }))
              }
            >
              {activeMgr === "MY_VIEW" ? "0.786 + No-FOMO" : "15m Time-Stop"}:{" "}
              {mgrCfg.guardEnabled[activeMgr] ? "ON" : "OFF"}
            </button>
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

        {job.data?.state === "DONE" && job.data.result && (
          <RangeBacktestResults
            result={job.data.result}
            traderFilter={traderFilter}
            sideFilter={sideFilter}
          />
        )}

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
