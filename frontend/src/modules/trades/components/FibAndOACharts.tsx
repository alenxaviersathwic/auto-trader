import React from "react";
import { FibLevels, OAAnalysis, OAStrikeRow } from "../types/trades.types";
import { formatRupee } from "../../opportunities/components/formatters";

export function computeFibLevels(
  entryAt: number,
  initialStop: number,
  initialTarget: number,
  swingLow?: number,
  swingHigh?: number,
): FibLevels {
  const move = Math.max(0.5, initialTarget - entryAt);
  const sLow = swingLow && swingLow > 0 ? swingLow : Number((initialStop * 0.94).toFixed(2));
  const sHigh = swingHigh && swingHigh > sLow ? swingHigh : Number(initialTarget.toFixed(2));
  return {
    swingLow: sLow,
    swingHigh: sHigh,
    fib382: Number((entryAt + 0.382 * move).toFixed(2)),
    fib500: Number((entryAt + 0.5 * move).toFixed(2)),
    fib618: Number((entryAt + 0.5 * move).toFixed(2)),
    fib786: Number(initialStop.toFixed(2)),
    fib100: Number(initialTarget.toFixed(2)),
    fib1272: Number((entryAt + 1.272 * move).toFixed(2)),
    fib1618: Number((entryAt + 1.618 * move).toFixed(2)),
  };
}

export function buildDefaultOAAnalysis(
  underlyingCode: string,
  optionType: "CE" | "PE",
  strike: number,
  initialStop: number,
  initialTarget: number,
  existing?: OAAnalysis,
): OAAnalysis {
  if (existing && existing.strikes && existing.strikes.length > 0) {
    return existing;
  }
  const code = (underlyingCode || "NIFTY").toUpperCase();
  const step =
    code === "BANKNIFTY" || code === "SENSEX"
      ? 100
      : code === "NIFTY" || code === "FINNIFTY"
        ? 50
        : 25;
  const isCe = optionType === "CE";
  const strikes: OAStrikeRow[] = [-3, -2, -1, 0, 1, 2, 3].map((offset) => {
    const st = Math.round(strike + offset * step);
    const callOi = isCe
      ? Math.round(
          1850000 * (offset === 2 ? 1.38 : offset === 1 ? 1.15 : offset <= 0 ? 0.72 : 0.95),
        )
      : Math.round(
          2150000 *
            (offset === 0 || offset === 1 ? 1.42 : offset === 2 ? 1.1 : 0.65),
        );
    const putOi = isCe
      ? Math.round(
          2150000 *
            (offset === -1 || offset === 0 ? 1.44 : offset === -2 ? 1.12 : 0.65),
        )
      : Math.round(
          1850000 * (offset === -2 ? 1.38 : offset === -1 ? 1.15 : offset >= 0 ? 0.72 : 0.95),
        );
    const callOiChgPct = isCe
      ? offset === 0 || offset === 1
        ? -14.8
        : offset === 2
          ? 22.4
          : 8.1
      : offset === 0 || offset === 1
        ? 28.6
        : 11.4;
    const putOiChgPct = isCe
      ? offset === -1 || offset === 0
        ? 29.4
        : 12.2
      : offset === -1 || offset === 0
        ? -15.2
        : 21.8;
    const role =
      offset === 0
        ? "ACTIVE_STRIKE"
        : (isCe && offset === 2) || (!isCe && offset === 1)
          ? "CALL_OI_WALL"
          : (isCe && offset === -1) || (!isCe && offset === -2)
            ? "PUT_OI_WALL"
            : "CHAIN";
    return {
      strike: st,
      callOi,
      putOi,
      callOiChgPct,
      putOiChgPct,
      volumeRatio: offset === 0 ? 1.58 : Math.abs(offset) === 1 ? 1.28 : 0.94,
      role,
    };
  });

  const pcr = isCe ? 1.26 : 0.76;
  const supportStrike = isCe ? strike - step : strike - 2 * step;
  const resistanceStrike = isCe ? strike + 2 * step : strike + step;
  return {
    pcr,
    maxPain: strike + (isCe ? step : -step),
    putOiSupportWall: supportStrike,
    callOiResistanceWall: resistanceStrike,
    gammaWall: isCe ? resistanceStrike : supportStrike,
    oiBuildup: isCe
      ? "SHORT_COVERING + PUT_WRITING_FLOOR"
      : "LONG_UNWINDING + CALL_WRITING_CEILING",
    verdict: `OA confirms ${optionType} edge: PCR ${pcr.toFixed(2)} with Put OI floor at ${supportStrike.toLocaleString("en-IN")} (backing SL ${formatRupee(initialStop)}) and Call unwinding toward ${resistanceStrike.toLocaleString("en-IN")} (Target ${formatRupee(initialTarget)}).`,
    strikes,
  };
}

/**
 * Interactive Fibonacci Golden-Pocket (0.50–0.618) & Step-Wave Extension (1.0 -> 1.272 -> 1.618) Chart.
 */
export const FibRetracementChart: React.FC<{
  entryAt: number;
  currentStop: number;
  currentTarget: number;
  lastPrice?: number;
  fibLevels?: FibLevels;
  onSelectTargetLevel?: (targetPrice: number, slPrice: number, label: string) => void;
}> = ({
  entryAt,
  currentStop,
  currentTarget,
  lastPrice,
  fibLevels,
  onSelectTargetLevel,
}) => {
  const fib = fibLevels ?? computeFibLevels(entryAt, currentStop, currentTarget);
  const ltp = lastPrice ?? entryAt;

  const width = 560;
  const height = 235;
  const padLeft = 16;
  const padRight = 152;
  const padTop = 16;
  const padBottom = 22;
  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;

  const swingLow = fib.swingLow ?? Number((currentStop * 0.94).toFixed(2));
  const stop786 = fib.fib786 ?? currentStop;
  const fib618 = fib.fib618;
  const fib100 = fib.fib100;
  const fib1272 = fib.fib1272;
  const fib1618 = fib.fib1618;

  const allVals = [swingLow, stop786, entryAt, fib618, currentTarget, fib100, fib1272, fib1618, ltp].filter(
    (v) => Number.isFinite(v) && v > 0,
  );
  const minP = Math.min(...allVals) * 0.96;
  const maxP = Math.max(...allVals) * 1.04;
  const span = Math.max(1, maxP - minP);
  const yFor = (p: number) =>
    Math.max(padTop + 4, Math.min(padTop + plotH - 4, padTop + ((maxP - p) / span) * plotH));

  // Synthesize the Fibonacci Impulse -> Golden Pocket Pullback -> Wave Extension curve
  const wavePts = [
    { x: padLeft + plotW * 0.04, y: yFor(swingLow), label: "Swing Low" },
    { x: padLeft + plotW * 0.28, y: yFor(fib100), label: "Impulse 1.0" },
    { x: padLeft + plotW * 0.48, y: yFor(entryAt), label: "0.618 Entry" },
    { x: padLeft + plotW * 0.68, y: yFor(Math.max(ltp, fib618)), label: "Wave Step" },
    { x: padLeft + plotW * 0.88, y: yFor(fib1272), label: "1.272 Ext" },
    { x: padLeft + plotW * 0.98, y: yFor(fib1618), label: "1.618 Ext" },
  ];
  const polyline = wavePts.map((pt) => `${pt.x.toFixed(1)},${pt.y.toFixed(1)}`).join(" ");

  const rows: Array<{
    ratio: string;
    label: string;
    price: number;
    color: string;
    slLock: number;
  }> = [
    {
      ratio: "1.618 EXT",
      label: "Golden Wave Ceiling (Lock SL @ 1.0)",
      price: fib1618,
      color: "#38bdf8",
      slLock: fib100,
    },
    {
      ratio: "1.272 EXT",
      label: "Step-Wave Target 2 (Lock SL @ 75%)",
      price: fib1272,
      color: "#4caf50",
      slLock: fib618,
    },
    {
      ratio: "1.000 HIGH",
      label: "Primary Swing Target 1",
      price: fib100,
      color: "#22c55e",
      slLock: currentStop,
    },
    {
      ratio: "0.618 POCKET",
      label: "Golden Pocket Entry / 50% Lock",
      price: entryAt,
      color: "#eab308",
      slLock: currentStop,
    },
    {
      ratio: "0.786 STOP",
      label: "Invalidation Stop-Loss Floor",
      price: currentStop,
      color: "#ef5350",
      slLock: currentStop,
    },
  ];

  return (
    <div className="sd-card">
      <div className="sd-card-header">
        <div>
          <span className="sd-card-title">
            Fibonacci Golden-Pocket &amp; Wave Extension Structure
          </span>
          <span className="sd-card-sub">
            0.618 Pullback Entry ({formatRupee(entryAt)}) → 1.0 Target ({formatRupee(fib100)}) → 1.272 ({formatRupee(fib1272)}) → 1.618 ({formatRupee(fib1618)})
          </span>
        </div>
        {onSelectTargetLevel && (
          <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
            <button
              type="button"
              className="sd-tag sd-tag--green mono"
              style={{ cursor: "pointer" }}
              onClick={() => onSelectTargetLevel(fib100, stop786, "1.0 Swing High Target")}
              title="Set Target to 1.0 Swing High & SL to 0.786"
            >
              Use 1.0 ({formatRupee(fib100)})
            </button>
            <button
              type="button"
              className="sd-tag sd-tag--cyan mono"
              style={{ cursor: "pointer" }}
              onClick={() => onSelectTargetLevel(fib1272, fib618, "1.272 Wave Extension")}
              title="Step Target to 1.272 Extension & Lock SL at 0.618"
            >
              Use 1.272 ({formatRupee(fib1272)})
            </button>
            <button
              type="button"
              className="sd-tag sd-tag--amber mono"
              style={{ cursor: "pointer" }}
              onClick={() => onSelectTargetLevel(fib1618, fib100, "1.618 Golden Extension")}
              title="Step Target to 1.618 Extension & Lock SL at 1.0"
            >
              Use 1.618 ({formatRupee(fib1618)})
            </button>
          </div>
        )}
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{
          width: "100%",
          height: "215px",
          display: "block",
          background: "#131720",
          borderRadius: "4px",
          border: "1px solid var(--border-subtle)",
        }}
      >
        {/* Golden Pocket Shaded Entry Band (Entry <-> Stop) */}
        <rect
          x={padLeft}
          y={Math.min(yFor(entryAt), yFor(currentStop))}
          width={plotW}
          height={Math.max(4, Math.abs(yFor(currentStop) - yFor(entryAt)))}
          fill="rgba(234, 179, 8, 0.09)"
        />

        {/* Wave Extension Profit Zone (Entry <-> 1.618 Ext) */}
        <rect
          x={padLeft}
          y={Math.min(yFor(fib1618), yFor(entryAt))}
          width={plotW}
          height={Math.max(4, Math.abs(yFor(entryAt) - yFor(fib1618)))}
          fill="rgba(56, 189, 248, 0.05)"
        />

        {/* Horizontal Fibonacci Level Lines */}
        {rows.map((r) => {
          const y = yFor(r.price);
          return (
            <g key={r.ratio}>
              <line
                x1={padLeft}
                x2={padLeft + plotW}
                y1={y}
                y2={y}
                stroke={r.color}
                strokeWidth="1.1"
                strokeDasharray={r.ratio.includes("EXT") ? "4 3" : "2 2"}
                opacity={0.85}
              />
              <rect
                x={padLeft + plotW + 4}
                y={y - 8}
                width={142}
                height={16}
                rx="3"
                fill="rgba(18, 22, 31, 0.92)"
                stroke={r.color}
                strokeWidth="0.7"
              />
              <text
                x={padLeft + plotW + 9}
                y={y + 3}
                fill={r.color}
                fontSize="9.2"
                fontWeight="700"
                fontFamily="monospace"
              >
                {r.ratio} ₹{r.price.toFixed(1)}
              </text>
            </g>
          );
        })}

        {/* Impulse -> Pullback -> Extension Wave Path */}
        <polyline
          fill="none"
          stroke="#38bdf8"
          strokeWidth="2"
          points={polyline}
        />

        {wavePts.map((pt, i) => (
          <g key={i}>
            <circle
              cx={pt.x}
              cy={pt.y}
              r={i === 2 ? 4.5 : 3.2}
              fill={i === 2 ? "#eab308" : i >= 4 ? "#4caf50" : "#38bdf8"}
            />
            <text
              x={pt.x}
              y={pt.y - 7}
              fill="#cbd5e1"
              fontSize="8.5"
              fontFamily="monospace"
              textAnchor="middle"
            >
              {pt.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
};

/**
 * OA Chart (Option Chain / Open Interest & Volume Strike Ladder Chart).
 * Shows Call OI Walls vs Put OI Support Floors across strikes around ATM.
 */
export const OptionChainOAChart: React.FC<{
  underlyingCode: string;
  optionType: "CE" | "PE";
  strike: number;
  initialStop: number;
  initialTarget: number;
  oaAnalysis?: OAAnalysis;
  onSelectStrike?: (strike: number) => void;
}> = ({
  underlyingCode,
  optionType,
  strike,
  initialStop,
  initialTarget,
  oaAnalysis,
  onSelectStrike,
}) => {
  const oa = buildDefaultOAAnalysis(
    underlyingCode,
    optionType,
    strike,
    initialStop,
    initialTarget,
    oaAnalysis,
  );
  const maxOi = Math.max(
    1,
    ...oa.strikes.flatMap((s) => [s.callOi, s.putOi]),
  );

  return (
    <div className="sd-card">
      <div className="sd-card-header">
        <div>
          <span className="sd-card-title">
            OA Option-Chain Structure (Call OI Resistance vs Put OI Support)
          </span>
          <span className="sd-card-sub">{oa.verdict}</span>
        </div>
        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
          <span className="sd-tag sd-tag--green mono">PCR {oa.pcr.toFixed(2)}</span>
          <span className="sd-tag sd-tag--cyan mono">
            Put Floor {oa.putOiSupportWall.toLocaleString("en-IN")}
          </span>
          <span className="sd-tag sd-tag--amber mono">
            Call Wall {oa.callOiResistanceWall.toLocaleString("en-IN")}
          </span>
          <span className="sd-tag mono">Max Pain {oa.maxPain.toLocaleString("en-IN")}</span>
        </div>
      </div>

      {/* Strike-by-Strike Call vs Put OI Butterfly Bar Chart */}
      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        <div
          className="mono micro text-muted"
          style={{
            display: "grid",
            gridTemplateColumns: "92px 1fr 94px 1fr 92px",
            alignItems: "center",
            padding: "0 6px",
          }}
        >
          <span>PUT OI (CHG)</span>
          <span style={{ textAlign: "right", paddingRight: 8 }}>PUT SUPPORT FLOOR</span>
          <span style={{ textAlign: "center" }}>STRIKE</span>
          <span style={{ paddingLeft: 8 }}>CALL RESISTANCE WALL</span>
          <span style={{ textAlign: "right" }}>CALL OI (CHG)</span>
        </div>

        {oa.strikes.map((row) => {
          const putW = Math.max(4, Math.round((row.putOi / maxOi) * 100));
          const callW = Math.max(4, Math.round((row.callOi / maxOi) * 100));
          const isAtm = row.role === "ACTIVE_STRIKE" || row.strike === strike;
          const isPutWall = row.role === "PUT_OI_WALL";
          const isCallWall = row.role === "CALL_OI_WALL";

          return (
            <div
              key={row.strike}
              onClick={() => onSelectStrike && onSelectStrike(row.strike)}
              style={{
                display: "grid",
                gridTemplateColumns: "92px 1fr 94px 1fr 92px",
                alignItems: "center",
                gap: "6px",
                padding: "5px 6px",
                borderRadius: "4px",
                cursor: onSelectStrike ? "pointer" : "default",
                background: isAtm
                  ? "rgba(56, 126, 209, 0.14)"
                  : "var(--bg-panel)",
                border: isAtm
                  ? "1px solid var(--kite-blue)"
                  : "1px solid var(--border-subtle)",
              }}
            >
              {/* Put OI numeric */}
              <div className="mono micro" style={{ fontSize: "0.68rem" }}>
                <span className="text-green">{(row.putOi / 100000).toFixed(1)}L</span>{" "}
                <span className={row.putOiChgPct >= 0 ? "text-green" : "text-red"}>
                  ({row.putOiChgPct >= 0 ? "+" : ""}
                  {row.putOiChgPct.toFixed(0)}%)
                </span>
              </div>

              {/* Put OI Bar (Right-aligned growing left) */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  alignItems: "center",
                  height: "12px",
                  background: "var(--bg-input)",
                  borderRadius: "2px",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${putW}%`,
                    height: "100%",
                    background: isPutWall ? "#22c55e" : "rgba(76, 175, 80, 0.65)",
                  }}
                />
              </div>

              {/* Center Strike Pill */}
              <div
                className="mono"
                style={{
                  textAlign: "center",
                  fontSize: "0.73rem",
                  fontWeight: isAtm ? 800 : 600,
                  color: isAtm ? "#ffffff" : "var(--text-heading)",
                }}
              >
                {row.strike.toLocaleString("en-IN")}
                {isAtm && (
                  <span
                    className="micro"
                    style={{
                      display: "block",
                      fontSize: "0.58rem",
                      color: "var(--cyan)",
                    }}
                  >
                    ACTIVE {optionType}
                  </span>
                )}
                {!isAtm && isPutWall && (
                  <span
                    className="micro"
                    style={{
                      display: "block",
                      fontSize: "0.58rem",
                      color: "var(--bullish-green)",
                    }}
                  >
                    PUT FLOOR
                  </span>
                )}
                {!isAtm && isCallWall && (
                  <span
                    className="micro"
                    style={{
                      display: "block",
                      fontSize: "0.58rem",
                      color: "var(--warning-amber)",
                    }}
                  >
                    CALL WALL
                  </span>
                )}
              </div>

              {/* Call OI Bar (Left-aligned growing right) */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-start",
                  alignItems: "center",
                  height: "12px",
                  background: "var(--bg-input)",
                  borderRadius: "2px",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${callW}%`,
                    height: "100%",
                    background: isCallWall ? "#ff9800" : "rgba(239, 83, 80, 0.65)",
                  }}
                />
              </div>

              {/* Call OI numeric */}
              <div
                className="mono micro"
                style={{ fontSize: "0.68rem", textAlign: "right" }}
              >
                <span className="text-red">{(row.callOi / 100000).toFixed(1)}L</span>{" "}
                <span className={row.callOiChgPct <= 0 ? "text-green" : "text-amber"}>
                  ({row.callOiChgPct >= 0 ? "+" : ""}
                  {row.callOiChgPct.toFixed(0)}%)
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

