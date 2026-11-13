import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "@tanstack/react-router";
import { AlertTriangle, ArrowLeft, CheckCircle2, Radio, Sliders, Square } from "lucide-react";
import { useAdjustTrade, useExitTrade, useTradeDetail } from "../hooks/useTrades";
import { useTradeStream } from "../hooks/useTradeStream";
import { TradeLiveLadder } from "../components/TradeLiveLadder";
import { TradePremiumChart } from "../components/TradePremiumChart";
import { TradeDecisionLog } from "../components/TradeDecisionLog";
import { formatExpiry, formatRupee } from "../../opportunities/components/formatters";

const hms = (iso: string | null): string =>
  iso ? new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false }) : "—";

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
      <div className="page-container">
        <div className="empty-state">
          <div className="empty-state__title">Loading Trader Cockpit #{id}…</div>
        </div>
      </div>
    );
  }

  const isRunning = trade.tradeState === "RUNNING";
  const pnlClass = trade.netPnl > 0 ? "text-green" : trade.netPnl < 0 ? "text-red" : "";
  const progressPct = trade.marketTelemetry.progressPct ?? 0;

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
          setFeedback({ type: "ok", text: `Updated SL to ₹${updated.currentStop} and Target to ₹${updated.currentTarget}` });
        },
        onError: (err) => {
          setFeedback({ type: "err", text: err instanceof Error ? err.message : "Failed to update levels" });
        },
      }
    );
  };

  const handleSquareOff = () => {
    if (!window.confirm(`Square off ${trade.underlyingCode} ${trade.strike} ${trade.optionType} (${trade.quantity} qty) at current market price?`)) {
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
          setFeedback({ type: "err", text: err instanceof Error ? err.message : "Square-off failed" });
        },
      }
    );
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => navigate({ to: "/sessions/$id", params: { id: String(trade.sessionId) } })}
            >
              <ArrowLeft size={14} />
              <span>Session #{trade.sessionId}</span>
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => navigate({ to: "/trades" })}>
              <span>All Trades</span>
            </button>
          </div>
          <h1 className="page-title" style={{ marginTop: "var(--space-2)" }}>
            Trade #{trade.id} · {trade.underlyingCode} {trade.strike} {trade.optionType}
          </h1>
          <p className="text-secondary micro">
            {formatExpiry(trade.expiry)} · {trade.strategy ?? "Tactical Setup"} · Profile:{" "}
            <strong>{trade.traderProfile}</strong> ({trade.winRatePct.toFixed(0)}% win-rate) ·{" "}
            {trade.routeThroughUpstox ? `Upstox LIVE (${trade.brokerStatus})` : "Simulated Execution"} · Entered{" "}
            {hms(trade.enteredAt)} IST
          </p>
        </div>

        <div className="page-actions">
          <span className={isRunning ? "badge badge--green" : "badge badge--slate"}>
            <Radio size={12} />
            <span>{isRunning ? "TRADER PILOT LIVE (1s)" : `EXITED (${trade.exitReason ?? "CLOSED"})`}</span>
          </span>
          {isRunning && (
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
          )}
        </div>
      </div>

      <div className="content-body sl-page">
        {/* Executive Telemetry Strip */}
        <div className="sl-strip">
          <div className="sl-stat">
            <span className="label">Entry → Live LTP</span>
            <span className="sl-stat__value mono">
              {formatRupee(trade.entryAt)} → {formatRupee(trade.exitPrice ?? trade.lastPrice)}
            </span>
            <span className="micro text-muted">
              {trade.lots} lot(s) × {trade.lotUnits} = {trade.quantity} qty ({formatRupee(trade.capitalUsed)})
            </span>
          </div>

          <div className="sl-stat">
            <span className="label">Net P&L (After Charges)</span>
            <span className={`sl-stat__value mono ${pnlClass}`}>
              {formatRupee(trade.netPnl)} ({trade.pnlPct >= 0 ? "+" : ""}{trade.pnlPct.toFixed(2)}%)
            </span>
            <span className="micro text-muted">
              Gross {formatRupee(trade.grossPnl)} · Charges {formatRupee(trade.charges)}
            </span>
          </div>

          <div className="sl-stat">
            <span className="label">Active Trailing SL</span>
            <span className="sl-stat__value mono text-red">{formatRupee(trade.currentStop)}</span>
            <span className="micro text-muted">Initial SL {formatRupee(trade.initialStop)}</span>
          </div>

          <div className="sl-stat">
            <span className="label">Active Trailing Target</span>
            <span className="sl-stat__value mono text-green">{formatRupee(trade.currentTarget)}</span>
            <span className="micro text-muted">Initial Target {formatRupee(trade.initialTarget)}</span>
          </div>

          <div className="sl-stat">
            <span className="label">Target Progress · Mode</span>
            <span className="sl-stat__value mono">{progressPct.toFixed(0)}%</span>
            <span className="micro text-muted">
              {trade.marketTelemetry.inRunnerMode
                ? "RUNNER MODE (Target Expanded)"
                : trade.traderProfile === "HIGH_CONVICTION"
                  ? "Wait 80% → Lock 50% SL"
                  : "Step Trail (50% → 80% → Target)"}
            </span>
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
            <div className="micro" style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
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
          <div className="card" style={{ borderColor: "var(--bearish-red)", padding: "var(--space-3)" }}>
            <div className="micro text-red" style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
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
        <div style={{ display: "grid", gridTemplateColumns: isRunning ? "2fr 1fr" : "1fr", gap: "var(--space-4)" }}>
          <TradePremiumChart trade={trade} />

          {isRunning && (
            <div className="card" style={{ padding: "var(--space-4)" }}>
              <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center", marginBottom: "var(--space-3)" }}>
                <Sliders size={15} />
                <span className="section-title" style={{ margin: 0 }}>Manual SL / Target Override</span>
              </div>
              <p className="micro text-muted" style={{ marginBottom: "var(--space-3)" }}>
                The Trader pilot automatically ratchets SL and Target based on win-rate and live volume. You can also nudge them manually at any time:
              </p>
              <form onSubmit={handleAdjust}>
                <div className="form-group" style={{ marginBottom: "var(--space-3)" }}>
                  <label className="form-label" htmlFor="override-stop">Active Stop-Loss (₹)</label>
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
                  <label className="form-label" htmlFor="override-target">Active Target (₹)</label>
                  <input
                    id="override-target"
                    type="number"
                    step="0.05"
                    className="input mono"
                    value={editTarget}
                    onChange={(e) => setEditTarget(e.target.value)}
                  />
                </div>
                <button type="submit" className="btn btn--primary" style={{ width: "100%" }} disabled={adjustMutation.isPending}>
                  {adjustMutation.isPending ? "Updating…" : "Apply SL / Target"}
                </button>
              </form>
            </div>
          )}
        </div>

        {/* Chronological Trader Decision Log */}
        <div className="section-title">Trader Pilot Decision Trail ({trade.trailEvents.length})</div>
        <TradeDecisionLog events={trade.trailEvents} />
      </div>
    </div>
  );
};

