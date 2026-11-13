import React from "react";
import { ActiveTrade } from "../types/trades.types";
import { formatRupee } from "../../opportunities/components/formatters";

/**
 * Pro Option Premium 1m Chart & Real-Time Trade Trajectory with:
 * - Shaded Profit Zone (Entry -> Target) & Risk / Locked-Profit Zone (Current SL -> Entry)
 * - ENTRY BUY marker pin
 * - 50% & 80% SL Ratchet Milestone guides
 * - Active Trailing SL line & locked-profit badge
 * - Target & Exit Zone marker callouts (where and why to exit)
 * - Synthesized live price trajectory when 1m candle history is sparse
 */
export const TradePremiumChart: React.FC<{ trade: ActiveTrade }> = ({ trade: t }) => {
  const bars = t.candles1m.slice(-40);
  const width = 820;
  const height = 300;
  const padLeft = 18;
  const padRight = 148;
  const padTop = 20;
  const padBottom = 42;
  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;

  const targetMove = Math.max(0.5, t.initialTarget - t.entryAt);
  const milestone50 = t.entryAt + 0.5 * targetMove;
  const milestone80 = t.entryAt + 0.8 * targetMove;
  const projectedTarget = Number(t.marketTelemetry?.projectedTarget || 0);
  const hasProjectedCeiling = projectedTarget > t.currentTarget + 0.5;

  // Synthesize live trajectory points from entryAt -> trailEvents -> peakPrice -> lastPrice when 1m bars are sparse
  const trailPoints = [
    t.entryAt,
    ...(t.trailEvents || []).map((ev) => Number(ev.ltp || t.entryAt)).filter((v) => v > 0),
    t.peakPrice > t.entryAt ? t.peakPrice : t.lastPrice,
    t.exitPrice ?? t.lastPrice,
  ];

  const prices = [
    t.initialStop,
    t.currentStop,
    t.entryAt,
    milestone50,
    milestone80,
    t.currentTarget,
    ...(hasProjectedCeiling ? [projectedTarget] : []),
    t.peakPrice,
    t.lastPrice,
    ...(t.exitPrice ? [t.exitPrice] : []),
    ...bars.flatMap((b) => [b.h, b.l]),
    ...trailPoints,
  ].filter((p) => Number.isFinite(p) && p > 0);

  const minP = Math.min(...prices) * 0.96;
  const maxP = Math.max(...prices) * 1.04;
  const spanP = Math.max(1.0, maxP - minP);
  const yFor = (p: number) =>
    Math.max(padTop + 4, Math.min(padTop + plotH - 4, padTop + ((maxP - p) / spanP) * plotH));

  const maxVol = Math.max(1, ...bars.map((b) => b.v ?? 0));

  const yTarget = yFor(t.currentTarget);
  const yProjected = hasProjectedCeiling ? yFor(projectedTarget) : yTarget;
  const yEntry = yFor(t.entryAt);
  const yStop = yFor(t.currentStop);
  const yInitStop = yFor(t.initialStop);
  const yLtp = yFor(t.exitPrice ?? t.lastPrice);
  const yM50 = yFor(milestone50);
  const yM80 = yFor(milestone80);

  const slLockedProfit = t.currentStop > t.entryAt;
  const exitSignal = t.marketTelemetry.exitSignal;
  const isExited = t.tradeState === "EXITED";

  // Build polyline coordinates for synthesized trajectory when bars.length < 3
  const polyPoints = trailPoints
    .map((px, i) => {
      const x =
        padLeft +
        (trailPoints.length <= 1 ? plotW * 0.5 : (i / (trailPoints.length - 1)) * (plotW * 0.88));
      const y = yFor(px);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const lastPointX =
    bars.length >= 3
      ? padLeft + ((bars.length - 0.5) / bars.length) * plotW
      : padLeft + plotW * 0.88;

  return (
    <div className="card" style={{ padding: "var(--space-4)" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "var(--space-2)",
          marginBottom: "var(--space-3)",
        }}
      >
        <div>
          <span className="section-title" style={{ margin: 0 }}>
            Live Trade Graph · Entry, Trailing SL &amp; Exit Marks
          </span>
          <span className="micro text-muted" style={{ marginLeft: "var(--space-2)" }}>
            1m Structure: <strong>{t.marketTelemetry.candleStructure ?? "NEUTRAL"}</strong> · Momentum:{" "}
            <strong>{t.marketTelemetry.momentumState ?? "STEADY"}</strong> · Vol Ratio:{" "}
            <strong>{t.marketTelemetry.volumeRatio ?? 1}x</strong>
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          {exitSignal && !isExited && (
            <span className="badge badge--amber">EXIT MARK TRIGGERED: {exitSignal}</span>
          )}
          {slLockedProfit && (
            <span className="badge badge--green">
              PROFIT LOCKED AT SL {formatRupee(t.currentStop)}
            </span>
          )}
          <span className="mono micro text-secondary">
            {bars.length > 0 ? `${bars.length} × 1m candles` : "Live Tick Trajectory"}
          </span>
        </div>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{
          width: "100%",
          height: "300px",
          display: "block",
          background: "#131720",
          borderRadius: "4px",
          border: "1px solid var(--border-subtle)",
        }}
      >
        {/* Shaded Profit Zone (Entry -> Current Target) */}
        <rect
          x={padLeft}
          y={Math.min(yTarget, yEntry)}
          width={plotW}
          height={Math.max(2, Math.abs(yEntry - yTarget))}
          fill="rgba(76, 175, 80, 0.06)"
        />

        {/* Shaded Risk or Locked-Profit Zone (Current Stop -> Entry) */}
        <rect
          x={padLeft}
          y={Math.min(yStop, yEntry)}
          width={plotW}
          height={Math.max(2, Math.abs(yStop - yEntry))}
          fill={slLockedProfit ? "rgba(76, 175, 80, 0.12)" : "rgba(239, 83, 80, 0.07)"}
        />

        {/* 80% Milestone Guide (SL Locks 50% Profit) */}
        {yM80 > yTarget + 12 && yM80 < yEntry - 12 && (
          <g>
            <line
              x1={padLeft}
              x2={padLeft + plotW}
              y1={yM80}
              y2={yM80}
              stroke="rgba(56, 189, 248, 0.28)"
              strokeWidth="1"
              strokeDasharray="2 4"
            />
            <text
              x={padLeft + 6}
              y={yM80 - 4}
              fill="rgba(56, 189, 248, 0.75)"
              fontSize="9.5"
              fontFamily="monospace"
            >
              ◆ 80% ZONE (₹{milestone80.toFixed(1)}) → Lock SL at ₹{(t.entryAt + 0.5 * targetMove).toFixed(1)}
            </text>
          </g>
        )}

        {/* 50% Milestone Guide (Step Guard SL Trail) */}
        {t.traderProfile === "STEP_GUARD" && yM50 > yM80 + 12 && yM50 < yEntry - 12 && (
          <g>
            <line
              x1={padLeft}
              x2={padLeft + plotW}
              y1={yM50}
              y2={yM50}
              stroke="rgba(255, 152, 0, 0.28)"
              strokeWidth="1"
              strokeDasharray="2 4"
            />
            <text
              x={padLeft + 6}
              y={yM50 - 4}
              fill="rgba(255, 152, 0, 0.8)"
              fontSize="9.5"
              fontFamily="monospace"
            >
              ◆ 50% ZONE (₹{milestone50.toFixed(1)}) → Step SL to ₹{(t.entryAt + 0.3 * targetMove).toFixed(1)}
            </text>
          </g>
        )}

        {/* Initial Stop Line (if Current Stop has trailed above it) */}
        {Math.abs(t.currentStop - t.initialStop) >= 0.1 && (
          <g>
            <line
              x1={padLeft}
              x2={padLeft + plotW}
              y1={yInitStop}
              y2={yInitStop}
              stroke="rgba(239, 83, 80, 0.35)"
              strokeWidth="1"
              strokeDasharray="2 3"
            />
            <text
              x={padLeft + plotW + 6}
              y={yInitStop + 3}
              fill="rgba(239, 83, 80, 0.6)"
              fontSize="9.5"
              fontFamily="monospace"
            >
              INIT SL ₹{t.initialStop.toFixed(2)}
            </text>
          </g>
        )}

        {/* Projected Wave / Fibonacci 1.618 Extension Ceiling Line */}
        {hasProjectedCeiling && Math.abs(yProjected - yTarget) > 14 && (
          <g>
            <line
              x1={padLeft}
              x2={padLeft + plotW}
              y1={yProjected}
              y2={yProjected}
              stroke="#38bdf8"
              strokeWidth="1.2"
              strokeDasharray="3 3"
            />
            <rect
              x={padLeft + plotW + 4}
              y={yProjected - 9}
              width={136}
              height={18}
              rx="3"
              fill="rgba(56, 189, 248, 0.16)"
              stroke="#38bdf8"
              strokeWidth="0.8"
            />
            <text
              x={padLeft + plotW + 10}
              y={yProjected + 3.5}
              fill="#38bdf8"
              fontSize="9.5"
              fontWeight="700"
              fontFamily="monospace"
            >
              ★ WAVE EXT ₹{projectedTarget.toFixed(2)}
            </text>
          </g>
        )}

        {/* Active Target / Exit Zone Line */}
        <line
          x1={padLeft}
          x2={padLeft + plotW}
          y1={yTarget}
          y2={yTarget}
          stroke="#4caf50"
          strokeWidth="1.5"
          strokeDasharray="5 3"
        />
        <rect
          x={padLeft + plotW + 4}
          y={yTarget - 9}
          width={136}
          height={18}
          rx="3"
          fill="rgba(76, 175, 80, 0.18)"
          stroke="#4caf50"
          strokeWidth="0.8"
        />
        <text
          x={padLeft + plotW + 10}
          y={yTarget + 3.5}
          fill="#4caf50"
          fontSize="10"
          fontWeight="700"
          fontFamily="monospace"
        >
          ▼ EXIT TGT ₹{t.currentTarget.toFixed(2)}
        </text>

        {/* Entry Line */}
        <line
          x1={padLeft}
          x2={padLeft + plotW}
          y1={yEntry}
          y2={yEntry}
          stroke="#94a3b8"
          strokeWidth="1.2"
          strokeDasharray="3 3"
        />
        <text
          x={padLeft + plotW + 6}
          y={yEntry + 3.5}
          fill="#cbd5e1"
          fontSize="10"
          fontWeight="600"
          fontFamily="monospace"
        >
          ▲ ENTRY ₹{t.entryAt.toFixed(2)}
        </text>

        {/* Active Trailing Stop-Loss Line */}
        <line
          x1={padLeft}
          x2={padLeft + plotW}
          y1={yStop}
          y2={yStop}
          stroke={slLockedProfit ? "#22c55e" : "#ef5350"}
          strokeWidth="1.6"
          strokeDasharray="4 2"
        />
        <rect
          x={padLeft + plotW + 4}
          y={yStop - 9}
          width={136}
          height={18}
          rx="3"
          fill={slLockedProfit ? "rgba(34, 197, 94, 0.18)" : "rgba(239, 83, 80, 0.18)"}
          stroke={slLockedProfit ? "#22c55e" : "#ef5350"}
          strokeWidth="0.8"
        />
        <text
          x={padLeft + plotW + 10}
          y={yStop + 3.5}
          fill={slLockedProfit ? "#22c55e" : "#ef5350"}
          fontSize="10"
          fontWeight="700"
          fontFamily="monospace"
        >
          ■ SL EXIT ₹{t.currentStop.toFixed(2)}
        </text>

        {/* Candlesticks & Volume Bars (when 1m bars exist) */}
        {bars.length >= 3 ? (
          bars.map((b, idx) => {
            const step = plotW / Math.max(1, bars.length);
            const cx = padLeft + idx * step + step * 0.5;
            const bw = Math.max(4, Math.min(13, step * 0.65));
            const up = b.c >= b.o;
            const color = up ? "#4caf50" : "#ef5350";
            const yHigh = yFor(b.h);
            const yLow = yFor(b.l);
            const yOpen = yFor(b.o);
            const yClose = yFor(b.c);
            const top = Math.min(yOpen, yClose);
            const bodyH = Math.max(2, Math.abs(yClose - yOpen));
            const vH = ((b.v ?? 0) / maxVol) * 28;
            return (
              <g key={b.t || idx}>
                <line x1={cx} x2={cx} y1={yHigh} y2={yLow} stroke={color} strokeWidth="1.1" />
                <rect x={cx - bw / 2} y={top} width={bw} height={bodyH} fill={color} rx="1" />
                <rect
                  x={cx - bw / 2}
                  y={height - 8 - vH}
                  width={bw}
                  height={vH}
                  fill={up ? "rgba(76, 175, 80, 0.32)" : "rgba(239, 83, 80, 0.32)"}
                />
              </g>
            );
          })
        ) : (
          /* Synthesized Live Price Trajectory Curve when 1m bars are not yet available */
          <g>
            <polyline
              fill="none"
              stroke="#38bdf8"
              strokeWidth="2.2"
               points={polyPoints}
            />
            {trailPoints.map((px, i) => {
              const cx =
                padLeft +
                (trailPoints.length <= 1
                  ? plotW * 0.5
                  : (i / (trailPoints.length - 1)) * (plotW * 0.88));
              const cy = yFor(px);
              return (
                <circle
                  key={i}
                  cx={cx}
                  cy={cy}
                  r={i === trailPoints.length - 1 ? 4.5 : 3}
                  fill={i === 0 ? "#cbd5e1" : "#38bdf8"}
                />
              );
            })}
          </g>
        )}

        {/* Entry Marker Pin on Left of Plot */}
        <g>
          <circle cx={padLeft + 10} cy={yEntry} r="4" fill="#38bdf8" />
          <text
            x={padLeft + 18}
            y={yEntry - 5}
            fill="#e2e8f0"
            fontSize="10"
            fontWeight="700"
            fontFamily="monospace"
          >
            BUY ENTRY @ ₹{t.entryAt.toFixed(2)}
          </text>
        </g>

        {/* Live LTP or Exited Price Line & Marker Pin */}
        <line
          x1={padLeft}
          x2={padLeft + plotW}
          y1={yLtp}
          y2={yLtp}
          stroke={isExited ? "#a855f7" : exitSignal ? "#ff9800" : "#38bdf8"}
          strokeWidth="1.4"
        />
        <circle
          cx={lastPointX}
          cy={yLtp}
          r="5"
          fill={isExited ? "#a855f7" : exitSignal ? "#ff9800" : "#38bdf8"}
        />
        <rect
          x={padLeft + plotW + 4}
          y={yLtp - 9}
          width={136}
          height={18}
          rx="3"
          fill={
            isExited
              ? "rgba(168, 85, 247, 0.22)"
              : exitSignal
                ? "rgba(255, 152, 0, 0.25)"
                : "rgba(56, 189, 248, 0.2)"
          }
          stroke={isExited ? "#a855f7" : exitSignal ? "#ff9800" : "#38bdf8"}
          strokeWidth="0.9"
        />
        <text
          x={padLeft + plotW + 10}
          y={yLtp + 3.5}
          fill={isExited ? "#e9d5ff" : exitSignal ? "#ffb74d" : "#38bdf8"}
          fontSize="10"
          fontWeight="700"
          fontFamily="monospace"
        >
          {isExited
            ? `✓ EXITED ₹${(t.exitPrice ?? t.lastPrice).toFixed(2)}`
            : exitSignal
              ? `★ EXIT NOW ₹${t.lastPrice.toFixed(2)}`
              : `● LIVE ₹${t.lastPrice.toFixed(2)}`}
        </text>
      </svg>

      {/* Bottom Legend & Exit Guidance Strip */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "var(--space-2)",
          marginTop: "var(--space-2)",
          paddingTop: "var(--space-2)",
          borderTop: "1px solid var(--border-subtle)",
          fontSize: "0.75rem",
        }}
      >
        <div style={{ display: "flex", gap: "var(--space-4)", flexWrap: "wrap" }}>
          <span className="mono text-secondary">
            ▲ <strong>Entry:</strong> {formatRupee(t.entryAt)}
          </span>
          <span className="mono text-red">
            ■ <strong>Stop Exit Mark:</strong> {formatRupee(t.currentStop)}
          </span>
          <span className="mono text-green">
            ▼ <strong>Target Exit Mark:</strong> {formatRupee(t.currentTarget)}
          </span>
          <span className="mono text-secondary">
            ★ <strong>Peak:</strong> {formatRupee(t.peakPrice)}
          </span>
        </div>
        <div className="micro text-secondary">
          <strong>Trader Guidance:</strong>{" "}
          {t.marketTelemetry.exitRecommendation ??
            "Holding position — monitoring 1m candle structure & volume for SL ratchet / exit."}
        </div>
      </div>
    </div>
  );
};
