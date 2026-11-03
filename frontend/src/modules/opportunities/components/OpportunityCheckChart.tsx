import React from "react";
import { OpportunityCheckItem } from "../types/opportunities.types";
import { formatRupee, formatTime } from "./formatters";

export const OpportunityCheckChart: React.FC<{
  checkResult: OpportunityCheckItem;
}> = ({ checkResult }) => {
  const { entry, stop, target, exitPrice, peakPrice, troughPrice, series = [], hitAt, targetAchieved, outcome } =
    checkResult;

  // Build points: if 1m candle series exists, use it; otherwise build a 3-point synthetic path (Entry -> Peak/Trough -> Exit)
  const points =
    series.length >= 2
      ? series.map((b) => ({
          t: b.t,
          c: b.c,
          h: b.h,
          l: b.l,
        }))
      : [
          { t: checkResult.createdAt, c: entry, h: entry, l: entry },
          {
            t: hitAt || checkResult.validUntil,
            c: exitPrice >= entry ? peakPrice : troughPrice,
            h: peakPrice,
            l: troughPrice,
          },
          { t: checkResult.validUntil, c: exitPrice, h: exitPrice, l: exitPrice },
        ];

  const allPrices = [
    entry,
    stop,
    target,
    exitPrice,
    peakPrice,
    troughPrice,
    ...points.flatMap((p) => [p.c, p.h, p.l]),
  ].filter((v) => Number.isFinite(v) && v > 0);

  const rawMin = Math.min(...allPrices);
  const rawMax = Math.max(...allPrices);
  const pad = Math.max((rawMax - rawMin) * 0.14, 1);
  const minP = rawMin - pad;
  const maxP = rawMax + pad;
  const span = Math.max(maxP - minP, 1);

  const W = 680;
  const H = 175;
  const LEFT = 56;
  const RIGHT = 92;
  const TOP = 14;
  const BOTTOM = 24;
  const plotW = W - LEFT - RIGHT;
  const plotH = H - TOP - BOTTOM;

  const yOf = (price: number) => TOP + ((maxP - price) / span) * plotH;
  const xOf = (idx: number) =>
    points.length <= 1 ? LEFT + plotW / 2 : LEFT + (idx / (points.length - 1)) * plotW;

  const yTarget = yOf(target);
  const yEntry = yOf(entry);
  const yStop = yOf(stop);
  const yExit = yOf(exitPrice);

  // Find index of peak high and hit point
  let peakIdx = 0;
  for (let i = 1; i < points.length; i++) {
    if (points[i].h >= points[peakIdx].h) peakIdx = i;
  }

  let hitIdx = -1;
  if (hitAt) {
    hitIdx = points.findIndex((p) => p.t === hitAt);
  }
  if (hitIdx < 0 && (targetAchieved || outcome === "STOP_HIT")) {
    hitIdx = points.findIndex((p) =>
      targetAchieved ? p.h >= target : p.l <= stop
    );
  }

  const closeLine = points.map((p, i) => `${xOf(i).toFixed(1)},${yOf(p.c).toFixed(1)}`).join(" ");
  const highBand = [
    ...points.map((p, i) => `${xOf(i).toFixed(1)},${yOf(p.h).toFixed(1)}`),
    ...[...points].reverse().map((p, rIdx) => {
      const i = points.length - 1 - rIdx;
      return `${xOf(i).toFixed(1)},${yOf(p.l).toFixed(1)}`;
    }),
  ].join(" ");

  const lineColor =
    checkResult.achievedPct >= 100
      ? "var(--bullish-green)"
      : checkResult.achievedPct >= 0
      ? "var(--kite-blue)"
      : "var(--bearish-red)";

  return (
    <div
      style={{
        padding: "8px 12px 10px",
        borderBottom: "1px solid var(--border-subtle)",
        background: "rgba(0, 0, 0, 0.16)",
      }}
    >
      {/* Legend Row */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 10,
          marginBottom: 6,
          fontSize: "0.7rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <span className="mono" style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: "var(--kite-blue)",
                display: "inline-block",
              }}
            />
            Entry: <strong>{formatRupee(entry)}</strong>
          </span>
          <span className="mono pos" style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: "var(--bullish-green)",
                display: "inline-block",
              }}
            />
            Target: <strong>{formatRupee(target)}</strong>
          </span>
          <span className="mono neg" style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: "var(--bearish-red)",
                display: "inline-block",
              }}
            />
            Stop: <strong>{formatRupee(stop)}</strong>
          </span>
          <span className="mono" style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: lineColor,
                display: "inline-block",
              }}
            />
            Actual Exit/Mark: <strong>{formatRupee(exitPrice)}</strong>
          </span>
        </div>
        <span className="mono" style={{ color: "var(--text-muted)" }}>
          Peak High: <strong className="pos">{formatRupee(peakPrice)}</strong> · Low:{" "}
          <strong className="neg">{formatRupee(troughPrice)}</strong>
        </span>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", height: 175, display: "block", overflow: "visible" }}
        role="img"
        aria-label="Opportunity price trajectory vs Entry, Target and Stop Loss"
      >
        {/* Shaded reward & risk zones */}
        <rect
          x={LEFT}
          y={Math.min(yTarget, yEntry)}
          width={plotW}
          height={Math.abs(yEntry - yTarget)}
          fill="var(--bullish-green)"
          fillOpacity={0.05}
        />
        <rect
          x={LEFT}
          y={Math.min(yEntry, yStop)}
          width={plotW}
          height={Math.abs(yStop - yEntry)}
          fill="var(--bearish-red)"
          fillOpacity={0.05}
        />

        {/* Target Horizontal Line */}
        <line
          x1={LEFT}
          y1={yTarget}
          x2={LEFT + plotW}
          y2={yTarget}
          stroke="var(--bullish-green)"
          strokeWidth={1.2}
          strokeDasharray="4 3"
        />
        <text
          x={LEFT + plotW + 6}
          y={yTarget + 3}
          fill="var(--bullish-green)"
          fontSize="10"
          fontFamily="var(--font-mono)"
        >
          TGT {target.toFixed(1)}
        </text>

        {/* Entry Horizontal Line */}
        <line
          x1={LEFT}
          y1={yEntry}
          x2={LEFT + plotW}
          y2={yEntry}
          stroke="var(--kite-blue)"
          strokeWidth={1.2}
          strokeDasharray="2 2"
        />
        <text
          x={LEFT + plotW + 6}
          y={yEntry + 3}
          fill="var(--kite-blue)"
          fontSize="10"
          fontFamily="var(--font-mono)"
        >
          ENT {entry.toFixed(1)}
        </text>

        {/* Stop Horizontal Line */}
        <line
          x1={LEFT}
          y1={yStop}
          x2={LEFT + plotW}
          y2={yStop}
          stroke="var(--bearish-red)"
          strokeWidth={1.2}
          strokeDasharray="4 3"
        />
        <text
          x={LEFT + plotW + 6}
          y={yStop + 3}
          fill="var(--bearish-red)"
          fontSize="10"
          fontFamily="var(--font-mono)"
        >
          SL {stop.toFixed(1)}
        </text>

        {/* Left Y-axis reference labels */}
        <text
          x={LEFT - 6}
          y={TOP + 8}
          textAnchor="end"
          fill="var(--text-muted)"
          fontSize="9.5"
          fontFamily="var(--font-mono)"
        >
          ₹{maxP.toFixed(0)}
        </text>
        <text
          x={LEFT - 6}
          y={TOP + plotH}
          textAnchor="end"
          fill="var(--text-muted)"
          fontSize="9.5"
          fontFamily="var(--font-mono)"
        >
          ₹{minP.toFixed(0)}
        </text>

        {/* High-Low range band */}
        {points.length > 1 && (
          <polygon points={highBand} fill={lineColor} fillOpacity={0.12} />
        )}

        {/* 1-minute High/Low wicks */}
        {points.map((p, i) => (
          <line
            key={i}
            x1={xOf(i)}
            y1={yOf(p.h)}
            x2={xOf(i)}
            y2={yOf(p.l)}
            stroke={lineColor}
            strokeOpacity={0.35}
            strokeWidth={1}
          />
        ))}

        {/* Actual Close Price Trajectory Line */}
        {points.length > 1 && (
          <polyline
            fill="none"
            stroke={lineColor}
            strokeWidth={2}
            points={closeLine}
          />
        )}

        {/* Entry Marker (Start) */}
        <circle
          cx={xOf(0)}
          cy={yEntry}
          r={4}
          fill="var(--kite-blue)"
          stroke="#0d1117"
          strokeWidth={1.5}
        />

        {/* Peak High Marker */}
        {points.length > 1 && (
          <g>
            <circle
              cx={xOf(peakIdx)}
              cy={yOf(points[peakIdx].h)}
              r={3.5}
              fill="var(--bullish-green)"
            />
            <text
              x={xOf(peakIdx)}
              y={Math.max(10, yOf(points[peakIdx].h) - 6)}
              textAnchor="middle"
              fill="var(--bullish-green)"
              fontSize="9.5"
              fontFamily="var(--font-mono)"
            >
              Peak ₹{points[peakIdx].h.toFixed(1)}
            </text>
          </g>
        )}

        {/* Target Hit / Stop Hit Marker */}
        {hitIdx >= 0 && (
          <circle
            cx={xOf(hitIdx)}
            cy={targetAchieved ? yTarget : yStop}
            r={5}
            fill={targetAchieved ? "var(--bullish-green)" : "var(--bearish-red)"}
            stroke="#fff"
            strokeWidth={1.5}
          />
        )}

        {/* Actual Exit / Final Mark Dot */}
        <circle
          cx={xOf(points.length - 1)}
          cy={yExit}
          r={4.5}
          fill={lineColor}
          stroke="#fff"
          strokeWidth={1.2}
        />
        <text
          x={LEFT + plotW + 6}
          y={Math.min(H - 6, Math.max(12, yExit + 3))}
          fill={lineColor}
          fontSize="10"
          fontWeight="bold"
          fontFamily="var(--font-mono)"
        >
          ACT {exitPrice.toFixed(1)}
        </text>

        {/* Bottom X-axis time labels */}
        <text
          x={LEFT}
          y={H - 5}
          textAnchor="start"
          fill="var(--text-muted)"
          fontSize="9.5"
          fontFamily="var(--font-mono)"
        >
          {formatTime(points[0].t)} (Entry)
        </text>
        {points.length > 2 && (
          <text
            x={LEFT + plotW / 2}
            y={H - 5}
            textAnchor="middle"
            fill="var(--text-muted)"
            fontSize="9.5"
            fontFamily="var(--font-mono)"
          >
            {formatTime(points[Math.floor(points.length / 2)].t)}
          </text>
        )}
        <text
          x={LEFT + plotW}
          y={H - 5}
          textAnchor="end"
          fill="var(--text-muted)"
          fontSize="9.5"
          fontFamily="var(--font-mono)"
        >
          {formatTime(points[points.length - 1].t)} (End)
        </text>
      </svg>
    </div>
  );
};

