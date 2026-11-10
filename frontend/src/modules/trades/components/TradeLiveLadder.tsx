import React from "react";
import { ActiveTrade } from "../types/trades.types";
import { formatRupee } from "../../opportunities/components/formatters";

export const TradeLiveLadder: React.FC<{ trade: ActiveTrade }> = ({ trade: t }) => {
  const minVal = Math.min(t.initialStop, t.currentStop, t.troughPrice, t.entryAt) * 0.96;
  const maxVal = Math.max(t.initialTarget, t.currentTarget, t.peakPrice, t.lastPrice, t.entryAt) * 1.04;
  const span = Math.max(1, maxVal - minVal);
  const pct = (v: number) => Math.max(2, Math.min(98, ((v - minVal) / span) * 100));

  const slMoved = t.currentStop > t.initialStop + 0.01;
  const targetMoved = Math.abs(t.currentTarget - t.initialTarget) > 0.01;

  return (
    <div className="card" style={{ padding: "var(--space-4)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
        <span className="section-title" style={{ margin: 0 }}>Live Position Price Ladder</span>
        <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "center" }}>
          {slMoved && (
            <span className="badge badge--green">
              SL Trailed: {formatRupee(t.initialStop)} → {formatRupee(t.currentStop)}
            </span>
          )}
          {targetMoved && (
            <span className="badge badge--cyan">
              Target Trailed: {formatRupee(t.initialTarget)} → {formatRupee(t.currentTarget)}
            </span>
          )}
        </div>
      </div>

      {/* Horizontal visual track */}
      <div
        style={{
          position: "relative",
          height: "36px",
          background: "var(--bg-elevated, #141922)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "4px",
          margin: "var(--space-4) 0",
        }}
      >
        {/* Profit zone between entryAt and currentTarget */}
        <div
          style={{
            position: "absolute",
            top: 0,
            bottom: 0,
            left: `${pct(t.entryAt)}%`,
            width: `${Math.max(0, pct(t.currentTarget) - pct(t.entryAt))}%`,
            background: "rgba(34, 197, 94, 0.12)",
          }}
        />
        {/* Locked profit zone when currentStop > entryAt */}
        {t.currentStop > t.entryAt && (
          <div
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              left: `${pct(t.entryAt)}%`,
              width: `${Math.max(0, pct(t.currentStop) - pct(t.entryAt))}%`,
              background: "rgba(34, 197, 94, 0.28)",
              borderRight: "2px dashed var(--bullish-green)",
            }}
            title="Guaranteed locked profit zone"
          />
        )}

        {/* Initial Stop marker */}
        <div
          style={{
            position: "absolute",
            top: "-4px",
            bottom: "-4px",
            left: `${pct(t.initialStop)}%`,
            width: "2px",
            background: "rgba(239, 68, 68, 0.45)",
          }}
          title={`Initial Stop: ${formatRupee(t.initialStop)}`}
        />

        {/* Active Stop marker */}
        <div
          style={{
            position: "absolute",
            top: "-6px",
            bottom: "-6px",
            left: `${pct(t.currentStop)}%`,
            width: "3px",
            background: "var(--bearish-red)",
          }}
          title={`Current Stop: ${formatRupee(t.currentStop)}`}
        />

        {/* Entry marker */}
        <div
          style={{
            position: "absolute",
            top: "-4px",
            bottom: "-4px",
            left: `${pct(t.entryAt)}%`,
            width: "2px",
            background: "var(--text-secondary)",
          }}
          title={`Entry At: ${formatRupee(t.entryAt)}`}
        />

        {/* Initial Target marker */}
        {targetMoved && (
          <div
            style={{
              position: "absolute",
              top: "-4px",
              bottom: "-4px",
              left: `${pct(t.initialTarget)}%`,
              width: "2px",
              background: "rgba(34, 197, 94, 0.45)",
            }}
            title={`Initial Target: ${formatRupee(t.initialTarget)}`}
          />
        )}

        {/* Current Target marker */}
        <div
          style={{
            position: "absolute",
            top: "-6px",
            bottom: "-6px",
            left: `${pct(t.currentTarget)}%`,
            width: "3px",
            background: "var(--bullish-green)",
          }}
          title={`Current Target: ${formatRupee(t.currentTarget)}`}
        />

        {/* Live LTP puck */}
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: `${pct(t.lastPrice)}%`,
            transform: "translate(-50%, -50%)",
            padding: "2px 8px",
            borderRadius: "3px",
            background: t.lastPrice >= t.entryAt ? "var(--bullish-green)" : "var(--bearish-red)",
            color: "#0b0e14",
            fontFamily: "var(--font-mono)",
            fontSize: "12px",
            fontWeight: 700,
            whiteSpace: "nowrap",
            zIndex: 2,
          }}
        >
          LTP {formatRupee(t.lastPrice)}
        </div>
      </div>

      {/* Numeric breakdown row */}
      <div className="sl-card__grid" style={{ gridTemplateColumns: "repeat(6, minmax(0, 1fr))" }}>
        <div className="sl-stat">
          <span className="label">Initial SL</span>
          <span className="sl-stat__value mono text-muted">{formatRupee(t.initialStop)}</span>
        </div>
        <div className="sl-stat">
          <span className="label">Active Trailing SL</span>
          <span className="sl-stat__value mono text-red">{formatRupee(t.currentStop)}</span>
        </div>
        <div className="sl-stat">
          <span className="label">Entry Fill</span>
          <span className="sl-stat__value mono">{formatRupee(t.entryAt)}</span>
        </div>
        <div className="sl-stat">
          <span className="label">Peak Reached</span>
          <span className="sl-stat__value mono text-green">{formatRupee(t.peakPrice)}</span>
        </div>
        <div className="sl-stat">
          <span className="label">Initial Target</span>
          <span className="sl-stat__value mono text-muted">{formatRupee(t.initialTarget)}</span>
        </div>
        <div className="sl-stat">
          <span className="label">Active Target</span>
          <span className="sl-stat__value mono text-green">{formatRupee(t.currentTarget)}</span>
        </div>
      </div>
    </div>
  );
};

