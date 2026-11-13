import React, { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Activity, Cpu, ExternalLink, Search, ShieldCheck, Zap } from "lucide-react";
import { useTradeSearch, useTraderPresets } from "../hooks/useTrades";
import { ActiveTrade, TradeSearchFilter, TraderPreset } from "../types/trades.types";
import { formatRupee } from "../../opportunities/components/formatters";

const hms = (iso: string | null): string =>
  iso
    ? new Date(iso).toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : "—";

function stateBadge(state: ActiveTrade["tradeState"]): string {
  return state === "RUNNING" ? "badge badge--green" : "badge badge--slate";
}

function profileBadge(profile: ActiveTrade["traderProfile"], traderCode?: string): string {
  const code = traderCode || profile;
  if (code === "FIB_GOLDEN_TRADER") return "badge badge--cyan";
  if (code === "ORB_WAVE_TRADER") return "badge badge--green";
  if (code === "FLOW_VWAP_TRADER") return "badge badge--amber";
  return profile === "HIGH_CONVICTION" ? "badge badge--cyan" : "badge badge--amber";
}

function presetBadgeClass(color: string): string {
  if (color === "cyan") return "badge badge--cyan";
  if (color === "green") return "badge badge--green";
  if (color === "amber") return "badge badge--amber";
  return "badge badge--blue";
}

const FALLBACK_PRESETS: TraderPreset[] = [
  {
    code: "FIB_GOLDEN_TRADER",
    name: "Fibonacci Golden-Pocket Specialist",
    shortLabel: "Fib Golden 0.618",
    badgeColor: "cyan",
    methodology:
      "Discovers institutional option setups on 0.50–0.618 Fibonacci pullbacks inside a directional intraday trend with supportive option-chain gamma walls.",
    entryLogic:
      "Enters when option premium reclaims the 0.618 Golden Pocket with rising 1m volume (>1.3x average) and bullish candle body confirmation.",
    trailLogic:
      "1-Second Fibonacci Wave Engine: projects 1.272 and 1.618 extension targets. When Target is 100 and wave projects 150, locks SL at 75 and steps Target to 120 → 150.",
    strategies: ["SWING_PULLBACK_CONTINUATION", "GAMMA_WALL_BOUNCE", "EMA_CROSSOVER_RIDE"],
    activeTradesCount: 0,
    totalTradesCount: 0,
    winRatePct: 0,
    netPnl: 0,
  },
  {
    code: "ORB_WAVE_TRADER",
    name: "ORB & Momentum Wave Runner",
    shortLabel: "ORB Wave Runner",
    badgeColor: "green",
    methodology:
      "Captures Opening Range Breakouts (ORB), volatility compression squeezes, and high-velocity directional expansion waves.",
    entryLogic:
      "Enters on 15m/5m Opening Range high-volume breakout with expanding ATR and strong option call/put buildup.",
    trailLogic:
      "1-Second Step-Wave Runner: when planned Target is 100 and live momentum projects 150, locks SL at 75 and steps Target 100 → 120 → 150 while riding higher lows.",
    strategies: ["OPENING_RANGE_BREAKOUT", "VOLATILITY_SQUEEZE_EXPANSION", "EXPIRY_0DTE_GAMMA_SNAP"],
    activeTradesCount: 0,
    totalTradesCount: 0,
    winRatePct: 0,
    netPnl: 0,
  },
  {
    code: "FLOW_VWAP_TRADER",
    name: "Institutional VWAP & OI Flow Trader",
    shortLabel: "VWAP + OI Flow",
    badgeColor: "amber",
    methodology:
      "Tracks institutional option-chain Open Interest (OI) unwinding, PCR shifts, and VWAP reclaim/rejection structure.",
    entryLogic:
      "Enters on institutional short-covering / writer-trap signals confirmed by VWAP hold and order-flow imbalance.",
    trailLogic:
      "1-Second Institutional Step-Guard: ratchets SL at 50% (+30% locked) and 80% (+50% locked), and steps Target higher when volume ratio ≥ 1.35x.",
    strategies: ["OI_UNWINDING_TRAP", "VWAP_RECLAIM_MOMENTUM", "PCR_EXTREME_REVERSAL"],
    activeTradesCount: 0,
    totalTradesCount: 0,
    winRatePct: 0,
    netPnl: 0,
  },
];

export const TradesPage: React.FC = () => {
  const navigate = useNavigate();
  const [selectedPreset, setSelectedPreset] = useState<string>("");
  const [filter, setFilter] = useState<TradeSearchFilter>({
    page: 0,
    limit: 25,
    sortBy: "createdAt",
    sortDir: "desc",
    status: "ACTIVE",
  });

  const { data: presetsData } = useTraderPresets();
  const presets = presetsData && presetsData.length > 0 ? presetsData : FALLBACK_PRESETS;

  const { data, isLoading } = useTradeSearch(filter);
  const allTrades = data?.list ?? [];
  const trades = selectedPreset
    ? allTrades.filter(
        (t) =>
          t.marketTelemetry?.traderCode === selectedPreset || t.traderProfile === selectedPreset,
      )
    : allTrades;

  const runningCount = allTrades.filter((t) => t.tradeState === "RUNNING").length;
  const totalNetPnl = allTrades.reduce((acc, t) => acc + Number(t.netPnl || 0), 0);
  const totalCapitalUsed = allTrades
    .filter((t) => t.tradeState === "RUNNING")
    .reduce((acc, t) => acc + Number(t.capitalUsed || 0), 0);

  return (
    <div className="sp-page">
      {/* Top Toolbar matching StrategiesPage & SessionsPage */}
      <header className="sp-toolbar">
        <div className="sp-toolbar__left">
          <div className="sp-brand">
            <div className="sp-brand__icon">
              <Cpu size={16} />
            </div>
            <div>
              <h1 className="sp-brand__title">Specialist Traders &amp; Live Execution Desk</h1>
              <span className="sp-brand__sub">
                3 Preset Institutional Traders · 1-Second Re-Analysis, SL Ratchet &amp; Target Wave Step-Up
              </span>
            </div>
          </div>

          <div className="sp-stats-inline">
            <div className="sp-stat-chip">
              <span className="sp-stat-chip__dot sp-stat-chip__dot--green" />
              <span className="sp-stat-chip__val">{runningCount}</span>
              <span className="sp-stat-chip__lbl">Live Running</span>
            </div>
            <div className="sp-stat-chip">
              <span className="sp-stat-chip__val">{formatRupee(totalCapitalUsed)}</span>
              <span className="sp-stat-chip__lbl">Active Capital</span>
            </div>
            <div className="sp-stat-chip">
              <span
                className="sp-stat-chip__val"
                style={{
                  color:
                    totalNetPnl > 0
                      ? "var(--bullish-green)"
                      : totalNetPnl < 0
                        ? "var(--bearish-red)"
                        : "var(--text-primary)",
                }}
              >
                {formatRupee(totalNetPnl)}
              </span>
              <span className="sp-stat-chip__lbl">Net P&amp;L</span>
            </div>
          </div>
        </div>

        <div className="sp-toolbar__right">
          <div className="sp-search">
            <Search size={13} className="sp-search__icon" />
            <input
              type="text"
              className="sp-search__input"
              placeholder="Filter underlying (NIFTY, BANKNIFTY)..."
              value={filter.underlyingCode ?? ""}
              onChange={(e) =>
                setFilter((prev) => ({
                  ...prev,
                  page: 0,
                  underlyingCode: e.target.value ? e.target.value.toUpperCase() : undefined,
                }))
              }
            />
          </div>

          <select
            className="select"
            style={{ width: 170, height: 32, fontSize: "0.75rem" }}
            value={filter.tradeState ?? ""}
            onChange={(e) =>
              setFilter((prev) => ({
                ...prev,
                page: 0,
                tradeState: (e.target.value || undefined) as TradeSearchFilter["tradeState"],
              }))
            }
          >
            <option value="">All Trade States</option>
            <option value="RUNNING">RUNNING (Live 1s Loop)</option>
            <option value="EXITED">EXITED (Closed)</option>
          </select>
        </div>
      </header>

      <div className="sp-body">
        {/* 3 Preset Institutional Traders Section */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "var(--space-2)",
          }}
        >
          <span className="section-title" style={{ margin: 0 }}>
            Preset Institutional Traders (Select to Filter Positions)
          </span>
          {selectedPreset && (
            <button
              type="button"
              className="btn btn--ghost"
              style={{ padding: "2px 10px", fontSize: "0.72rem" }}
              onClick={() => setSelectedPreset("")}
            >
              Show All 3 Traders
            </button>
          )}
        </div>

        <div className="sp-grid" style={{ marginBottom: "var(--space-5)" }}>
          {presets.map((preset) => {
            const isSelected = selectedPreset === preset.code;
            const pnlColor =
              preset.netPnl > 0
                ? "var(--bullish-green)"
                : preset.netPnl < 0
                  ? "var(--bearish-red)"
                  : "var(--text-primary)";
            return (
              <div
                key={preset.code}
                className={`sp-card ${preset.activeTradesCount > 0 ? "sp-card--active" : ""}`}
                style={{
                  cursor: "pointer",
                  borderColor: isSelected ? "var(--accent-blue)" : undefined,
                }}
                onClick={() =>
                  setSelectedPreset((prev) => (prev === preset.code ? "" : preset.code))
                }
              >
                <div className="sp-card__accent" />
                <div className="sp-card__head">
                  <div className="sp-card__identity">
                    <div className="sp-card__title-row">
                      <h3 className="sp-card__name">{preset.name}</h3>
                      <span className={presetBadgeClass(preset.badgeColor)}>
                        {preset.shortLabel}
                      </span>
                    </div>
                    <span className="sp-card__code">{preset.code}</span>
                  </div>
                  {preset.activeTradesCount > 0 ? (
                    <span className="badge badge--green">
                      <Activity size={11} /> {preset.activeTradesCount} LIVE
                    </span>
                  ) : (
                    <span className="badge badge--slate">STANDBY</span>
                  )}
                </div>

                <p className="sp-card__desc" style={{ WebkitLineClamp: 3 }}>
                  {preset.methodology}
                </p>

                <div
                  style={{
                    padding: "var(--space-2) var(--space-4)",
                    fontSize: "0.72rem",
                    color: "var(--text-secondary)",
                    borderTop: "1px solid var(--border-subtle)",
                    background: "rgba(15, 23, 42, 0.35)",
                  }}
                >
                  <div style={{ marginBottom: 4 }}>
                    <strong className="text-primary">Discovery:</strong> {preset.entryLogic}
                  </div>
                  <div>
                    <strong className="text-green">1s Re-Analysis Brain:</strong> {preset.trailLogic}
                  </div>
                </div>

                <div className="sp-card__metrics">
                  <div className="sp-metric">
                    <span className="sp-metric__lbl">Active Loops</span>
                    <span className="sp-metric__val text-green">{preset.activeTradesCount}</span>
                  </div>
                  <div className="sp-metric">
                    <span className="sp-metric__lbl">Closed Trades</span>
                    <span className="sp-metric__val">{preset.totalTradesCount}</span>
                  </div>
                  <div className="sp-metric">
                    <span className="sp-metric__lbl">Win Rate</span>
                    <span className="sp-metric__val">{preset.winRatePct.toFixed(0)}%</span>
                  </div>
                  <div className="sp-metric">
                    <span className="sp-metric__lbl">Realized P&amp;L</span>
                    <span className="sp-metric__val" style={{ color: pnlColor }}>
                      {formatRupee(preset.netPnl)}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Active & Historical Trades Table */}
        <div className="sp-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Contract</th>
                <th>Assigned Trader</th>
                <th>Session</th>
                <th>Lots (Qty)</th>
                <th>Entry At</th>
                <th>Active SL</th>
                <th>Active Target</th>
                <th>Projected Wave</th>
                <th>Last / Exit</th>
                <th>Net P&amp;L</th>
                <th>Broker</th>
                <th>State</th>
                <th style={{ textAlign: "right" }}>Live Graph</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={14} className="text-muted">
                    Loading trader positions…
                  </td>
                </tr>
              )}
              {!isLoading && trades.length === 0 && (
                <tr>
                  <td colSpan={14} className="text-muted">
                    No active trades yet. Start a Session in Manual, Semi-Auto, or Full-Auto mode to let your Preset Traders discover and execute setups.
                  </td>
                </tr>
              )}
              {trades.map((t) => {
                const pnlClass = t.netPnl > 0 ? "text-green" : t.netPnl < 0 ? "text-red" : "";
                const traderCode = t.marketTelemetry?.traderCode || t.traderProfile;
                const traderLabel =
                  t.marketTelemetry?.traderName ||
                  (traderCode === "FIB_GOLDEN_TRADER"
                    ? "Fib Golden 0.618"
                    : traderCode === "ORB_WAVE_TRADER"
                      ? "ORB Wave Runner"
                      : traderCode === "FLOW_VWAP_TRADER"
                        ? "VWAP + OI Flow"
                        : t.traderProfile);
                const projected = t.marketTelemetry?.projectedTarget;
                return (
                  <tr
                    key={t.id}
                    onClick={() =>
                      navigate({ to: "/trades/$tradeId", params: { tradeId: String(t.id) } })
                    }
                    style={{ cursor: "pointer" }}
                  >
                    <td className="mono">#{t.id}</td>
                    <td className="mono text-primary">
                      {t.underlyingCode} {t.strike} {t.optionType}
                      <div className="micro text-muted">{t.strategy ?? t.expiry}</div>
                    </td>
                    <td>
                      <span className={profileBadge(t.traderProfile, traderCode)}>
                        {traderLabel}
                      </span>{" "}
                      <span className="mono micro">{t.winRatePct.toFixed(0)}%</span>
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
                    <td className="mono text-blue">
                      {projected && projected > t.currentTarget
                        ? formatRupee(projected)
                        : formatRupee(t.currentTarget)}
                    </td>
                    <td className="mono">{formatRupee(t.exitPrice ?? t.lastPrice)}</td>
                    <td className={`mono ${pnlClass}`}>
                      {formatRupee(t.netPnl)} ({t.pnlPct >= 0 ? "+" : ""}
                      {t.pnlPct.toFixed(1)}%)
                    </td>
                    <td className="micro">
                      {t.routeThroughUpstox ? (
                        <span className="badge badge--green">
                          <Zap size={10} /> Upstox ({t.brokerStatus})
                        </span>
                      ) : (
                        <span className="badge badge--slate">
                          <ShieldCheck size={10} /> Simulated
                        </span>
                      )}
                    </td>
                    <td>
                      <span className={stateBadge(t.tradeState)}>
                        {t.tradeState === "RUNNING" ? (
                          <>
                            <Activity size={11} /> LIVE 1s
                          </>
                        ) : (
                          t.exitReason ?? "EXITED"
                        )}
                      </span>
                      <div className="micro text-muted">{hms(t.exitedAt ?? t.enteredAt)}</div>
                    </td>
                    <td style={{ textAlign: "right" }} onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        className="btn btn--ghost"
                        onClick={() =>
                          navigate({ to: "/trades/$tradeId", params: { tradeId: String(t.id) } })
                        }
                      >
                        <ExternalLink size={13} />
                        <span>Live Graph</span>
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

