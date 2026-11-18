import React, { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Play, RefreshCw, RotateCcw, X } from "lucide-react";
import { opportunitiesApi } from "../../opportunity-finder/api/opportunities.api";
import { useUnderlyingChart } from "../../opportunity-finder/hooks/useOpportunities";
import { ChartTimeframe, UnderlyingBar5 } from "../../opportunity-finder/types/opportunities.types";
import { TRADER_META } from "../../trade-history/components/traderMeta";
import { TraderCode } from "../../trade-history/types/trades.types";

interface Props {
  code: string;
  finderCodes?: TraderCode[];
  onClose: () => void;
}

const TIMEFRAMES: ChartTimeframe[] = ["1m", "5m", "15m", "1h"];
const FIB_RATIOS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0];

const fmtTime = (iso: string): string => {
  if (!iso) return "";
  const m = iso.match(/T(\d{2}:\d{2})/);
  return m ? m[1] : iso.slice(11, 16);
};

const fmtPrice = (v: number): string =>
  v >= 1000 ? v.toLocaleString("en-IN", { maximumFractionDigits: 1 }) : v.toFixed(2);

const STAGE_STYLE: Record<string, { label: string; cls: string }> = {
  IN_POCKET: { label: "IN POCKET", cls: "te-pill--green" },
  SHALLOW: { label: "WAITING POCKET", cls: "badge--blue" },
  STALE: { label: "STALE", cls: "badge--amber" },
  FAILED: { label: "SWING FAILED", cls: "te-pill--red" },
  NO_SWING: { label: "NO SWING", cls: "" },
};

export const UnderlyingChartModal: React.FC<Props> = ({ code, finderCodes, onClose }) => {
  const finders: TraderCode[] =
    finderCodes && finderCodes.length > 0 ? finderCodes : ["FIB_GOLDEN_TRADER", "FLOW_MOMENTUM_TRADER"];
  const [activeFinder, setActiveFinder] = useState<TraderCode>(finders[0]);
  const [timeframe, setTimeframe] = useState<ChartTimeframe>("5m");
  const { data, isLoading, isFetching, refetch } = useUnderlyingChart(code, timeframe);
  const [scanning, setScanning] = useState(false);

  // Overlay toggles (auto-configured per finder specialty, user can also toggle manually)
  const [showFib, setShowFib] = useState(activeFinder === "FIB_GOLDEN_TRADER");
  const [showEma, setShowEma] = useState(true);
  const [showVwap, setShowVwap] = useState(activeFinder !== "FIB_GOLDEN_TRADER");
  const [showLevels, setShowLevels] = useState(true);
  const [showNoise, setShowNoise] = useState(activeFinder === "FLOW_MOMENTUM_TRADER");

  const selectFinder = (f: TraderCode) => {
    setActiveFinder(f);
    if (f === "FIB_GOLDEN_TRADER") {
      setShowFib(true);
      setShowNoise(false);
      setShowVwap(false);
      setShowEma(true);
      setShowLevels(true);
    } else if (f === "FLOW_MOMENTUM_TRADER") {
      setShowFib(false);
      setShowNoise(true);
      setShowVwap(true);
      setShowEma(true);
      setShowLevels(true);
    } else {
      setShowFib(false);
      setShowNoise(false);
      setShowVwap(true);
      setShowEma(true);
      setShowLevels(true);
    }
  };

  // Zoom / Pan state (slice over allBars)
  const [viewCount, setViewCount] = useState<number>(80);
  const [panRightOffset, setPanRightOffset] = useState<number>(0);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [hoverY, setHoverY] = useState<number | null>(null);
  const dragRef = useRef<{ startX: number; startOffset: number } | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    setPanRightOffset(0);
    setViewCount(80);
    setHoverIdx(null);
  }, [code, timeframe]);

  const allBars = data?.bars5 ?? [];
  const allEma9 = data?.ema9 ?? [];
  const allEma21 = data?.ema21 ?? [];

  const total = allBars.length;
  const clampedCount = Math.max(15, Math.min(total || 80, viewCount));
  const maxOffset = Math.max(0, total - clampedCount);
  const safeOffset = Math.max(0, Math.min(maxOffset, panRightOffset));
  const endIdx = total - safeOffset;
  const startIdx = Math.max(0, endIdx - clampedCount);

  const bars = allBars.slice(startIdx, endIdx);
  const ema9 = allEma9.slice(startIdx, endIdx);
  const ema21 = allEma21.slice(startIdx, endIdx);
  const primaryFib = data?.fibWatch?.[0];

  const fibLines = useMemo(() => {
    if (!showFib || !primaryFib?.swingLow || !primaryFib?.swingHigh) return [];
    const lo = primaryFib.swingLow;
    const hi = primaryFib.swingHigh;
    const move = hi - lo;
    if (move <= 0) return [];
    const up = primaryFib.side === "CE";
    return FIB_RATIOS.map((r) => {
      const price = up ? hi - r * move : lo + r * move;
      const isPocket = r === 0.5 || r === 0.618;
      const isStop = r === 0.786;
      return {
        ratio: r,
        label: `Fib ${r.toFixed(3).replace(/0+$/, "").replace(/\.$/, "")}`,
        price,
        color: isPocket ? "#38bdf8" : isStop ? "#ef4444" : "#64748b",
        bold: isPocket || isStop,
      };
    });
  }, [showFib, primaryFib]);

  const chart = useMemo(() => {
    if (bars.length === 0) return null;
    const W = 820;
    const H = 450;
    const padL = 12;
    const padR = 78;
    const padT = 16;
    const padB = 26;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;
    const volH = 44;

    const prices: number[] = [];
    bars.forEach((b) => prices.push(b.h, b.l));
    if (showEma) {
      ema9.forEach((v) => Number.isFinite(v) && prices.push(v));
      ema21.forEach((v) => Number.isFinite(v) && prices.push(v));
    }
    if (showVwap && data?.vwap) prices.push(data.vwap);
    if (showLevels && data?.levels) {
      if (data.levels.orHigh) prices.push(data.levels.orHigh);
      if (data.levels.orLow) prices.push(data.levels.orLow);
    }
    if (data?.spot) prices.push(data.spot);
    if (showFib && primaryFib?.pocket) prices.push(primaryFib.pocket[0], primaryFib.pocket[1]);

    const rawMin = Math.min(...prices);
    const rawMax = Math.max(...prices);
    const pad = Math.max((rawMax - rawMin) * 0.08, rawMax * 0.0008);
    const minP = rawMin - pad;
    const maxP = rawMax + pad;
    const span = Math.max(1e-6, maxP - minP);

    const yFor = (p: number) => padT + ((maxP - p) / span) * plotH;
    const priceForY = (y: number) => maxP - ((y - padT) / plotH) * span;
    const stepX = plotW / Math.max(bars.length, 1);
    const xFor = (i: number) => padL + stepX * (i + 0.5);
    const candleW = Math.max(2.5, Math.min(12, stepX * 0.68));
    const maxVol = Math.max(1, ...bars.map((b) => Number(b.v || 0)));

    const yTicks = [0, 0.2, 0.4, 0.6, 0.8, 1].map((f) => ({ p: maxP - f * span, y: padT + f * plotH }));

    const linePath = (vals: number[]) =>
      vals
        .map((v, i) => (i < bars.length && Number.isFinite(v) ? `${i === 0 ? "M" : "L"}${xFor(i).toFixed(1)},${yFor(v).toFixed(1)}` : ""))
        .filter(Boolean)
        .join(" ");

    return {
      W,
      H,
      padL,
      padR,
      padT,
      padB,
      plotW,
      plotH,
      volH,
      maxVol,
      minP,
      maxP,
      yFor,
      priceForY,
      xFor,
      candleW,
      yTicks,
      ema9Path: linePath(ema9),
      ema21Path: linePath(ema21),
    };
  }, [bars, ema9, ema21, showEma, showVwap, showLevels, showFib, data?.vwap, data?.levels, data?.spot, primaryFib]);

  const activeBar: UnderlyingBar5 | null =
    hoverIdx !== null && bars[hoverIdx] ? bars[hoverIdx] : bars.length ? bars[bars.length - 1] : null;
  const activeIdx = hoverIdx !== null && bars[hoverIdx] ? hoverIdx : bars.length - 1;

  const scan = data?.lastScan;
  const details = scan?.details;
  const rejected = details?.setupsRejected ?? [];
  const fired = details?.setupsFired ?? [];
  const confirmed = details?.setupsConfirmed ?? [];
  const menuDropped = Object.entries(details?.menuDropped ?? {});
  const valDropped = Object.entries(details?.dropped ?? {});
  const nearestContracts = details?.nearestContracts ?? [];

  const keyLines = showLevels
    ? [
        data?.levels?.pdh ? { label: "PDH", price: data.levels.pdh, color: "#f59e0b" } : null,
        data?.levels?.pdl ? { label: "PDL", price: data.levels.pdl, color: "#f59e0b" } : null,
        data?.levels?.orHigh ? { label: "ORH", price: data.levels.orHigh, color: "#38bdf8" } : null,
        data?.levels?.orLow ? { label: "ORL", price: data.levels.orLow, color: "#38bdf8" } : null,
      ].filter((x): x is { label: string; price: number; color: string } => Boolean(x))
    : [];

  const handleScanNow = async () => {
    if (!data?.masterId || scanning) return;
    setScanning(true);
    try {
      await opportunitiesApi.iterate(data.masterId);
      await refetch();
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label={`${code} live chart and agent diagnostics`} onClick={onClose}>
      <div className="modal-card uc-modal" onClick={(e) => e.stopPropagation()}>
        <header className="uc-head">
          <div className="uc-head__left">
            <h2 className="uc-head__title mono">{code}</h2>
            {data?.spot != null && <span className="uc-head__spot mono">{fmtPrice(data.spot)}</span>}
            {data?.regime && <span className="te-pill">{data.regime}</span>}
            {data?.trend15 && (
              <span className={`te-pill ${data.trend15 === "UP" ? "te-pill--green" : data.trend15 === "DOWN" ? "te-pill--red" : ""}`}>
                15m {data.trend15}
              </span>
            )}
            {data?.dayType?.type && (
              <span className="te-pill">
                {data.dayType.type}
                {data.dayType.side ? ` ${data.dayType.side}` : ""}
              </span>
            )}
          </div>
          <div className="uc-head__right">
            <div className="sd-seg-group" role="group" aria-label="Timeframe">
              {TIMEFRAMES.map((tf) => (
                <button
                  key={tf}
                  type="button"
                  className={`sd-seg-btn ${timeframe === tf ? "active" : ""}`}
                  onClick={() => setTimeframe(tf)}
                >
                  {tf}
                </button>
              ))}
            </div>
            {data?.masterId && (
              <button
                type="button"
                className="te-btn te-btn--primary te-btn--xs"
                onClick={handleScanNow}
                disabled={scanning}
                title="Trigger an immediate scanner pass for this underlying"
              >
                <Play size={11} /> {scanning ? "Scanning…" : "Scan Now"}
              </button>
            )}
            <button type="button" className="te-btn te-btn--ghost te-btn--xs" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw size={12} />
            </button>
            <button type="button" className="ss-close" onClick={onClose} aria-label="Close chart">
              <X size={16} />
            </button>
          </div>
        </header>

        <div className="uc-body">
          {/* LEFT: Interactive Trader Chart */}
          <div className="uc-chart-pane">
            <div className="uc-toolbar">
              <div className="uc-ohlc-bar mono micro">
                {activeBar ? (
                  <>
                    <span className="text-muted">{fmtTime(activeBar.t)}</span>
                    <span>O {fmtPrice(activeBar.o)}</span>
                    <span className="text-green">H {fmtPrice(activeBar.h)}</span>
                    <span className="text-red">L {fmtPrice(activeBar.l)}</span>
                    <span className={activeBar.c >= activeBar.o ? "text-green" : "text-red"}>C {fmtPrice(activeBar.c)}</span>
                    {showEma && ema9[activeIdx] != null && <span style={{ color: "#38bdf8" }}>E9 {fmtPrice(ema9[activeIdx])}</span>}
                    {showEma && ema21[activeIdx] != null && <span style={{ color: "#f59e0b" }}>E21 {fmtPrice(ema21[activeIdx])}</span>}
                    {showVwap && data?.vwap != null && <span style={{ color: "#a78bfa" }}>VWAP {fmtPrice(data.vwap)}</span>}
                  </>
                ) : (
                  <span className="text-muted">{timeframe} chart</span>
                )}
              </div>
              <div className="uc-overlays">
                {[
                  { label: "Fib", on: showFib, set: setShowFib },
                  { label: "EMA", on: showEma, set: setShowEma },
                  { label: "VWAP", on: showVwap, set: setShowVwap },
                  { label: "Levels", on: showLevels, set: setShowLevels },
                  { label: "Noise", on: showNoise, set: setShowNoise },
                ].map((ov) => (
                  <button
                    key={ov.label}
                    type="button"
                    className={`toggle-chip ${ov.on ? "toggle-chip--active" : ""}`}
                    onClick={() => ov.set((v) => !v)}
                  >
                    {ov.label}
                  </button>
                ))}
                {(panRightOffset > 0 || viewCount !== 80) && (
                  <button
                    type="button"
                    className="toggle-chip"
                    onClick={() => {
                      setPanRightOffset(0);
                      setViewCount(80);
                    }}
                    title="Reset zoom & scroll to latest bar"
                  >
                    <RotateCcw size={10} />
                  </button>
                )}
              </div>
            </div>

            {isLoading ? (
              <div className="uc-empty">Loading {code} {timeframe} chart…</div>
            ) : !chart ? (
              <div className="uc-empty">
                <AlertTriangle size={18} className="text-amber" />
                <span>{data?.marketError ?? `No intraday ${timeframe} candles available right now.`}</span>
              </div>
            ) : (
              <svg
                className="uc-svg"
                viewBox={`0 0 ${chart.W} ${chart.H}`}
                onWheel={(e) => {
                  e.preventDefault();
                  const delta = e.deltaY > 0 ? 10 : -10;
                  setViewCount((prev) => Math.max(15, Math.min(Math.max(allBars.length, 80), prev + delta)));
                }}
                onMouseDown={(e) => {
                  dragRef.current = { startX: e.clientX, startOffset: safeOffset };
                }}
                onMouseUp={() => {
                  dragRef.current = null;
                }}
                onMouseLeave={() => {
                  dragRef.current = null;
                  setHoverIdx(null);
                  setHoverY(null);
                }}
                onMouseMove={(e) => {
                  const rect = e.currentTarget.getBoundingClientRect();
                  if (dragRef.current) {
                    const dx = e.clientX - dragRef.current.startX;
                    const barsShift = Math.round((dx / Math.max(1, rect.width)) * clampedCount);
                    setPanRightOffset(Math.max(0, Math.min(maxOffset, dragRef.current.startOffset + barsShift)));
                    return;
                  }
                  const relX = ((e.clientX - rect.left) / rect.width) * chart.W;
                  const relY = ((e.clientY - rect.top) / rect.height) * chart.H;
                  const idx = Math.floor(((relX - chart.padL) / chart.plotW) * bars.length);
                  if (idx >= 0 && idx < bars.length) setHoverIdx(idx);
                  if (relY >= chart.padT && relY <= chart.padT + chart.plotH) setHoverY(relY);
                }}
              >
                {/* Grid lines */}
                {chart.yTicks.map((tk, i) => (
                  <g key={i}>
                    <line x1={chart.padL} x2={chart.W - chart.padR} y1={tk.y} y2={tk.y} stroke="rgba(255,255,255,0.06)" strokeWidth={1} />
                    <text x={chart.W - chart.padR + 6} y={tk.y + 3} fill="#64748b" fontSize="10" fontFamily="monospace">
                      {fmtPrice(tk.p)}
                    </text>
                  </g>
                ))}

                {/* Noise Area band */}
                {showNoise && data?.noise?.lower && data.noise.upper && (
                  <rect
                    x={chart.padL}
                    width={chart.plotW}
                    y={Math.max(chart.padT, Math.min(chart.yFor(data.noise.upper), chart.yFor(data.noise.lower)))}
                    height={Math.max(2, Math.abs(chart.yFor(data.noise.lower) - chart.yFor(data.noise.upper)))}
                    fill="rgba(148, 163, 184, 0.07)"
                  />
                )}

                {/* Full Fibonacci Retracement Levels + Golden Pocket */}
                {showFib && primaryFib?.pocket && (
                  <rect
                    x={chart.padL}
                    width={chart.plotW}
                    y={Math.max(chart.padT, Math.min(chart.yFor(primaryFib.pocket[0]), chart.yFor(primaryFib.pocket[1])))}
                    height={Math.max(2, Math.abs(chart.yFor(primaryFib.pocket[0]) - chart.yFor(primaryFib.pocket[1])))}
                    fill="rgba(56, 189, 248, 0.13)"
                  />
                )}
                {fibLines.map((fl) => {
                  if (fl.price < chart.minP || fl.price > chart.maxP) return null;
                  const y = chart.yFor(fl.price);
                  return (
                    <g key={fl.label}>
                      <line
                        x1={chart.padL}
                        x2={chart.W - chart.padR}
                        y1={y}
                        y2={y}
                        stroke={fl.color}
                        strokeOpacity={fl.bold ? 0.75 : 0.38}
                        strokeDasharray={fl.bold ? "4 3" : "2 4"}
                        strokeWidth={fl.bold ? 1.2 : 0.9}
                      />
                      <text x={chart.padL + 6} y={y - 3} fill={fl.color} fontSize="9.5" fontFamily="monospace">
                        {fl.label} ({fmtPrice(fl.price)})
                      </text>
                    </g>
                  );
                })}

                {/* VWAP */}
                {showVwap && data?.vwap != null && data.vwap >= chart.minP && data.vwap <= chart.maxP && (
                  <g>
                    <line x1={chart.padL} x2={chart.W - chart.padR} y1={chart.yFor(data.vwap)} y2={chart.yFor(data.vwap)} stroke="#a78bfa" strokeDasharray="5 3" strokeWidth={1.3} />
                    <text x={chart.W - chart.padR + 6} y={chart.yFor(data.vwap) + 3} fill="#a78bfa" fontSize="9.5" fontFamily="monospace">
                      VWAP
                    </text>
                  </g>
                )}

                {/* Key Levels */}
                {keyLines.map((kl) => {
                  if (kl.price < chart.minP || kl.price > chart.maxP) return null;
                  const y = chart.yFor(kl.price);
                  return (
                    <g key={kl.label}>
                      <line x1={chart.padL} x2={chart.W - chart.padR} y1={y} y2={y} stroke={kl.color} strokeOpacity={0.6} strokeDasharray="4 4" strokeWidth={1} />
                      <text x={chart.W - chart.padR + 6} y={y + 3} fill={kl.color} fontSize="9.5" fontFamily="monospace">
                        {kl.label} {fmtPrice(kl.price)}
                      </text>
                    </g>
                  );
                })}

                {/* Volume Histogram */}
                {bars.map((b, i) => {
                  const v = Number(b.v || 0);
                  if (v <= 0) return null;
                  const h = (v / chart.maxVol) * chart.volH;
                  const up = b.c >= b.o;
                  return (
                    <rect
                      key={`v-${i}`}
                      x={chart.xFor(i) - chart.candleW / 2}
                      y={chart.padT + chart.plotH - h}
                      width={chart.candleW}
                      height={h}
                      fill={up ? "rgba(34, 197, 94, 0.22)" : "rgba(239, 68, 68, 0.22)"}
                    />
                  );
                })}

                {/* EMA21 & EMA9 */}
                {showEma && chart.ema21Path && <path d={chart.ema21Path} fill="none" stroke="#f59e0b" strokeWidth={1.3} strokeOpacity={0.85} />}
                {showEma && chart.ema9Path && <path d={chart.ema9Path} fill="none" stroke="#38bdf8" strokeWidth={1.4} strokeOpacity={0.95} />}

                {/* Candlesticks */}
                {bars.map((b, i) => {
                  const x = chart.xFor(i);
                  const up = b.c >= b.o;
                  const color = up ? "#22c55e" : "#ef4444";
                  const yH = chart.yFor(b.h);
                  const yL = chart.yFor(b.l);
                  const yO = chart.yFor(b.o);
                  const yC = chart.yFor(b.c);
                  const bodyY = Math.min(yO, yC);
                  const bodyH = Math.max(1.5, Math.abs(yO - yC));
                  return (
                    <g key={b.t || i}>
                      <line x1={x} x2={x} y1={yH} y2={yL} stroke={color} strokeWidth={1.1} />
                      <rect x={x - chart.candleW / 2} y={bodyY} width={chart.candleW} height={bodyH} fill={color} rx={0.8} />
                    </g>
                  );
                })}

                {/* Active Setup Entry / Stop / Target Markings */}
                {data?.activeSetups?.[0] && (() => {
                  const s = data.activeSetups[0];
                  const lines = [
                    s.target ? { lbl: `TARGET ${fmtPrice(s.target)}`, px: s.target, col: "#22c55e" } : null,
                    s.entry ? { lbl: `ENTRY ${s.name} ${s.side}`, px: s.entry, col: "#38bdf8" } : null,
                    s.stop ? { lbl: `STOP ${fmtPrice(s.stop)}`, px: s.stop, col: "#ef4444" } : null,
                  ].filter((x): x is { lbl: string; px: number; col: string } => Boolean(x));
                  return lines.map((ln) => {
                    if (ln.px < chart.minP || ln.px > chart.maxP) return null;
                    const y = chart.yFor(ln.px);
                    return (
                      <g key={ln.lbl}>
                        <line x1={chart.padL} x2={chart.W - chart.padR} y1={y} y2={y} stroke={ln.col} strokeDasharray="6 3" strokeWidth={1.2} />
                        <text x={chart.padL + 6} y={y - 3} fill={ln.col} fontSize="9.5" fontWeight="700" fontFamily="monospace">
                          {ln.lbl}
                        </text>
                      </g>
                    );
                  });
                })()}

                {/* Current Spot Marker */}
                {data?.spot != null && data.spot >= chart.minP && data.spot <= chart.maxP && (
                  <g>
                    <line
                      x1={chart.padL}
                      x2={chart.W - chart.padR}
                      y1={chart.yFor(data.spot)}
                      y2={chart.yFor(data.spot)}
                      stroke="#e2e8f0"
                      strokeDasharray="2 3"
                      strokeWidth={1}
                    />
                    <rect x={chart.W - chart.padR + 2} y={chart.yFor(data.spot) - 8} width={70} height={16} rx={3} fill="#387ed1" />
                    <text x={chart.W - chart.padR + 6} y={chart.yFor(data.spot) + 3} fill="#ffffff" fontSize="10" fontWeight="700" fontFamily="monospace">
                      {fmtPrice(data.spot)}
                    </text>
                  </g>
                )}

                {/* Interactive Crosshair + Price/Time Pills */}
                {hoverIdx !== null && bars[hoverIdx] && (
                  <g pointerEvents="none">
                    <line
                      x1={chart.xFor(hoverIdx)}
                      x2={chart.xFor(hoverIdx)}
                      y1={chart.padT}
                      y2={chart.padT + chart.plotH}
                      stroke="rgba(255,255,255,0.28)"
                      strokeDasharray="3 3"
                      strokeWidth={1}
                    />
                    <rect x={chart.xFor(hoverIdx) - 20} y={chart.H - 22} width={40} height={15} rx={3} fill="#1e293b" />
                    <text x={chart.xFor(hoverIdx)} y={chart.H - 11} fill="#e2e8f0" fontSize="9.5" textAnchor="middle" fontFamily="monospace">
                      {fmtTime(bars[hoverIdx].t)}
                    </text>
                  </g>
                )}
                {hoverY !== null && (
                  <g pointerEvents="none">
                    <line
                      x1={chart.padL}
                      x2={chart.W - chart.padR}
                      y1={hoverY}
                      y2={hoverY}
                      stroke="rgba(255,255,255,0.22)"
                      strokeDasharray="3 3"
                      strokeWidth={1}
                    />
                    <rect x={chart.W - chart.padR + 2} y={hoverY - 8} width={70} height={16} rx={3} fill="#1e293b" />
                    <text x={chart.W - chart.padR + 6} y={hoverY + 3} fill="#e2e8f0" fontSize="9.5" fontFamily="monospace">
                      {fmtPrice(chart.priceForY(hoverY))}
                    </text>
                  </g>
                )}

                {/* Time Labels */}
                {bars.map((b, i) => {
                  const step = Math.max(1, Math.floor(bars.length / 7));
                  if (i % step !== 0 && i !== bars.length - 1) return null;
                  return (
                    <text key={`t-${i}`} x={chart.xFor(i)} y={chart.H - 8} fill="#64748b" fontSize="10" textAnchor="middle" fontFamily="monospace">
                      {fmtTime(b.t)}
                    </text>
                  );
                })}
              </svg>
            )}
          </div>

          {/* RIGHT: Finder-Specific Markings & Agent Diagnostics */}
          <aside className="uc-agent-pane" aria-label="Agent diagnostics">
            {/* Finder Switcher */}
            <div className="uc-finder-tabs" role="tablist" aria-label="Opportunity Finder view">
              {finders.map((fc) => {
                const m = TRADER_META[fc];
                const active = activeFinder === fc;
                return (
                  <button
                    key={fc}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    className={`sd-seg-btn ${active ? "active" : ""}`}
                    onClick={() => selectFinder(fc)}
                    title={m.tagline}
                  >
                    {m.name.replace(" Trader", "")}
                  </button>
                );
              })}
            </div>

            {/* Finder Specialty Section */}
            {activeFinder === "FIB_GOLDEN_TRADER" && (
              <section className="uc-box">
                <div className="uc-box__head">
                  <span className="label">Fib Golden-Pocket Markings</span>
                  <span className="badge badge--cyan mono">FIB + PA + OI</span>
                </div>
                {data?.fibWatch?.length ? (
                  <div className="uc-list">
                    {data.fibWatch.map((fw, idx) => {
                      const st = STAGE_STYLE[fw.stage] ?? STAGE_STYLE.NO_SWING;
                      return (
                        <div key={idx} className="uc-item">
                          <div className="uc-item__top">
                            <strong className="mono">Fib {fw.side}</strong>
                            <span className={`te-pill ${st.cls}`}>{st.label}</span>
                          </div>
                          <span className="micro text-secondary">{fw.text}</span>
                          {fw.pocket && fw.invalidation != null && (
                            <span className="micro mono text-muted">
                              Pocket {fmtPrice(fw.pocket[0])}–{fmtPrice(fw.pocket[1])} · SL {fmtPrice(fw.invalidation)}
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <span className="micro text-muted">Waiting for a 3-ATR impulse swing to draw Fib levels.</span>
                )}
              </section>
            )}

            {activeFinder === "FLOW_MOMENTUM_TRADER" && (
              <section className="uc-box">
                <div className="uc-box__head">
                  <span className="label">Flow &amp; Momentum Markings</span>
                  <span className="badge badge--green mono">FLOW + MOMO</span>
                </div>
                <div className="uc-list">
                  <div className="uc-item">
                    <div className="uc-item__top micro">
                      <strong>Noise Area</strong>
                      <span className="mono">{data?.noise?.state ?? "N/A"}</span>
                    </div>
                    {data?.noise?.lower && data?.noise?.upper && (
                      <span className="micro mono text-muted">
                        Band {fmtPrice(data.noise.lower)} – {fmtPrice(data.noise.upper)}
                      </span>
                    )}
                  </div>
                  <div className="uc-item">
                    <div className="uc-item__top micro">
                      <strong>Multi-Timeframe Gate</strong>
                      <span className="mono">15m {data?.trend15 ?? "?"} · {data?.dayType?.type ?? "RANGE"}</span>
                    </div>
                    <span className="micro text-secondary">
                      Needs 5m breakout/setup + 15m trend match + 1m close beyond EMA9.
                    </span>
                  </div>
                  {data?.activeSetups?.map((s, idx) => (
                    <div key={idx} className="uc-item uc-item--ok">
                      <div className="uc-item__top mono micro">
                        <strong>{s.name} {s.side}</strong>
                        <span>R:R {s.rr ?? "-"}</span>
                      </div>
                      <span className="micro mono text-muted">
                        Entry {s.entry ? fmtPrice(s.entry) : "-"} · SL {s.stop ? fmtPrice(s.stop) : "-"} · T {s.target ? fmtPrice(s.target) : "-"}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {activeFinder === "COMMODITY_DESK_TRADER" && (
              <section className="uc-box">
                <div className="uc-box__head">
                  <span className="label">Commodity Desk Markings</span>
                  <span className="badge badge--amber mono">DESK + OI</span>
                </div>
                <div className="uc-list">
                  <div className="uc-item">
                    <div className="uc-item__top micro">
                      <strong>Option Chain &amp; OI Walls</strong>
                      <span className="mono">{data?.oi?.pcr != null ? `PCR ${Number(data.oi.pcr).toFixed(2)}` : "PCR n/a"}</span>
                    </div>
                    <span className="micro mono text-muted">
                      Sup {data?.oi?.support ? fmtPrice(data.oi.support) : "-"} · Res {data?.oi?.resistance ? fmtPrice(data.oi.resistance) : "-"}
                    </span>
                  </div>
                  {data?.vwap != null && (
                    <div className="uc-item">
                      <div className="uc-item__top micro">
                        <strong>MCX Futures VWAP</strong>
                        <span className="mono">{fmtPrice(data.vwap)}</span>
                      </div>
                      <span className="micro text-secondary">
                        Price {data.spot && data.spot > data.vwap ? "above" : "below"} VWAP · 15m {data.trend15 ?? "?"}
                      </span>
                    </div>
                  )}
                </div>
              </section>
            )}

            <section className="uc-box">
              <div className="uc-box__head">
                <span className="label">Latest Scan Verdict</span>
                {scan?.result && (
                  <span className={`te-pill ${scan.result === "SAVED" ? "te-pill--green" : scan.result === "ERROR" ? "te-pill--red" : ""}`}>
                    {scan.result}
                  </span>
                )}
              </div>
              <p className="micro text-primary" style={{ margin: 0 }}>
                {details?.reason || scan?.summary || "No scan recorded yet for this underlying."}
              </p>
              {scan?.createdAt && <span className="micro text-muted">Last scanned at {fmtTime(scan.createdAt)} IST</span>}
            </section>

            <section className="uc-box">
              <span className="label">What Setups Were Tested</span>
              {fired.length === 0 && rejected.length === 0 ? (
                <span className="micro text-muted">
                  No coded setup fired on the last completed 5m bar. Waiting for price structure trigger.
                </span>
              ) : (
                <div className="uc-list">
                  {confirmed.map((s, idx) => (
                    <div key={`c-${idx}`} className="uc-item uc-item--ok">
                      <strong className="mono">{s.name} {s.side}</strong>
                      <span className="micro">Confirmed (strength {s.strength})</span>
                    </div>
                  ))}
                  {rejected.map((r, idx) => (
                    <div key={`r-${idx}`} className="uc-item uc-item--rej">
                      <strong className="mono">{r.name} {r.side}</strong>
                      <span className="micro text-secondary">{r.reason}</span>
                    </div>
                  ))}
                </div>
              )}
              {(menuDropped.length > 0 || valDropped.length > 0) && (
                <div className="uc-dropped micro text-muted">
                  <strong>Dropped contracts:</strong>{" "}
                  {[...menuDropped, ...valDropped].map(([k, n]) => `${n}× ${k}`).join(", ")}
                </div>
              )}
            </section>

            {nearestContracts.length > 0 && (
              <section className="uc-box">
                <span className="label">Nearest Option Strikes</span>
                <div className="uc-list">
                  {nearestContracts.map((nc, idx) => (
                    <div key={idx} className="uc-item">
                      <div className="uc-item__top mono micro">
                        <strong>{nc.strike} {nc.side}</strong>
                        <span>₹{nc.ltp.toFixed(2)}</span>
                      </div>
                      <span className="micro text-muted mono">
                        {nc.spreadPct != null ? `spread ${nc.spreadPct}%` : "spread n/a"}
                        {nc.delta != null ? ` · Δ ${nc.delta}` : ""}
                        {` · OI ${nc.oi.toLocaleString("en-IN")}`}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </aside>
        </div>
      </div>
    </div>
  );
};
