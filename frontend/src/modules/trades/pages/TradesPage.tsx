import React, { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  Activity,
  Cpu,
  ExternalLink,
  Plus,
  Search,
  ShieldCheck,
  X,
  Zap,
} from "lucide-react";
import { useTradeSearch, useTraderPresets } from "../hooks/useTrades";
import { ActiveTrade, TradeSearchFilter, TraderCode } from "../types/trades.types";
import { TRADER_META, normalizeTraderCode, traderForStrategy } from "../components/traderMeta";
import { useCreateSession } from "../../sessions/hooks/useSessions";
import { SessionDialog } from "../../sessions/components/SessionDialog";
import { formatCompactRupee, formatRupee } from "../../opportunities/components/formatters";

const hms = (iso: string | null): string =>
  iso
    ? new Date(iso).toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      })
    : "—";

const signedRupee = (n: number): string =>
  n === 0 ? "₹0.00" : `${n > 0 ? "+" : "-"}${formatRupee(Math.abs(n))}`;

const traderOf = (t: ActiveTrade): TraderCode =>
  normalizeTraderCode(t.marketTelemetry?.traderCode) ?? traderForStrategy(t.strategy);

/**
 * Traders & Session Hub (/trades):
 * - Tab 1: Opportunities Trader (Specialist Traders, 4-Level Risk Config, Live & Historical Trades)
 * - Tab 2: Session Manager (2 LLM-Supported Session Managers + Compact Inline Config)
 */
export const TradesPage: React.FC = () => {
  const navigate = useNavigate({ from: "/trades" });

  const [selectedTrader, setSelectedTrader] = useState<TraderCode | "">("");
  const [searchInput, setSearchInput] = useState<string>("");
  const [sessionDialogOpen, setSessionDialogOpen] = useState<boolean>(false);
  const [filter, setFilter] = useState<TradeSearchFilter>({
    page: 0,
    limit: 25,
    sortBy: "createdAt",
    sortDir: "desc",
    status: "ACTIVE",
  });

  const { data: presets } = useTraderPresets();
  const { data, isLoading } = useTradeSearch(filter);
  const createSessionMutation = useCreateSession();

  const allTrades = data?.list ?? [];
  const trades = selectedTrader ? allTrades.filter((t) => traderOf(t) === selectedTrader) : allTrades;
  const running = allTrades.filter((t) => t.tradeState === "RUNNING");
  const capitalInUse = running.reduce((sum, t) => sum + Number(t.capitalUsed || 0), 0);
  const netPnl = allTrades.reduce((sum, t) => sum + Number(t.netPnl || 0), 0);
  const openCockpit = (id: number) =>
    navigate({ to: "/trades/$tradeId", params: { tradeId: String(id) } });

  return (
    <div className="sp-page">
      <div className="sp-toolbar">
        <div className="sp-toolbar-left">
          <div className="sp-tabs" role="tablist">
            <span className="sp-tab sp-tab--active" role="tab" aria-selected="true">
              <Cpu size={13} />
              <span>Trade history</span>
              <span className="sp-tab-count mono">{allTrades.length}</span>
            </span>
          </div>

          <div className="sp-summary-strip">
            <div className="sp-stat-pill" title="Trades running right now">
              <span className={`sp-status-dot ${running.length > 0 ? "sp-status-dot--live" : ""}`} />
              <span className="sp-stat-label">Live trades</span>
              <span className="sp-stat-val mono sp-up">{running.length}</span>
            </div>
            <div className="sp-stat-pill" title="Premium deployed in open positions">
              <span className="sp-stat-label">Capital in use</span>
              <span className="sp-stat-val mono">{formatCompactRupee(capitalInUse)}</span>
            </div>
            <div className="sp-stat-pill" title="Net P&L of the trades on this page">
              <span className="sp-stat-label">Net P&amp;L</span>
              <span className={`sp-stat-val mono ${netPnl > 0 ? "sp-up" : netPnl < 0 ? "sp-down" : ""}`}>
                {signedRupee(netPnl)}
              </span>
            </div>
          </div>
        </div>

        <div className="sp-actions">
          <button
            type="button"
            className="sp-btn sp-btn--run"
            onClick={() => setSessionDialogOpen(true)}
          >
            <Plus size={13} /> New Session
          </button>
        </div>
      </div>

      <>
          {/* Trader Filter Strip */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
            <div className="toggle-chip-group">
              <button
                type="button"
                className={`toggle-chip ${selectedTrader === "" ? "toggle-chip--active" : ""}`}
                onClick={() => setSelectedTrader("")}
              >
                All Traders ({allTrades.length})
              </button>
              {(presets ?? []).map((p) => {
                const code = normalizeTraderCode(p.code);
                if (!code) return null;
                return (
                  <button
                    key={code}
                    type="button"
                    className={`toggle-chip ${selectedTrader === code ? "toggle-chip--active" : ""}`}
                    onClick={() => setSelectedTrader((prev) => (prev === code ? "" : code))}
                  >
                    {TRADER_META[code].tag}
                    {p.activeTradesCount > 0 ? ` (${p.activeTradesCount} LIVE)` : ""}
                  </button>
                );
              })}
            </div>
          </div>

      {/* The two traders: what each checks, and its real results */}
      <div className="sp-grid">
        {(presets ?? []).map((preset) => {
          const code = normalizeTraderCode(preset.code);
          if (!code) return null;
          const meta = TRADER_META[code];
          const pnl = Number(preset.netPnl || 0);
          const closed = preset.totalTradesCount - preset.activeTradesCount;
          const isLive = preset.activeTradesCount > 0;
          return (
            <div
              key={code}
              className={`sp-card ${pnl > 0 ? "sp-card--bull" : pnl < 0 ? "sp-card--bear" : ""} ${
                isLive ? "sp-card--iterating" : ""
              } ${selectedTrader === code ? "sp-card--selected" : ""}`}
              onClick={() => setSelectedTrader((prev) => (prev === code ? "" : code))}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setSelectedTrader((prev) => (prev === code ? "" : code));
                }
              }}
            >
              <div className="sp-card-top">
                <div className="sp-symbol-row">
                  <span className={`badge ${meta.badgeClass} mono`}>{meta.tag}</span>
                  <h2 className="sp-name">{meta.name}</h2>
                </div>
                {isLive ? (
                  <span className="badge badge--green">
                    <Activity size={11} /> {preset.activeTradesCount} LIVE
                  </span>
                ) : (
                  <span className="badge badge--slate">IDLE</span>
                )}
              </div>

              <ul className="desk-checks">
                {meta.checks.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
              <div className="micro text-muted">{meta.manages}</div>

              <div className="sp-metrics">
                <div className="sp-metric-cell">
                  <div className="sp-metric-label">Open</div>
                  <div className="sp-metric-value mono">{preset.activeTradesCount}</div>
                </div>
                <div className="sp-metric-cell">
                  <div className="sp-metric-label">Total trades</div>
                  <div className="sp-metric-value mono">{preset.totalTradesCount}</div>
                </div>
                <div className="sp-metric-cell">
                  <div className="sp-metric-label">Win rate</div>
                  <div className="sp-metric-value mono" title={`${closed} closed trades`}>
                    {closed > 0 ? `${preset.winRatePct.toFixed(0)}%` : "—"}
                  </div>
                </div>
                <div className="sp-metric-cell">
                  <div className="sp-metric-label">Net P&amp;L</div>
                  <div className={`sp-metric-value mono ${pnl > 0 ? "sp-up" : pnl < 0 ? "sp-down" : ""}`}>
                    {signedRupee(pnl)}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="card desk-filter-bar">
        <span className="section-title">Live and past trades</span>
        <div className="desk-filter-bar__controls">
          <div className="desk-search">
            <Search size={14} className="desk-search__icon" />
            <input
              type="text"
              className="input desk-search__input"
              value={searchInput}
              onChange={(e) => {
                const v = e.target.value.toUpperCase();
                setSearchInput(v);
                setFilter((prev) => ({ ...prev, page: 0, underlyingCode: v.trim() || undefined }));
              }}
              placeholder="Filter underlying (NIFTY, BANKNIFTY)"
            />
            {searchInput && (
              <button
                type="button"
                className="desk-search__clear"
                aria-label="Clear filter"
                onClick={() => {
                  setSearchInput("");
                  setFilter((prev) => ({ ...prev, page: 0, underlyingCode: undefined }));
                }}
              >
                <X size={13} />
              </button>
            )}
          </div>
          <div className="toggle-chip-group">
            {(
              [
                { key: "", label: "ALL" },
                { key: "RUNNING", label: "RUNNING" },
                { key: "EXITED", label: "EXITED" },
              ] as const
            ).map((st) => (
              <button
                key={st.key || "ALL"}
                type="button"
                className={`toggle-chip ${(filter.tradeState ?? "") === st.key ? "toggle-chip--active" : ""}`}
                onClick={() =>
                  setFilter((prev) => ({
                    ...prev,
                    page: 0,
                    tradeState: (st.key || undefined) as TradeSearchFilter["tradeState"],
                  }))
                }
              >
                {st.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="card desk-table-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Contract</th>
              <th>Trader</th>
              <th>Session</th>
              <th>Lots (qty)</th>
              <th>Entry</th>
              <th>Stop</th>
              <th>Target</th>
              <th>Last / exit</th>
              <th>Net P&amp;L</th>
              <th>Broker</th>
              <th>State</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={13} className="text-muted">
                  Loading trades…
                </td>
              </tr>
            )}
            {!isLoading && trades.length === 0 && (
              <tr>
                <td colSpan={13} className="text-muted">
                  No trades yet. Open a session to let the traders find and manage trades.
                </td>
              </tr>
            )}
            {trades.map((t) => {
              const meta = TRADER_META[traderOf(t)];
              return (
                <tr key={t.id} className="desk-row" onClick={() => openCockpit(t.id)}>
                  <td className="mono">#{t.id}</td>
                  <td className="mono text-primary">
                    {t.underlyingCode} {t.strike} {t.optionType}
                    <div className="micro text-muted">{t.strategy ?? t.expiry}</div>
                  </td>
                  <td>
                    <span className={`badge ${meta.badgeClass}`}>{meta.tag}</span>
                  </td>
                  <td className="mono">
                    S#{t.sessionId} · <span className="micro">{t.sessionType}</span>
                  </td>
                  <td className="mono">
                    {t.lots} ({t.quantity})
                  </td>
                  <td className="mono">{formatRupee(t.entryAt)}</td>
                  <td className="mono text-red">{formatRupee(t.currentStop)}</td>
                  <td className="mono text-green">{formatRupee(t.currentTarget)}</td>
                  <td className="mono">{formatRupee(t.exitPrice ?? t.lastPrice)}</td>
                  <td className={`mono ${t.netPnl > 0 ? "text-green" : t.netPnl < 0 ? "text-red" : ""}`}>
                    {formatRupee(t.netPnl)} ({t.pnlPct >= 0 ? "+" : ""}
                    {t.pnlPct.toFixed(1)}%)
                  </td>
                  <td className="micro">
                    {t.routeThroughUpstox ? (
                      <span className="badge badge--green">
                        <Zap size={10} /> {t.brokerStatus}
                      </span>
                    ) : (
                      <span className="badge badge--slate">
                        <ShieldCheck size={10} /> SIMULATED
                      </span>
                    )}
                  </td>
                  <td>
                    <span className={t.tradeState === "RUNNING" ? "badge badge--green" : "badge badge--slate"}>
                      {t.tradeState === "RUNNING" ? "LIVE" : (t.exitReason ?? "EXITED")}
                    </span>
                    <div className="micro text-muted">{hms(t.exitedAt ?? t.enteredAt)}</div>
                  </td>
                  <td>
                    <ExternalLink size={13} className="text-muted" />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
        </>

      <SessionDialog
        isOpen={sessionDialogOpen}
        onClose={() => setSessionDialogOpen(false)}
        onCreate={(payload) => createSessionMutation.mutateAsync(payload)}
      />
    </div>
  );
};
