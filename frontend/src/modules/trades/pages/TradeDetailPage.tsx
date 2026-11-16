import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "@tanstack/react-router";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Cpu,
  ShieldCheck,
  Sliders,
  Square,
  Zap,
} from "lucide-react";
import { useAdjustTrade, useExitTrade, useTradeDetail } from "../hooks/useTrades";
import { useTradeStream } from "../hooks/useTradeStream";
import { TradeLiveLadder } from "../components/TradeLiveLadder";
import { TradePremiumChart } from "../components/TradePremiumChart";
import { TradeDecisionLog } from "../components/TradeDecisionLog";
import { FibRetracementChart, OptionChainOAChart } from "../components/FibAndOACharts";
import { formatExpiry, formatRupee } from "../../opportunities/components/formatters";

const hms = (iso: string | null): string =>
  iso
    ? new Date(iso).toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour12: false,
      })
    : "—";

const TRADER_DESC: Record<string, { name: string; tag: string; brain: string }> = {
  FIB_GOLDEN_TRADER: {
    name: "Fibonacci Golden-Pocket Specialist",
    tag: "FIB 0.618 → 1.618 EXT",
    brain:
      "1-Second Fibonacci Wave Brain — Trails SL along 1.0 → 1.272 → 1.618 extensions and steps Target (e.g. 100 → 120 → 150) while locking SL (75 → 100).",
  },
  ORB_WAVE_TRADER: {
    name: "ORB & Momentum Wave Runner",
    tag: "STEP-WAVE 100→120→150",
    brain:
      "1-Second Step-Wave Brain — When planned Target is 100 and wave projects 150, locks SL at 75 and steps Target 100 → 120 → 150.",
  },
  FLOW_VWAP_TRADER: {
    name: "Institutional VWAP & OI Flow Trader",
    tag: "VWAP + OI FLOW",
    brain:
      "1-Second Institutional Flow Brain — Ratchets SL at 50% (+30% locked) and 80% (+50% locked), stepping Target up on ≥ 1.35x volume surges.",
  },
};

export const TradeDetailPage: React.FC = () => {
  const { tradeId } = useParams({ strict: false }) as { tradeId: string };
  const navigate = useNavigate();
  const id = Number(tradeId);

  const { data: initialTrade, isLoading } = useTradeDetail(id);
  const stream = useTradeStream(id, !!initialTrade && initialTrade.tradeState === "RUNNING");
  const adjustMutation = useAdjustTrade(id);
  const exitMutation = useExitTrade(id);

  const trade = stream.trade ?? initialTrade;

  const [editStop, setEditStop] = useState<string>("");
  const [editTarget, setEditTarget] = useState<string>("");
  const [feedback, setFeedback] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    if (trade) {
      setEditStop((prev) => (prev === "" ? String(trade.currentStop) : prev));
      setEditTarget((prev) => (prev === "" ? String(trade.currentTarget) : prev));
    }
  }, [trade]);

  if (isLoading || !trade) {
    return (
      <div className="sd-page">
        <div className="sd-loading-box">Loading Trader Cockpit #{id}…</div>
      </div>
    );
  }

  const isRunning = trade.tradeState === "RUNNING";
  const pnlClass = trade.netPnl > 0 ? "text-green" : trade.netPnl < 0 ? "text-red" : "";
  const progressPct = trade.marketTelemetry.progressPct ?? 0;
  const traderCode = trade.marketTelemetry.traderCode || trade.traderProfile;
  const traderMeta = TRADER_DESC[traderCode] ?? {
    name: trade.marketTelemetry.traderName || trade.traderProfile,
    tag: trade.traderProfile,
    brain:
      "1-Second Re-Analysis Loop — Continuously evaluates LTP, 1m candle structure, volume ratio & projected wave ceiling to trail SL & Target.",
  };
  const projectedTarget = trade.marketTelemetry.projectedTarget ?? trade.currentTarget;
  const fibLevels = trade.marketTelemetry.fibLevels;

  const handleAdjust = (e: React.FormEvent) => {
    e.preventDefault();
    const cs = Number(editStop);
    const ct = Number(editTarget);
    if (!cs || !ct || cs <= 0 || ct <= 0) return;
    adjustMutation.mutate(
      { currentStop: cs, currentTarget: ct, reason: "Manual Trader cockpit adjustment" },
      {
        onSuccess: (updated) => {
          setEditStop(String(updated.currentStop));
          setEditTarget(String(updated.currentTarget));
          setFeedback({
            type: "ok",
            text: `Updated SL to ₹${updated.currentStop} and Target to ₹${updated.currentTarget}`,
          });
        },
        onError: (err) => {
          setFeedback({
            type: "err",
            text: err instanceof Error ? err.message : "Failed to update levels",
          });
        },
      },
    );
  };

  const handleSquareOff = () => {
    if (
      !window.confirm(
        `Square off ${trade.underlyingCode} ${trade.strike} ${trade.optionType} (${trade.quantity} qty) at current market price?`,
      )
    ) {
      return;
    }
    exitMutation.mutate(
      { reason: "MANUAL_EXIT" },
      {
        onSuccess: (closed) => {
          setFeedback({
            type: "ok",
            text: `Position squared off at ₹${closed.exitPrice ?? closed.lastPrice} · Net P&L: ${formatRupee(closed.netPnl)}`,
          });
        },
        onError: (err) => {
          setFeedback({
            type: "err",
            text: err instanceof Error ? err.message : "Square-off failed",
          });
        },
      },
    );
  };

  return (
    <div className="sd-page">
      {/* 1. Compact Top Bar (.sd-topbar) */}
      <div className="sd-topbar">
        <div className="sd-topbar-left">
          <button
            type="button"
            className="sd-ctrl-btn"
            onClick={() =>
              navigate({ to: "/sessions/$id", params: { id: String(trade.sessionId) } })
            }
          >
            <ArrowLeft size={13} />
            <span>Session #{trade.sessionId}</span>
          </button>
          <button
            type="button"
            className="sd-ctrl-btn"
            onClick={() => navigate({ to: "/trades" })}
          >
            <Cpu size={13} />
            <span>Traders Desk</span>
          </button>
          <span className="sd-topbar-sep" />
          <span className="sd-code-tag">{traderMeta.tag}</span>
          <span className="sd-ver-tag">{trade.sessionType}</span>
          <span className={isRunning ? "sd-status-pill is-green" : "sd-status-pill"}>
            <span className="sd-status-dot" />
            {isRunning
              ? "TRADER PILOT LIVE (1s LOOP)"
              : `EXITED (${trade.exitReason ?? "CLOSED"})`}
          </span>
        </div>

        <div className="sd-topbar-right">
          {trade.routeThroughUpstox ? (
            <span className="sd-status-pill is-green">
              <Zap size={11} />
              UPSTOX LIVE ({trade.brokerStatus})
            </span>
          ) : (
            <span className="sd-status-pill">
              <ShieldCheck size={11} />
              SIMULATED
            </span>
          )}
          {isRunning && (
            <button
              type="button"
              className="sd-ctrl-btn sd-ctrl-btn--danger"
              onClick={handleSquareOff}
              disabled={exitMutation.isPending}
            >
              <Square size={12} />
              <span>{exitMutation.isPending ? "Squaring Off…" : "Square Off Now"}</span>
            </button>
          )}
        </div>
      </div>

      {/* 2. Unified Trade Summary & 6-Column Telemetry Card (.sd-summary-card) */}
      <div className="sd-summary-card">
        <div className="sd-summary-head">
          <div className="sd-summary-title-block">
            <h1 className="sd-title">
              Trade #{trade.id} · {trade.underlyingCode} {trade.strike} {trade.optionType} ·{" "}
              <span className="text-blue">{traderMeta.name}</span>
            </h1>
            <p className="sd-desc">
              {formatExpiry(trade.expiry)} · Strategy: <strong>{trade.strategy ?? "Tactical"}</strong>{" "}
              · Win Prob: <strong>{trade.winRatePct.toFixed(0)}%</strong> · Entered at{" "}
              <strong>{hms(trade.enteredAt)} IST</strong>
              {trade.exitedAt ? ` · Exited at ${hms(trade.exitedAt)} IST` : ""} — {traderMeta.brain}
            </p>
          </div>

          <div className="sd-summary-badges">
            {fibLevels && (
              <>
                <span className="sd-tag mono">0.618: ₹{fibLevels.fib618.toFixed(1)}</span>
                <span className="sd-tag sd-tag--green mono">
                  1.0 TGT: ₹{fibLevels.fib100.toFixed(1)}
                </span>
                <span className="sd-tag sd-tag--cyan mono">
                  1.272 EXT: ₹{fibLevels.fib1272.toFixed(1)}
                </span>
                <span className="sd-tag sd-tag--amber mono">
                  1.618 EXT: ₹{fibLevels.fib1618.toFixed(1)}
                </span>
              </>
            )}
          </div>
        </div>

        {/* 6-Column Telemetry Strip */}
        <div className="sd-telemetry-strip">
          <div className="sd-telemetry-cell">
            <span className="sd-telemetry-label">Entry → Live LTP</span>
            <span className="sd-telemetry-val">
              {formatRupee(trade.entryAt)} → {formatRupee(trade.exitPrice ?? trade.lastPrice)}
            </span>
            <span className="sd-telemetry-sub">
              {trade.lots} lot(s) × {trade.lotUnits} = {trade.quantity} qty (
              {formatRupee(trade.capitalUsed)})
            </span>
          </div>

          <div className="sd-telemetry-cell">
            <span className="sd-telemetry-label">Net P&amp;L (After Charges)</span>
            <span className={`sd-telemetry-val ${pnlClass}`}>
              {formatRupee(trade.netPnl)} ({trade.pnlPct >= 0 ? "+" : ""}
              {trade.pnlPct.toFixed(2)}%)
            </span>
            <span className="sd-telemetry-sub">
              Gross {formatRupee(trade.grossPnl)} · Charges {formatRupee(trade.charges)}
            </span>
          </div>

          <div className="sd-telemetry-cell">
            <span className="sd-telemetry-label">Active Trailing SL</span>
            <span className="sd-telemetry-val text-red">{formatRupee(trade.currentStop)}</span>
            <span className="sd-telemetry-sub">
              Initial SL {formatRupee(trade.initialStop)}{" "}
              {trade.currentStop > trade.entryAt ? "· PROFIT LOCKED" : ""}
            </span>
          </div>

          <div className="sd-telemetry-cell">
            <span className="sd-telemetry-label">Active Step Target</span>
            <span className="sd-telemetry-val text-green">{formatRupee(trade.currentTarget)}</span>
            <span className="sd-telemetry-sub">
              Initial Target {formatRupee(trade.initialTarget)}
            </span>
          </div>

          <div className="sd-telemetry-cell">
            <span className="sd-telemetry-label">Projected Wave Ceiling</span>
            <span className="sd-telemetry-val" style={{ color: "var(--cyan)" }}>
              {formatRupee(projectedTarget)}
            </span>
            <span className="sd-telemetry-sub">
              {projectedTarget > trade.currentTarget
                ? "Steps SL & Target on approach"
                : "At full wave extension"}
            </span>
          </div>

          <div className="sd-telemetry-cell">
            <span className="sd-telemetry-label">Progress · 1m Structure</span>
            <span className="sd-telemetry-val">{progressPct.toFixed(0)}%</span>
            <span className="sd-telemetry-sub">
              {trade.marketTelemetry.candleStructure ?? "STEADY"} · Vol{" "}
              {trade.marketTelemetry.volumeRatio ?? 1}x
            </span>
          </div>
        </div>
      </div>

      {feedback && (
        <div
          className="card"
          style={{
            borderColor: feedback.type === "err" ? "var(--bearish-red)" : "var(--bullish-green)",
            padding: "var(--space-3)",
          }}
        >
          <div
            className="micro"
            style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}
          >
            {feedback.type === "err" ? (
              <AlertTriangle size={14} className="text-red" />
            ) : (
              <CheckCircle2 size={14} className="text-green" />
            )}
            <span>{feedback.text}</span>
          </div>
        </div>
      )}

      {trade.brokerError && (
        <div
          className="card"
          style={{ borderColor: "var(--bearish-red)", padding: "var(--space-3)" }}
        >
          <div
            className="micro text-red"
            style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}
          >
            <AlertTriangle size={14} />
            <span>Upstox Broker Notice: {trade.brokerError}</span>
          </div>
        </div>
      )}

      {/* Live Exit Signal Alert Banner (for SEMI_AUTO when exit mark is reached on the graph) */}
      {isRunning && trade.marketTelemetry.exitSignal && (
        <div
          className="card"
          style={{
            borderColor: "var(--warning-amber)",
            background: "var(--warning-amber-tint)",
            padding: "var(--space-3) var(--space-4)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "var(--space-3)",
            flexWrap: "wrap",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <AlertTriangle size={16} className="text-amber" />
            <div>
              <div className="mono" style={{ fontWeight: 700, color: "var(--warning-amber)" }}>
                ★ EXIT MARK REACHED ({trade.marketTelemetry.exitSignal}) — Recommended Exit @{" "}
                {formatRupee(trade.marketTelemetry.recommendedExitPrice ?? trade.lastPrice)}
              </div>
              <div className="micro text-secondary">
                {trade.marketTelemetry.exitRecommendation ??
                  "Exit condition triggered on live 1m chart. Square off now to lock outcome."}
              </div>
            </div>
          </div>
          <button
            type="button"
            className="btn btn--primary"
            style={{ background: "var(--bearish-red)", borderColor: "var(--bearish-red)" }}
            onClick={handleSquareOff}
            disabled={exitMutation.isPending}
          >
            <Square size={14} />
            <span>{exitMutation.isPending ? "Squaring Off…" : "Square Off Now"}</span>
          </button>
        </div>
      )}

      {/* Visual Live Price Ladder */}
      <TradeLiveLadder trade={trade} />

      {/* Live 1-Minute Option Premium Chart & Manual Override Strip */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: isRunning ? "2.2fr 1fr" : "1fr",
          gap: "var(--space-4)",
        }}
      >
        <TradePremiumChart trade={trade} />

        {isRunning && (
          <div className="card" style={{ padding: "var(--space-4)" }}>
            <div
              style={{
                display: "flex",
                gap: "var(--space-2)",
                alignItems: "center",
                marginBottom: "var(--space-3)",
              }}
            >
              <Sliders size={15} />
              <span className="section-title" style={{ margin: 0 }}>
                Manual SL / Target Override
              </span>
            </div>
            <p className="micro text-muted" style={{ marginBottom: "var(--space-3)" }}>
              The <strong>{traderMeta.name}</strong> pilot automatically re-analyzes every second and steps SL &amp; Target (e.g. 100 → 120 → 150 with SL 75 → 100). You can also override levels manually at any time:
            </p>
            <form onSubmit={handleAdjust}>
              <div className="form-group" style={{ marginBottom: "var(--space-3)" }}>
                <label className="form-label" htmlFor="override-stop">
                  Active Stop-Loss (₹)
                </label>
                <input
                  id="override-stop"
                  type="number"
                  step="0.05"
                  className="input mono"
                  value={editStop}
                  onChange={(e) => setEditStop(e.target.value)}
                />
              </div>
              <div className="form-group" style={{ marginBottom: "var(--space-3)" }}>
                <label className="form-label" htmlFor="override-target">
                  Active Target (₹)
                </label>
                <input
                  id="override-target"
                  type="number"
                  step="0.05"
                  className="input mono"
                  value={editTarget}
                  onChange={(e) => setEditTarget(e.target.value)}
                />
              </div>
              <button
                type="submit"
                className="btn btn--primary"
                style={{ width: "100%" }}
                disabled={adjustMutation.isPending}
              >
                {adjustMutation.isPending ? "Updating…" : "Apply SL / Target"}
              </button>
            </form>
          </div>
        )}
      </div>

      {/* Chronological Trader Decision Log */}
      <div className=" sd-overview-cols">
        <FibRetracementChart
          entryAt={trade.entryAt}
          currentStop={trade.currentStop}
          currentTarget={trade.currentTarget}
          lastPrice={trade.exitPrice ?? trade.lastPrice}
          fibLevels={trade.marketTelemetry.fibLevels}
          onSelectTargetLevel={
            isRunning
              ? (tgt, sl, lbl) => {
                  adjustMutation.mutate(
                    {
                      currentStop: sl,
                      currentTarget: tgt,
                      reason: `Applied Fib Level (${lbl}): SL ₹${sl}, Target ₹${tgt}`,
                    },
                    {
                      onSuccess: (updated) => {
                        setEditStop(String(updated.currentStop));
                        setEditTarget(String(updated.currentTarget));
                        setFeedback({
                          type: "ok",
                          text: `Applied ${lbl}: SL ₹${updated.currentStop}, Target ₹${updated.currentTarget}`,
                        });
                      },
                    },
                  );
                }
              : undefined
          }
        />

        <OptionChainOAChart
          underlyingCode={trade.underlyingCode}
          optionType={trade.optionType}
          strike={trade.strike}
          initialStop={trade.currentStop}
          initialTarget={trade.currentTarget}
          oaAnalysis={trade.marketTelemetry.oaAnalysis}
        />
      </div>

      {/* Chronological Trader Decision Log */}
      <div className="section-title">
        1-Second Trader Re-Analysis &amp; Step-Wave Trail Log ({trade.trailEvents.length})
      </div>
      <TradeDecisionLog events={trade.trailEvents} />
    </div>
  );
};

