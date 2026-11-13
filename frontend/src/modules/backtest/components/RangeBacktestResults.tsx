import React from "react";
import { AlertTriangle } from "lucide-react";
import { RangeBacktestResult, RangeSetupStats, RangeStats } from "../types/backtest.types";

type Tab = "summary" | "strategies" | "rules" | "daily" | "trades" | "portfolio";

const TABS: { key: Tab; label: string }[] = [
  { key: "summary", label: "Summary" },
  { key: "strategies", label: "Strategies" },
  { key: "rules", label: "Rules" },
  { key: "daily", label: "Daily P&L" },
  { key: "trades", label: "Trades" },
  { key: "portfolio", label: "With capital" },
];

function pnlClass(v: number | null | undefined): string {
  if (v === null || v === undefined) return "text-secondary";
  return v > 0 ? "text-bullish" : v < 0 ? "text-bearish" : "text-secondary";
}

function rs(v: number | null | undefined): string {
  if (v === null || v === undefined) return "--";
  return `${v >= 0 ? "+" : ""}${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function pct(v: number | null | undefined): string {
  return v === null || v === undefined ? "--" : `${v.toFixed(1)}%`;
}

const Stat: React.FC<{ label: string; value: React.ReactNode; cls?: string }> = ({ label, value, cls }) => (
  <div className="backtest-stat">
    <span className="label text-muted">{label}</span>
    <span className={`mono backtest-stat__value ${cls ?? ""}`}>{value}</span>
  </div>
);

const StatsCells: React.FC<{ s: RangeStats }> = ({ s }) => (
  <>
    <td className="mono">{s.trades}</td>
    <td className="mono">{pct(s.winRatePct)}</td>
    <td className={`mono ${pnlClass(s.netPnl)}`}>{rs(s.netPnl)}</td>
    <td className={`mono ${pnlClass(s.avgPnl)}`}>{rs(s.avgPnl)}</td>
    <td className="mono">{s.profitFactor ?? "--"}</td>
    <td className="mono text-bullish">{rs(s.best)}</td>
    <td className="mono text-bearish">{rs(s.worst)}</td>
  </>
);

const STATS_HEAD = (
  <>
    <th>Trades</th>
    <th>Win %</th>
    <th>Net Rs</th>
    <th>Avg Rs</th>
    <th>PF</th>
    <th>Best</th>
    <th>Worst</th>
  </>
);

const SetupTable: React.FC<{ rows: RangeSetupStats[]; empty: string }> = ({ rows, empty }) =>
  rows.length === 0 ? (
    <p className="text-muted micro">{empty}</p>
  ) : (
    <table className="data-table">
      <thead>
        <tr>
          <th>Strategy</th>
          <th>Policy</th>
          {STATS_HEAD}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.setup}>
            <td className="ticker">{r.setup}</td>
            <td>
              <span className={`badge ${r.policy === "CORE" || r.policy === "MERGED" ? "badge--blue" : "badge--slate"}`}>
                {r.policy.replace(/_/g, " ")}
              </span>
            </td>
            <StatsCells s={r} />
          </tr>
        ))}
      </tbody>
    </table>
  );

export const RangeBacktestResults: React.FC<{ result: RangeBacktestResult }> = ({ result }) => {
  const [tab, setTab] = React.useState<Tab>("summary");
  const t = result.totals;
  const p = result.portfolio;
  const worstSetup = result.perSetup[0];
  const costliestRule = result.ruleImpact.find((r) => r.verdict === "COST");

  return (
    <div className="card">
      <div className="backtest-stats-row">
        <Stat label="Trades" value={t.trades} />
        <Stat label="Win rate" value={pct(t.winRatePct)} />
        <Stat label="Net P&L (1 lot)" value={`Rs ${rs(t.netPnl)}`} cls={pnlClass(t.netPnl)} />
        <Stat label="Profit factor" value={t.profitFactor ?? "--"} />
        <Stat label="Max drawdown" value={`Rs ${rs(-t.maxDrawdown)}`} cls="text-bearish" />
        <Stat label="1st half / 2nd half" value={`${rs(t.firstHalfPnl)} / ${rs(t.secondHalfPnl)}`} />
        <Stat label="Trades / day" value={t.tradesPerDay} />
        <Stat label={`With Rs ${p.capital.toLocaleString("en-IN")}`} value={`Rs ${rs(p.netPnl)}`} cls={pnlClass(p.netPnl)} />
      </div>
      <p className="text-muted micro" style={{ marginTop: "var(--space-2)" }}>
        {result.range.from} to {result.range.to} · {result.range.tradingDays} trading days · {result.range.codes.join(", ")} ·{" "}
        {result.range.pricing}
      </p>
      {(worstSetup || costliestRule) && (
        <p className="text-secondary micro">
          {worstSetup && (
            <>
              Weakest live strategy: <span className="ticker">{worstSetup.setup}</span>{" "}
              <span className={pnlClass(worstSetup.netPnl)}>Rs {rs(worstSetup.netPnl)}</span>.{" "}
            </>
          )}
          {costliestRule && (
            <>
              Rule that cost the most: <span className="ticker">{costliestRule.rule}</span>{" "}
              <span className="text-bearish">Rs {rs(costliestRule.impact)}</span> (the trades it blocked would have made money).
            </>
          )}
        </p>
      )}
      {result.errors.length > 0 && (
        <p className="text-bearish micro">
          <AlertTriangle size={13} style={{ marginRight: 6, verticalAlign: "-2px" }} />
          {result.errors.length} date/index could not be replayed: {result.errors.slice(0, 3).map((e) => `${e.code} ${e.date}: ${e.error}`).join("; ")}
        </p>
      )}

      <div className="tab-bar" style={{ marginTop: "var(--space-4)" }}>
        {TABS.map((x) => (
          <button type="button" key={x.key} className={`tab ${tab === x.key ? "active" : ""}`} onClick={() => setTab(x.key)}>
            {x.label}
          </button>
        ))}
      </div>

      <div style={{ marginTop: "var(--space-4)" }}>
        {tab === "summary" && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Index</th>
                {STATS_HEAD}
              </tr>
            </thead>
            <tbody>
              {result.perIndex.map((r) => (
                <tr key={r.code}>
                  <td className="ticker">{r.code}</td>
                  <StatsCells s={r} />
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === "strategies" && (
          <>
            <span className="section-title">Live strategies (trades taken) — worst first</span>
            <SetupTable rows={result.perSetup} empty="No trades in this range." />
            <span className="section-title backtest-section-title" style={{ display: "block" }}>
              Blocked signals by strategy — what they would have made if taken (worst first)
            </span>
            <SetupTable rows={result.blockedSetups} empty="Nothing was blocked." />
          </>
        )}

        {tab === "rules" && (
          <>
            <p className="text-muted micro">
              Every signal a rule blocked was also simulated as if taken. SAVED = those trades would have lost (the rule
              helped). COST = they would have made money (the rule hurt). Worst rule first.
            </p>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Rule</th>
                  <th>Verdict</th>
                  <th>Impact Rs</th>
                  <th>Blocked</th>
                  {STATS_HEAD}
                </tr>
              </thead>
              <tbody>
                {result.ruleImpact.map((r) => (
                  <tr key={r.rule}>
                    <td className="ticker">{r.rule}</td>
                    <td>
                      <span className={`badge ${r.verdict === "SAVED" ? "badge--green" : "badge--red"}`}>{r.verdict}</span>
                    </td>
                    <td className={`mono ${pnlClass(r.impact)}`}>{rs(r.impact)}</td>
                    <td className="mono">{r.blockedSignals}</td>
                    <StatsCells s={r} />
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {tab === "daily" && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Trades</th>
                <th>Net Rs</th>
                <th>Cumulative Rs</th>
              </tr>
            </thead>
            <tbody>
              {result.daily.map((d) => (
                <tr key={d.date}>
                  <td className="mono">{d.date}</td>
                  <td className="mono">{d.trades}</td>
                  <td className={`mono ${pnlClass(d.netPnl)}`}>{rs(d.netPnl)}</td>
                  <td className={`mono ${pnlClass(d.cumPnl)}`}>{rs(d.cumPnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === "trades" && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Index</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>Strategy</th>
                <th>Side</th>
                <th>Strike</th>
                <th>Prem in</th>
                <th>Prem out</th>
                <th>Move</th>
                <th>Exit by</th>
                <th>Risk/lot</th>
                <th>Net Rs</th>
              </tr>
            </thead>
            <tbody>
              {result.trades.map((x, i) => (
                <tr key={i} title={x.reason}>
                  <td className="mono">{x.date}</td>
                  <td className="ticker">{x.code}</td>
                  <td className="mono">{x.time}</td>
                  <td className="mono">{x.exitTime}</td>
                  <td className="ticker">{x.setup}</td>
                  <td>
                    <span className={`badge ${x.side === "CE" ? "badge--green" : "badge--red"}`}>{x.side}</span>
                  </td>
                  <td className="mono">{x.strike}</td>
                  <td className="mono">{x.entryPremium.toFixed(1)}</td>
                  <td className="mono">{x.exitPremium.toFixed(1)}</td>
                  <td className={`mono ${pnlClass(x.pctMove)}`}>{x.pctMove.toFixed(1)}%</td>
                  <td>
                    <span className="badge badge--slate">{x.outcome.replace("_", " ")}</span>
                  </td>
                  <td className="mono">{rs(x.riskPerLot)}</td>
                  <td className={`mono ${pnlClass(x.netPnl)}`}>{rs(x.netPnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === "portfolio" && (
          <>
            <div className="backtest-stats-row">
              <Stat label="Capital" value={`Rs ${p.capital.toLocaleString("en-IN")}`} />
              <Stat label="Trades taken" value={p.trades} />
              <Stat label="Net P&L" value={`Rs ${rs(p.netPnl)}`} cls={pnlClass(p.netPnl)} />
              <Stat label="Return" value={pct(p.returnPct)} cls={pnlClass(p.returnPct)} />
              <Stat label="Ending capital" value={`Rs ${p.endingEquity.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`} />
              <Stat label="Max drawdown" value={`Rs ${rs(-p.maxDrawdown)}`} cls="text-bearish" />
              <Stat label="Win rate" value={pct(p.winRatePct)} />
              <Stat label="Lots avg / max" value={`${p.avgLots ?? "--"} / ${p.maxLots ?? "--"}`} />
            </div>
            <p className="text-muted micro" style={{ marginTop: "var(--space-2)" }}>
              {p.sizing === "MAX_LOTS"
                ? "Each trade buys the maximum lots the current capital (starting capital + realised P&L) pays for. "
                : `Live risk sizer: 1 lot, refused when it risks more than ${p.oneLotRiskPct}% of capital. `}
              One index position at a time; the day stops after a {p.maxLossPct}% loss.
            </p>
            {Object.keys(p.skipped).length > 0 && (
              <table className="data-table" style={{ marginBottom: "var(--space-4)" }}>
                <thead>
                  <tr>
                    <th>Trades skipped because</th>
                    <th>Count</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(p.skipped).map(([k, v]) => (
                    <tr key={k}>
                      <td className="text-secondary">{k}</td>
                      <td className="mono">{v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Trades</th>
                  <th>Net Rs</th>
                  <th>Cumulative Rs</th>
                </tr>
              </thead>
              <tbody>
                {p.daily.map((d) => (
                  <tr key={d.date}>
                    <td className="mono">{d.date}</td>
                    <td className="mono">{d.trades}</td>
                    <td className={`mono ${pnlClass(d.netPnl)}`}>{rs(d.netPnl)}</td>
                    <td className={`mono ${pnlClass(d.cumPnl)}`}>{rs(d.cumPnl)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <span className="section-title backtest-section-title" style={{ display: "block" }}>Trades taken with this capital</span>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Index</th>
                  <th>Entry</th>
                  <th>Exit</th>
                  <th>Strategy</th>
                  <th>Side</th>
                  <th>Lots</th>
                  <th>Qty</th>
                  <th>Capital used</th>
                  <th>Risk Rs</th>
                  <th>Net Rs</th>
                </tr>
              </thead>
              <tbody>
                {p.tradeList.map((x, i) => (
                  <tr key={i} title={x.reason}>
                    <td className="mono">{x.date}</td>
                    <td className="ticker">{x.code}</td>
                    <td className="mono">{x.time}</td>
                    <td className="mono">{x.exitTime}</td>
                    <td className="ticker">{x.setup}</td>
                    <td>
                      <span className={`badge ${x.side === "CE" ? "badge--green" : "badge--red"}`}>{x.side}</span>
                    </td>
                    <td className="mono">{x.lots}</td>
                    <td className="mono">{x.qty}</td>
                    <td className="mono">{x.capitalUsed.toLocaleString("en-IN", { maximumFractionDigits: 0 })}</td>
                    <td className="mono">{rs(-x.riskAmount)}</td>
                    <td className={`mono ${pnlClass(x.netPnlLots)}`}>{rs(x.netPnlLots)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  );
};
