import React, { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Activity, ExternalLink } from "lucide-react";
import { useTradeSearch } from "../hooks/useTrades";
import { ActiveTrade, TradeSearchFilter } from "../types/trades.types";
import { formatRupee } from "../../opportunities/components/formatters";

const hms = (iso: string | null): string =>
  iso ? new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false }) : "—";

function stateBadge(state: ActiveTrade["tradeState"]): string {
  return state === "RUNNING" ? "badge badge--green" : "badge badge--slate";
}

function profileBadge(profile: ActiveTrade["traderProfile"]): string {
  return profile === "HIGH_CONVICTION" ? "badge badge--cyan" : "badge badge--amber";
}

export const TradesPage: React.FC = () => {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<TradeSearchFilter>({
    page: 0,
    limit: 25,
    sortBy: "createdAt",
    sortDir: "desc",
    status: "ACTIVE",
  });

  const { data, isLoading } = useTradeSearch(filter);
  const trades = data?.list ?? [];

  const runningCount = trades.filter((t) => t.tradeState === "RUNNING").length;
  const totalNetPnl = trades.reduce((acc, t) => acc + Number(t.netPnl || 0), 0);
  const totalCapitalUsed = trades
    .filter((t) => t.tradeState === "RUNNING")
    .reduce((acc, t) => acc + Number(t.capitalUsed || 0), 0);

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Active Trader Positions</h1>
          <p className="text-secondary micro">
            Dedicated human-like Trader loops per locked trade · Dynamic SL & Target trailing
          </p>
        </div>
        <div className="page-actions">
          <select
            className="select"
            value={filter.tradeState ?? ""}
            onChange={(e) =>
              setFilter((prev) => ({
                ...prev,
                page: 0,
                tradeState: (e.target.value || undefined) as TradeSearchFilter["tradeState"],
              }))
            }
          >
            <option value="">All States</option>
            <option value="RUNNING">RUNNING (Live)</option>
            <option value="EXITED">EXITED (Closed)</option>
          </select>
        </div>
      </div>

      <div className="content-body sl-page">
        <div className="sl-strip">
          <div className="sl-stat">
            <span className="label">Active Trades Running</span>
            <span className="sl-stat__value text-green">{runningCount}</span>
            <span className="micro text-muted">1 dedicated loop per trade</span>
          </div>
          <div className="sl-stat">
            <span className="label">Active Capital Deployed</span>
            <span className="sl-stat__value">{formatRupee(totalCapitalUsed)}</span>
          </div>
          <div className="sl-stat">
            <span className="label">Combined Net P&L (Page)</span>
            <span className={`sl-stat__value ${totalNetPnl > 0 ? "text-green" : totalNetPnl < 0 ? "text-red" : ""}`}>
              {formatRupee(totalNetPnl)}
            </span>
          </div>
          <div className="sl-stat">
            <span className="label">Total Positions</span>
            <span className="sl-stat__value">{data?.totalItems ?? 0}</span>
          </div>
        </div>

        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Contract</th>
                <th>Session</th>
                <th>Profile · Win%</th>
                <th>Lots (Qty)</th>
                <th>Entry At</th>
                <th>Active SL</th>
                <th>Active Target</th>
                <th>Last / Exit</th>
                <th>Net P&L</th>
                <th>Broker</th>
                <th>State</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={13} className="text-muted">Loading trader positions…</td>
                </tr>
              )}
              {!isLoading && trades.length === 0 && (
                <tr>
                  <td colSpan={13} className="text-muted">
                    No active trades yet. Lock and enter an opportunity from a Trading Session to launch a Trader loop.
                  </td>
                </tr>
              )}
              {trades.map((t) => {
                const pnlClass = t.netPnl > 0 ? "text-green" : t.netPnl < 0 ? "text-red" : "";
                return (
                  <tr
                    key={t.id}
                    onClick={() => navigate({ to: "/trades/$tradeId", params: { tradeId: String(t.id) } })}
                    style={{ cursor: "pointer" }}
                  >
                    <td className="mono">#{t.id}</td>
                    <td className="mono text-primary">
                      {t.underlyingCode} {t.strike} {t.optionType}
                      <div className="micro text-muted">{t.strategy ?? t.expiry}</div>
                    </td>
                    <td className="mono">S#{t.sessionId} · {t.sessionType}</td>
                    <td>
                      <span className={profileBadge(t.traderProfile)}>{t.traderProfile}</span>{" "}
                      <span className="mono micro">{t.winRatePct.toFixed(0)}%</span>
                    </td>
                    <td className="mono">{t.lots} ({t.quantity})</td>
                    <td className="mono">{formatRupee(t.entryAt)}</td>
                    <td className="mono text-red">{formatRupee(t.currentStop)}</td>
                    <td className="mono text-green">{formatRupee(t.currentTarget)}</td>
                    <td className="mono">{formatRupee(t.exitPrice ?? t.lastPrice)}</td>
                    <td className={`mono ${pnlClass}`}>
                      {formatRupee(t.netPnl)} ({t.pnlPct >= 0 ? "+" : ""}{t.pnlPct.toFixed(1)}%)
                    </td>
                    <td className="micro">
                      {t.routeThroughUpstox ? `Upstox (${t.brokerStatus})` : "Simulated"}
                    </td>
                    <td>
                      <span className={stateBadge(t.tradeState)}>
                        {t.tradeState === "RUNNING" ? (
                          <>
                            <Activity size={11} /> LIVE
                          </>
                        ) : (
                          t.exitReason ?? "EXITED"
                        )}
                      </span>
                      <div className="micro text-muted">{hms(t.exitedAt ?? t.enteredAt)}</div>
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        className="btn btn--ghost"
                        onClick={() => navigate({ to: "/trades/$tradeId", params: { tradeId: String(t.id) } })}
                      >
                        <ExternalLink size={13} />
                        <span>Cockpit</span>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

