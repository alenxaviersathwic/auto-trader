import React, { useState } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";
import {
  Activity,
  CalendarClock,
  ChevronRight,
  Cpu,
  ExternalLink,
  Layers,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  X,
  Zap,
} from "lucide-react";
import { useTradeSearch, useTraderPresets } from "../hooks/useTrades";
import { ActiveTrade, TradeSearchFilter, TraderPreset } from "../types/trades.types";
import { SideSheetMode, TraderSideSheet } from "../components/TraderSideSheet";
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

function presetSymbolClass(color: string): string {
  if (color === "cyan") return "sp-symbol sp-symbol--commodity";
  if (color === "amber") return "sp-symbol sp-symbol--index";
  return "badge badge--green mono";
}

const FALLBACK_PRESETS: TraderPreset[] = [
  {
    code: "FIB_GOLDEN_TRADER",
    name: "Fibonacci Golden-Pocket Specialist",
    shortLabel: "FIB 0.618 → 1.618",
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
    shortLabel: "STEP-WAVE 100→120→150",
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
    shortLabel: "VWAP + OI FLOW",
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
  const navigate = useNavigate({ from: "/trades" });
  const search = useSearch({ from: "/trades" }) as {
    sheet?: SideSheetMode;
    trader?: string;
    tradeId?: number;
  };

  const [selectedPreset, setSelectedPreset] = useState<string>("");
  const [searchInput, setSearchInput] = useState<string>("");

  const sheetOpen = Boolean(search.sheet);
  const sheetMode: SideSheetMode = search.sheet ?? "SUGGESTIONS";
  const sheetPresetCode = search.trader ?? "FIB_GOLDEN_TRADER";
  const inspectedTradeId = search.tradeId ?? null;

  const [filter, setFilter] = useState<TradeSearchFilter>({
    page: 0,
    limit: 25,
    sortBy: "createdAt",
    sortDir: "desc",
    status: "ACTIVE",
  });

  const { data: presetsData } = useTraderPresets();
  const presets = presetsData && presetsData.length > 0 ? presetsData : FALLBACK_PRESETS;
  const activeSheetPreset =
    presets.find((p) => p.code === sheetPresetCode) ?? presets[0] ?? FALLBACK_PRESETS[0];

  const updateSheetSearch = (patch: {
    sheet?: SideSheetMode;
    trader?: string;
    tradeId?: number;
  }) => {
    navigate({
      search: (prev: Record<string, unknown>) => ({
        ...prev,
        ...patch,
      }),
    });
  };

  const openSuggestionsSheet = (code: string) => {
    updateSheetSearch({ sheet: "SUGGESTIONS", trader: code, tradeId: undefined });
  };

  const openInsertTradeSheet = (code?: string) => {
    updateSheetSearch({
      sheet: "INSERT_TRADE",
      trader: code || sheetPresetCode,
      tradeId: undefined,
    });
  };

  const openTradeInspectSheet = (trade: ActiveTrade) => {
    const tCode = trade.marketTelemetry?.traderCode || trade.traderProfile;
    const trader = presets.some((p) => p.code === tCode) ? tCode : sheetPresetCode;
    updateSheetSearch({ sheet: "TRADE_INSPECT", trader, tradeId: trade.id });
  };

  const closeSheet = () => {
    updateSheetSearch({ sheet: undefined, trader: undefined, tradeId: undefined });
  };

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
      {/* Minimal High-Density Command & Summary Strip (matching StrategiesPage / SessionsPage) */}
      <div className="sp-toolbar">
        <div className="sp-toolbar-left">
          <div className="sp-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={selectedPreset === ""}
              className={`sp-tab ${selectedPreset === "" ? "sp-tab--active" : ""}`}
              onClick={() => setSelectedPreset("")}
            >
              <Cpu size={13} />
              <span>All 3 Preset Traders</span>
              <span className="sp-tab-count mono">{allTrades.length}</span>
            </button>
            {presets.map((p) => (
              <button
                key={p.code}
                type="button"
                role="tab"
                aria-selected={selectedPreset === p.code}
                className={`sp-tab ${selectedPreset === p.code ? "sp-tab--active" : ""}`}
                onClick={() => setSelectedPreset((prev) => (prev === p.code ? "" : p.code))}
              >
                <span>{p.shortLabel}</span>
                {p.activeTradesCount > 0 && (
                  <span className="sp-tab-live mono">{p.activeTradesCount} LIVE</span>
                )}
              </button>
            ))}
          </div>

          <div className="sp-summary-strip">
            <div className="sp-stat-pill" title="Active 1-second Trader loops currently running">
              <span className={`sp-status-dot ${runningCount > 0 ? "sp-status-dot--live" : ""}`} />
              <span className="sp-stat-label">Live 1s Loops</span>
              <span className="sp-stat-val mono sp-up">{runningCount}</span>
            </div>

            <div className="sp-stat-pill" title="Capital deployed in open positions">
              <span className="sp-stat-label">Active Capital</span>
              <span className="sp-stat-val mono">{formatCompactRupee(totalCapitalUsed)}</span>
            </div>

            <div className="sp-stat-pill" title="Combined Net P&L across trader positions">
              <span className="sp-stat-label">Net P&amp;L</span>
              <span
                className={`sp-stat-val mono ${
                  totalNetPnl > 0 ? "sp-up" : totalNetPnl < 0 ? "sp-down" : ""
                }`}
              >
                {signedRupee(totalNetPnl)}
              </span>
            </div>
          </div>
        </div>

        <div className="sp-actions">
          <button
            type="button"
            className="sp-btn sp-btn--secondary"
            onClick={() => openSuggestionsSheet(selectedPreset || "FIB_GOLDEN_TRADER")}
          >
            <Sparkles size={13} /> Trader Suggestions
          </button>
          <button
            type="button"
            className="sp-btn sp-btn--run"
            onClick={() => openInsertTradeSheet(selectedPreset || "FIB_GOLDEN_TRADER")}
          >
            <Plus size={14} strokeWidth={2.5} /> Insert Trade (Fib + OA)
          </button>
          <button
            type="button"
            className="sp-btn"
            onClick={() => navigate({ to: "/sessions" })}
          >
            <CalendarClock size={13} /> Sessions
          </button>
        </div>
      </div>

      {/* 3 Preset Institutional Traders Grid (clicking opens Right-Side Bar with Suggestions & Fib/OA) */}
      <div className="sp-grid">
        {presets.map((preset) => {
          const isSelected =
            selectedPreset === preset.code ||
            (sheetOpen && sheetPresetCode === preset.code);
          const isRunning = preset.activeTradesCount > 0;
          const pnl = Number(preset.netPnl || 0);
          const tone = pnl > 0 ? "sp-card--bull" : pnl < 0 ? "sp-card--bear" : "";

          return (
            <div
              key={preset.code}
              className={`sp-card ${tone} ${isRunning ? "sp-card--iterating" : ""} ${
                isSelected ? "sp-card--selected" : ""
              }`}
              onClick={() => openSuggestionsSheet(preset.code)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  openSuggestionsSheet(preset.code);
                }
              }}
            >
              <div className="sp-card-top">
                <div className="sp-card-title-group">
                  <div className="sp-symbol-row">
                    <span className={presetSymbolClass(preset.badgeColor)}>
                      {preset.shortLabel}
                    </span>
                    <h2 className="sp-name">{preset.name}</h2>
                  </div>
                </div>

                <div className="sp-card-badges" onClick={(e) => e.stopPropagation()}>
                  {isRunning ? (
                    <span className="badge badge--green">
                      <Activity size={11} /> {preset.activeTradesCount} LIVE
                    </span>
                  ) : (
                    <span className="badge badge--slate">READY</span>
                  )}
                  <button
                    type="button"
                    className="sp-card-action sp-card-action--run"
                    onClick={() => openInsertTradeSheet(preset.code)}
                    title={`Insert trade with ${preset.name} Fib + OA Analyzer`}
                  >
                    <Plus size={11} /> Fib + OA
                  </button>
                </div>
              </div>

              {/* Trader Methodology & 1s Brain Breakdown */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px",
                  fontSize: "0.73rem",
                  color: "var(--text-secondary)",
                  lineHeight: 1.45,
                }}
              >
                <div>{preset.methodology}</div>
                <div
                  style={{
                    padding: "8px 10px",
                    background: "var(--bg-panel)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-sm)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "4px",
                  }}
                >
                  <div>
                    <strong className="text-heading">Entry Discovery:</strong> {preset.entryLogic}
                  </div>
                  <div>
                    <strong className="text-green">1s Step-Wave Brain:</strong> {preset.trailLogic}
                  </div>
                </div>
              </div>

              {/* 4-Column Compact Telemetry Grid inside Card */}
              <div className="sp-metrics">
                <div className="sp-metric-cell">
                  <div className="sp-metric-label">1s Loops</div>
                  <div className="sp-metric-value">
                    {isRunning ? (
                      <span className="sp-state-pill sp-state-pill--running">
                        <span className="sp-pulse-dot" /> {preset.activeTradesCount} LIVE
                      </span>
                    ) : (
                      <span className="sp-state-pill sp-state-pill--idle">0 OPEN</span>
                    )}
                  </div>
                </div>

                <div className="sp-metric-cell">
                  <div className="sp-metric-label">Total Trades</div>
                  <div className="sp-metric-value mono">{preset.totalTradesCount}</div>
                </div>

                <div className="sp-metric-cell">
                  <div className="sp-metric-label">Win Rate</div>
                  <div className="sp-metric-value mono">{preset.winRatePct.toFixed(0)}%</div>
                </div>

                <div className="sp-metric-cell">
                  <div className="sp-metric-label">Realized P&amp;L</div>
                  <div
                    className={`sp-metric-value mono ${
                      pnl > 0 ? "sp-up" : pnl < 0 ? "sp-down" : ""
                    }`}
                  >
                    {signedRupee(pnl)}
                  </div>
                </div>
              </div>

              {/* Card Footer with Strategy Tags */}
              <div className="sp-card-foot">
                <div className="sp-foot-left" style={{ flexWrap: "wrap" }}>
                  {preset.strategies.map((st) => (
                    <span key={st} className="sp-session-tag mono">
                      {st}
                    </span>
                  ))}
                </div>
                <span className="sp-inspect-link">
                  <span>Suggestions &amp; Fib/OA</span>
                  <ChevronRight size={13} />
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Filter & Search Bar for Positions Table */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "12px",
          flexWrap: "wrap",
          background: "var(--bg-card)",
          padding: "10px 14px",
          borderRadius: "var(--radius-md)",
          border: "1px solid var(--border-subtle)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          <span className="section-title" style={{ margin: 0 }}>
            Live &amp; Historical Trader Positions
          </span>
          {selectedPreset && (
            <span className="badge badge--blue">
              Filtered: {selectedPreset}{" "}
              <button
                type="button"
                onClick={() => setSelectedPreset("")}
                style={{ marginLeft: 6, cursor: "pointer" }}
              >
                ×
              </button>
            </span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
          <div style={{ position: "relative", minWidth: "220px" }}>
            <Search
              size={14}
              color="var(--text-muted)"
              style={{
                position: "absolute",
                left: "10px",
                top: "50%",
                transform: "translateY(-50%)",
              }}
            />
            <input
              type="text"
              className="input"
              value={searchInput}
              onChange={(e) => {
                const v = e.target.value.toUpperCase();
                setSearchInput(v);
                setFilter((prev) => ({
                  ...prev,
                  page: 0,
                  underlyingCode: v.trim() || undefined,
                }));
              }}
              placeholder="Filter underlying (NIFTY, BANKNIFTY)..."
              style={{ paddingLeft: "30px", height: "32px", fontSize: "0.78rem" }}
            />
            {searchInput && (
              <button
                type="button"
                onClick={() => {
                  setSearchInput("");
                  setFilter((prev) => ({ ...prev, page: 0, underlyingCode: undefined }));
                }}
                style={{
                  position: "absolute",
                  right: "8px",
                  top: "50%",
                  transform: "translateY(-50%)",
                }}
              >
                <X size={13} />
              </button>
            )}
          </div>

          <div className="toggle-chip-group">
            {(
              [
                { key: "", label: "ALL STATES" },
                { key: "RUNNING", label: "RUNNING (LIVE 1s)" },
                { key: "EXITED", label: "EXITED" },
              ] as const
            ).map((st) => {
              const active = (filter.tradeState ?? "") === st.key;
              return (
                <button
                  key={st.key || "ALL"}
                  type="button"
                  className={`toggle-chip ${active ? "toggle-chip--active" : ""}`}
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
              );
            })}
          </div>
        </div>
      </div>

      {/* Positions Table */}
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
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
                  onClick={() => openTradeInspectSheet(t)}
                  style={{
                    cursor: "pointer",
                    background:
                      sheetOpen && sheetMode === "TRADE_INSPECT" && inspectedTradeId === t.id
                        ? "rgba(56, 126, 209, 0.1)"
                        : undefined,
                  }}
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
                    <div style={{ display: "inline-flex", gap: "6px" }}>
                      <button
                        type="button"
                        className="btn btn--ghost"
                        onClick={() => openTradeInspectSheet(t)}
                        title="Open right-side bar with live Fib + OA charts & Trader suggestions"
                      >
                        <Layers size={13} />
                        <span>Sidebar</span>
                      </button>
                      <button
                        type="button"
                        className="btn btn--ghost"
                        onClick={() =>
                          navigate({ to: "/trades/$tradeId", params: { tradeId: String(t.id) } })
                        }
                        title="Open full-page Trade Cockpit"
                      >
                        <ExternalLink size={13} />
                        <span>Cockpit</span>
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Right-Side Bar (Suggestions, Insert Trade with Fib + OA, & Live Trade Inspector) */}
      {sheetOpen && (
        <TraderSideSheet
          mode={sheetMode}
          preset={activeSheetPreset}
          allPresets={presets}
          selectedTradeId={inspectedTradeId}
          onChangeMode={(m) => updateSheetSearch({ sheet: m })}
          onSelectPreset={(code) => updateSheetSearch({ trader: code })}
          onSelectTrade={(tid) => updateSheetSearch({ tradeId: tid })}
          onClose={closeSheet}
        />
      )}
    </div>
  );
};

