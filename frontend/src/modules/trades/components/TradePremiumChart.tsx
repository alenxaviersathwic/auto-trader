import React from "react";
import { ActiveTrade } from "../types/trades.types";
import { formatRupee } from "../../opportunities/components/formatters";

/**
 * 1-Minute Option Premium Candlestick & Volume Chart with Entry, Active Stop, and Active Target overlays.
 */
export const TradePremiumChart: React.FC<{ trade: ActiveTrade }> = ({ trade: t }) => {
  const bars = t.candles1m.slice(-40);
  const width = 760;
  const height = 220;
  const padLeft = 12;
  const padRight = 68;
  const padTop = 14;
  const padBottom = 38;
  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;

  const prices = [
    t.entryAt,
    t.currentStop,
    t.currentTarget,
    t.lastPrice,
    ...bars.flatMap((b) => [b.h, b.l]),
  ];
  const minP = Math.min(...prices) * 0.985;
  const maxP = Math.max(...prices) * 1.015;
  const spanP = Math.max(0.5, maxP - minP);
  const yFor = (p: number) => padTop + ((maxP - p) / spanP) * plotH;

  const maxVol = Math.max(1, ...bars.map((b) => b.v ?? 0));

  return (
    <div className="card" style={{ padding: "var(--space-4)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-2)" }}>
        <div>
          <span className="section-title" style={{ margin: 0 }}>
            Option Premium 1m Chart & Volume
          </span>
          <span className="micro text-muted" style={{ marginLeft: "var(--space-2)" }}>
            Structure: {t.marketTelemetry.candleStructure ?? "NEUTRAL"} · Momentum:{" "}
            {t.marketTelemetry.momentumState ?? "STEADY"} · Vol Ratio: {t.marketTelemetry.volumeRatio ?? 1}x
          </span>
        </div>
        <span className="mono micro text-secondary">
          {bars.length > 0 ? `${bars.length} bars (1m)` : "Live tick mode (awaiting 1m candle history)"}
        </span>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ width: "100%", height: "220px", display: "block", background: "var(--bg-elevated, #10141d)", borderRadius: "4px" }}
      >
        {/* Target Line */}
        <line
          x1={padLeft}
          x2={width - padRight}
          y1={yFor(t.currentTarget)}
          y2={yFor(t.currentTarget)}
          stroke="#22c55e"
          strokeWidth="1.2"
          strokeDasharray="4 3"
        />
        <text x={width - padRight + 4} y={yFor(t.currentTarget) + 4} fill="#22c55e" fontSize="10" fontFamily="monospace">
          TGT {t.currentTarget.toFixed(1)}
        </text>

        {/* Entry Line */}
        <line
          x1={padLeft}
          x2={width - padRight}
          y1={yFor(t.entryAt)}
          y2={yFor(t.entryAt)}
          stroke="#94a3b8"
          strokeWidth="1"
          strokeDasharray="2 2"
        />
        <text x={width - padRight + 4} y={yFor(t.entryAt) + 4} fill="#94a3b8" fontSize="10" fontFamily="monospace">
          ENT {t.entryAt.toFixed(1)}
        </text>

        {/* Active Stop Line */}
        <line
          x1={padLeft}
          x2={width - padRight}
          y1={yFor(t.currentStop)}
          y2={yFor(t.currentStop)}
          stroke="#ef4444"
          strokeWidth="1.2"
          strokeDasharray="4 3"
        />
        <text x={width - padRight + 4} y={yFor(t.currentStop) + 4} fill="#ef4444" fontSize="10" fontFamily="monospace">
          SL {t.currentStop.toFixed(1)}
        </text>

        {/* Candlesticks & Volume Bars */}
        {bars.map((b, idx) => {
          const step = plotW / Math.max(1, bars.length);
          const cx = padLeft + idx * step + step * 0.5;
          const bw = Math.max(3, Math.min(12, step * 0.65));
          const up = b.c >= b.o;
          const color = up ? "#22c55e" : "#ef4444";
          const yHigh = yFor(b.h);
          const yLow = yFor(b.l);
          const yOpen = yFor(b.o);
          const yClose = yFor(b.c);
          const top = Math.min(yOpen, yClose);
          const bodyH = Math.max(2, Math.abs(yClose - yOpen));

          const vH = ((b.v ?? 0) / maxVol) * 26;
          return (
            <g key={b.t || idx}>
              <line x1={cx} x2={cx} y1={yHigh} y2={yLow} stroke={color} strokeWidth="1" />
              <rect x={cx - bw / 2} y={top} width={bw} height={bodyH} fill={color} rx="1" />
              <rect
                x={cx - bw / 2}
                y={height - 6 - vH}
                width={bw}
                height={vH}
                fill={up ? "rgba(34,197,94,0.35)" : "rgba(239,68,68,0.35)"}
              />
            </g>
          );
        })}

        {/* Live LTP Line */}
        <line
          x1={padLeft}
          x2={width - padRight}
          y1={yFor(t.lastPrice)}
          y2={yFor(t.lastPrice)}
          stroke="#38bdf8"
          strokeWidth="1"
        />
        <text x={width - padRight + 4} y={yFor(t.lastPrice) + 4} fill="#38bdf8" fontSize="10" fontFamily="monospace">
          LTP {formatRupee(t.lastPrice)}
        </text>
      </svg>
    </div>
  );
};

