import React from "react";
import { ActiveTrade, OAStrikeRow } from "../types/trades.types";
import { formatRupee } from "../../opportunities/components/formatters";

function computeRsi14(closes: number[]): number[] {
  if (closes.length < 2) return [];
  const rsi: number[] = new Array(closes.length).fill(50);
  let avgGain = 0;
  let avgLoss = 0;
  const period = Math.min(14, Math.max(2, closes.length - 1));
  for (let i = 1; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? -diff : 0;
    if (i <= period) {
      avgGain += gain / period;
      avgLoss += loss / period;
    } else {
      avgGain = (avgGain * (period - 1) + gain) / period;
      avgLoss = (avgLoss * (period - 1) + loss) / period;
    }
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    rsi[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + rs);
  }
  return rsi;
}

/**
 * Real-Data 1m Option Premium Scalper Chart:
 * - Renders ONLY real 1m candles from Upstox (`t.candles1m`), real Entry / Trailing SL / Target levels,
 *   and real OA / Max Pain / RSI(14) when real data exists (no synthetic/simulated data).
 */
export const TradePremiumChart: React.FC<{ trade: ActiveTrade }> = ({ trade: t }) => {
  const bars = t.candles1m.slice(-45);
  const hasRealCandles = bars.length >= 2;
  const realOa = t.marketTelemetry?.oaAnalysis;
  const hasRealOa = Boolean(realOa && realOa.strikes && realOa.strikes.length > 0);

  const width = 840;
  const height = hasRealCandles ? 360 : 270;
  const padLeft = 18;
  const padRight = 154;
  const padTop = 20;
  const mainH = hasRealCandles ? 236 : 210;
  const rsiTop = 274;
  const rsiH = 66;
  const plotW = width - padLeft - padRight;

  const projectedTarget = Number(t.marketTelemetry?.projectedTarget || 0);
  const hasProjectedCeiling = projectedTarget > t.currentTarget + 0.5;

  const prices = [
    t.initialStop,
    t.currentStop,
    t.entryAt,
    t.currentTarget,
    ...(hasProjectedCeiling ? [projectedTarget] : []),
    t.peakPrice,
    t.lastPrice,
    ...(t.exitPrice ? [t.exitPrice] : []),
    ...bars.flatMap((b) => [b.h, b.l]),
  ].filter((p) => Number.isFinite(p) && p > 0);

  const minP = Math.min(...prices) * 0.96;
  const maxP = Math.max(...prices) * 1.04;
  const spanP = Math.max(1.0, maxP - minP);
  const yFor = (p: number) =>
    Math.max(padTop + 4, Math.min(padTop + mainH - 4, padTop + ((maxP - p) / spanP) * mainH));

  const maxVol = Math.max(1, ...bars.map((b) => b.v ?? 0));

  const yTarget = yFor(t.currentTarget);
  const yProjected = hasProjectedCeiling ? yFor(projectedTarget) : yTarget;
  const yEntry = yFor(t.entryAt);
  const yStop = yFor(t.currentStop);
  const yInitStop = yFor(t.initialStop);
  const yLtp = yFor(t.exitPrice ?? t.lastPrice);

  const slLockedProfit = t.currentStop > t.entryAt;
  const exitSignal = t.marketTelemetry.exitSignal;
  const isExited = t.tradeState === "EXITED";

  const boxStartX = hasRealCandles ? padLeft + plotW * 0.6 : padLeft + 12;
  const boxWidth = padLeft + plotW - boxStartX;

  const lastPointX = hasRealCandles
    ? padLeft + ((bars.length - 0.5) / bars.length) * plotW
    : padLeft + plotW * 0.85;

  const rsiSeries = React.useMemo(
    () => (hasRealCandles ? computeRsi14(bars.map((b) => b.c)) : []),
    [hasRealCandles, bars],
  );
  const currentRsi = rsiSeries.length > 0 ? rsiSeries[rsiSeries.length - 1] : null;
  const rsiPoints = rsiSeries
    .map((val, i) => {
      const x =
        padLeft +
        (rsiSeries.length <= 1 ? plotW * 0.5 : (i / (rsiSeries.length - 1)) * (plotW * 0.96));
      const y = rsiTop + ((100 - Math.max(0, Math.min(100, val))) / 100) * rsiH;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const maxOi = hasRealOa && realOa
    ? Math.max(1, ...realOa.strikes.flatMap((s: OAStrikeRow) => [s.callOi, s.putOi]))
    : 1;

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
            Live 1m Scalper Chart · Entry, Trailing SL &amp; Target
          </span>
          <span className="micro text-muted" style={{ marginLeft: "var(--space-2)" }}>
            1m Structure: <strong>{t.marketTelemetry.candleStructure ?? "NEUTRAL"}</strong> · Vol:{" "}
            <strong>{t.marketTelemetry.volumeRatio ?? 1}x</strong>
            {currentRsi !== null && (
              <>
                {" "}
                · RSI(14):{" "}
                <strong className={currentRsi >= 55 ? "text-green" : currentRsi <= 45 ? "text-red" : ""}>
                  {currentRsi.toFixed(1)}
                </strong>
              </>
            )}
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
            {bars.length > 0 ? `${bars.length} × 1m candles (Upstox)` : "Waiting for live 1m candles"}
          </span>
        </div>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{
          width: "100%",
          height: hasRealCandles ? "350px" : "260px",
          display: "block",
          background: "#131720",
          borderRadius: "4px",
          border: "1px solid var(--border-subtle)",
        }}
      >
        {/* Real Risk-Reward Position Box */}
        <rect
          x={boxStartX}
          y={Math.min(yTarget, yEntry)}
          width={boxWidth}
          height={Math.max(4, Math.abs(yEntry - yTarget))}
          fill="rgba(34, 197, 94, 0.12)"
        />
        <rect
          x={boxStartX}
          y={Math.min(yEntry, yInitStop)}
          width={boxWidth}
          height={Math.max(4, Math.abs(yInitStop - yEntry))}
          fill="rgba(239, 83, 80, 0.12)"
        />
        {slLockedProfit && (
          <rect
            x={boxStartX}
            y={Math.min(yStop, yEntry)}
            width={boxWidth}
            height={Math.max(3, Math.abs(yStop - yEntry))}
            fill="rgba(34, 197, 94, 0.22)"
          />
        )}

        {/* Real Right-Edge OI Profile Bars (only when real OA telemetry is present) */}
        {hasRealOa &&
          realOa &&
          realOa.strikes.map((row: OAStrikeRow, idx: number) => {
            const yBand = padTop + 20 + (idx / Math.max(1, realOa.strikes.length - 1)) * (mainH - 40);
            const putW = Math.max(4, (row.putOi / maxOi) * 44);
            const callW = Math.max(4, (row.callOi / maxOi) * 44);
            return (
              <g key={row.strike} opacity={0.55}>
                <rect x={padLeft + plotW - callW} y={yBand - 4} width={callW} height={3.5} fill="#ef5350" rx="1" />
                <rect x={padLeft + plotW - putW} y={yBand + 0.5} width={putW} height={3.5} fill="#4caf50" rx="1" />
              </g>
            );
          })}

        {/* Projected Wave Extension Ceiling Line */}
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
              width={142}
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

        {/* Active Target Line */}
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
          width={142}
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

        {/* Active Trailing SL Line */}
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
          width={142}
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

        {/* Real 1m Candlesticks & Volume Bars */}
        {hasRealCandles ? (
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
            const vH = ((b.v ?? 0) / maxVol) * 24;
            return (
              <g key={b.t || idx}>
                <line x1={cx} x2={cx} y1={yHigh} y2={yLow} stroke={color} strokeWidth="1.1" />
                <rect x={cx - bw / 2} y={top} width={bw} height={bodyH} fill={color} rx="1" />
                <rect
                  x={cx - bw / 2}
                  y={padTop + mainH - vH}
                  width={bw}
                  height={vH}
                  fill={up ? "rgba(76, 175, 80, 0.28)" : "rgba(239, 83, 80, 0.28)"}
                />
              </g>
            );
          })
        ) : (
          <text
            x={padLeft + plotW * 0.5}
            y={padTop + mainH * 0.5}
            fill="#64748b"
            fontSize="12"
            fontFamily="monospace"
            textAnchor="middle"
          >
            Waiting for live Upstox 1m candles (plotting real Entry / SL / Target / LTP levels)
          </text>
        )}

        {/* Live LTP Line & Marker */}
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
          r="4.5"
          fill={isExited ? "#a855f7" : exitSignal ? "#ff9800" : "#38bdf8"}
        />
        <rect
          x={padLeft + plotW + 4}
          y={yLtp - 9}
          width={142}
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

        {/* Real RSI(14) Sub-Panel (only when real 1m candles exist) */}
        {hasRealCandles && rsiSeries.length >= 2 && (
          <g>
            <line x1={padLeft} x2={padLeft + plotW} y1={rsiTop - 8} y2={rsiTop - 8} stroke="#262626" strokeWidth="1" />
            <rect
              x={padLeft}
              y={rsiTop + 0.3 * rsiH}
              width={plotW}
              height={0.4 * rsiH}
              fill="rgba(168, 85, 247, 0.08)"
            />
            <line
              x1={padLeft}
              x2={padLeft + plotW}
              y1={rsiTop + 0.3 * rsiH}
              y2={rsiTop + 0.3 * rsiH}
              stroke="rgba(148, 163, 184, 0.28)"
              strokeDasharray="2 3"
            />
            <line
              x1={padLeft}
              x2={padLeft + plotW}
              y1={rsiTop + 0.7 * rsiH}
              y2={rsiTop + 0.7 * rsiH}
              stroke="rgba(148, 163, 184, 0.28)"
              strokeDasharray="2 3"
            />
            <polyline fill="none" stroke="#a855f7" strokeWidth="1.5" points={rsiPoints} />
            <text x={padLeft + 6} y={rsiTop + 10} fill="#94a3b8" fontSize="9.5" fontFamily="monospace">
              RSI 14{" "}
              <tspan fill="#c084fc" fontWeight="700">
                {(currentRsi ?? 50).toFixed(2)}
              </tspan>
            </text>
            <text x={padLeft + plotW + 8} y={rsiTop + 0.3 * rsiH + 3} fill="#64748b" fontSize="9" fontFamily="monospace">
              70.00
            </text>
            <text x={padLeft + plotW + 8} y={rsiTop + 0.7 * rsiH + 3} fill="#64748b" fontSize="9" fontFamily="monospace">
              30.00
            </text>
          </g>
        )}
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
            ■ <strong>SL:</strong> {formatRupee(t.currentStop)}
          </span>
          <span className="mono text-green">
            ▼ <strong>Target:</strong> {formatRupee(t.currentTarget)}
          </span>
          <span className="mono text-secondary">
            ★ <strong>Peak:</strong> {formatRupee(t.peakPrice)}
          </span>
        </div>
        <div className="micro text-secondary">
          <strong>Trader Guidance:</strong>{" "}
          {t.marketTelemetry.exitRecommendation ??
            "Monitoring live 1m Upstox candles & volume every second."}
        </div>
      </div>
    </div>
  );
};
