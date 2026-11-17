import React, { useEffect, useMemo, useState } from "react";
import { AlertTriangle, RefreshCw, X } from "lucide-react";
import { useUnderlyingChart } from "../../opportunity-finder/hooks/useOpportunities";
import { UnderlyingBar5 } from "../../opportunity-finder/types/opportunities.types";

interface Props {
  code: string;
  onClose: () => void;
}

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

export const UnderlyingChartModal: React.FC<Props> = ({ code, onClose }) => {
  const { data, isLoading, isFetching, refetch } = useUnderlyingChart(code);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const bars = data?.bars5 ?? [];
  const ema9 = data?.ema9 ?? [];
  const ema21 = data?.ema21 ?? [];
  const primaryFib = data?.fibWatch?.[0];

  const chart = useMemo(() => {
    if (bars.length === 0) return null;
    const W = 780;
    const H = 430;
    const padL = 14;
    const padR = 76;
    const padT = 18;
    const padB = 28;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;

    const prices: number[] = [];
    bars.forEach((b) => {
      prices.push(b.h, b.l);
    });
    ema9.forEach((v) => Number.isFinite(v) && prices.push(v));
    ema21.forEach((v) => Number.isFinite(v) && prices.push(v));
    if (data?.vwap) prices.push(data.vwap);
    if (data?.levels?.orHigh) prices.push(data.levels.orHigh);
    if (data?.levels?.orLow) prices.push(data.levels.orLow);
    if (data?.spot) prices.push(data.spot);
    if (primaryFib?.pocket) prices.push(primaryFib.pocket[0], primaryFib.pocket[1]);

    const rawMin = Math.min(...prices);
    const rawMax = Math.max(...prices);
    const pad = Math.max((rawMax - rawMin) * 0.08, rawMax * 0.0008);
    const minP = rawMin - pad;
    const maxP = rawMax + pad;
    const span = Math.max(1e-6, maxP - minP);

    const yFor = (p: number) => padT + ((maxP - p) / span) * plotH;
    const stepX = plotW / Math.max(bars.length, 1);
    const xFor = (i: number) => padL + stepX * (i + 0.5);
    const candleW = Math.max(3, Math.min(11, stepX * 0.65));

    const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => {
      const p = maxP - f * span;
      return { p, y: padT + f * plotH };
    });

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
      minP,
      maxP,
      yFor,
      xFor,
      candleW,
      yTicks,
      ema9Path: linePath(ema9),
      ema21Path: linePath(ema21),
    };
  }, [bars, ema9, ema21, data?.vwap, data?.levels?.orHigh, data?.levels?.orLow, data?.spot, primaryFib]);

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

  const keyLines = [
    data?.levels?.pdh ? { label: "PDH", price: data.levels.pdh, color: "#f59e0b" } : null,
    data?.levels?.pdl ? { label: "PDL", price: data.levels.pdl, color: "#f59e0b" } : null,
    data?.levels?.orHigh ? { label: "ORH", price: data.levels.orHigh, color: "#38bdf8" } : null,
    data?.levels?.orLow ? { label: "ORL", price: data.levels.orLow, color: "#38bdf8" } : null,
    data?.vwap ? { label: "VWAP", price: data.vwap, color: "#a78bfa" } : null,
  ].filter((x): x is { label: string; price: number; color: string } => Boolean(x));

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
            <button type="button" className="te-btn te-btn--ghost te-btn--xs" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw size={12} /> {isFetching ? "Refreshing…" : "Refresh"}
            </button>
            <button type="button" className="ss-close" onClick={onClose} aria-label="Close chart">
              <X size={16} />
            </button>
          </div>
        </header>

        <div className="uc-body">
          {/* LEFT: Main Trader Candlestick Chart */}
          <div className="uc-chart-pane">
            <div className="uc-ohlc-bar mono micro">
              {activeBar ? (
                <>
                  <span className="text-muted">{fmtTime(activeBar.t)} IST</span>
                  <span>O {fmtPrice(activeBar.o)}</span>
                  <span className="text-green">H {fmtPrice(activeBar.h)}</span>
                  <span className="text-red">L {fmtPrice(activeBar.l)}</span>
                  <span className={activeBar.c >= activeBar.o ? "text-green" : "text-red"}>C {fmtPrice(activeBar.c)}</span>
                  {ema9[activeIdx] != null && <span style={{ color: "#38bdf8" }}>EMA9 {fmtPrice(ema9[activeIdx])}</span>}
                  {ema21[activeIdx] != null && <span style={{ color: "#f59e0b" }}>EMA21 {fmtPrice(ema21[activeIdx])}</span>}
                  {data?.vwap != null && <span style={{ color: "#a78bfa" }}>VWAP {fmtPrice(data.vwap)}</span>}
                </>
              ) : (
                <span className="text-muted">5-minute chart</span>
              )}
            </div>

            {isLoading ? (
              <div className="uc-empty">Loading {code} 5-minute chart…</div>
            ) : !chart ? (
              <div className="uc-empty">
                <AlertTriangle size={18} className="text-amber" />
                <span>{data?.marketError ?? "No intraday 5-minute candles available right now."}</span>
              </div>
            ) : (
              <svg
                className="uc-svg"
                viewBox={`0 0 ${chart.W} ${chart.H}`}
                onMouseLeave={() => setHoverIdx(null)}
                onMouseMove={(e) => {
                  const rect = e.currentTarget.getBoundingClientRect();
                  const relX = ((e.clientX - rect.left) / rect.width) * chart.W;
                  const idx = Math.floor(((relX - chart.padL) / chart.plotW) * bars.length);
                  if (idx >= 0 && idx < bars.length) setHoverIdx(idx);
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
                {data?.noise?.lower && data.noise.upper && (
                  <rect
                    x={chart.padL}
                    width={chart.plotW}
                    y={Math.max(chart.padT, Math.min(chart.yFor(data.noise.upper), chart.yFor(data.noise.lower)))}
                    height={Math.max(2, Math.abs(chart.yFor(data.noise.lower) - chart.yFor(data.noise.upper)))}
                    fill="rgba(148, 163, 184, 0.07)"
                  />
                )}

                {/* Fib Golden Pocket Zone */}
                {primaryFib?.pocket && (
                  <g>
                    <rect
                      x={chart.padL}
                      width={chart.plotW}
                      y={Math.max(chart.padT, Math.min(chart.yFor(primaryFib.pocket[0]), chart.yFor(primaryFib.pocket[1])))}
                      height={Math.max(2, Math.abs(chart.yFor(primaryFib.pocket[0]) - chart.yFor(primaryFib.pocket[1])))}
                      fill="rgba(56, 189, 248, 0.14)"
                    />
                    <text x={chart.padL + 6} y={chart.yFor((primaryFib.pocket[0] + primaryFib.pocket[1]) / 2) + 3} fill="#38bdf8" fontSize="9.5" fontFamily="monospace">
                      FIB POCKET {primaryFib.side}
                    </text>
                  </g>
                )}

                {/* Key Price Levels */}
                {keyLines.map((kl) => {
                  if (kl.price < chart.minP || kl.price > chart.maxP) return null;
                  const y = chart.yFor(kl.price);
                  return (
                    <g key={kl.label}>
                      <line x1={chart.padL} x2={chart.W - chart.padR} y1={y} y2={y} stroke={kl.color} strokeOpacity={0.55} strokeDasharray="4 4" strokeWidth={1} />
                      <text x={chart.W - chart.padR + 6} y={y + 3} fill={kl.color} fontSize="9.5" fontFamily="monospace">
                        {kl.label} {fmtPrice(kl.price)}
                      </text>
                    </g>
                  );
                })}

                {/* EMA21 & EMA9 */}
                {chart.ema21Path && <path d={chart.ema21Path} fill="none" stroke="#f59e0b" strokeWidth={1.3} strokeOpacity={0.85} />}
                {chart.ema9Path && <path d={chart.ema9Path} fill="none" stroke="#38bdf8" strokeWidth={1.4} strokeOpacity={0.9} />}

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
                    <rect x={chart.W - chart.padR + 2} y={chart.yFor(data.spot) - 8} width={68} height={16} rx={3} fill="#387ed1" />
                    <text x={chart.W - chart.padR + 6} y={chart.yFor(data.spot) + 3} fill="#ffffff" fontSize="10" fontWeight="700" fontFamily="monospace">
                      {fmtPrice(data.spot)}
                    </text>
                  </g>
                )}

                {/* Hover Crosshair */}
                {hoverIdx !== null && bars[hoverIdx] && (
                  <line
                    x1={chart.xFor(hoverIdx)}
                    x2={chart.xFor(hoverIdx)}
                    y1={chart.padT}
                    y2={chart.H - chart.padB}
                    stroke="rgba(255,255,255,0.25)"
                    strokeDasharray="3 3"
                    strokeWidth={1}
                  />
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

          {/* RIGHT: Agent Diagnostics — Why No Opportunity & What We Are Waiting For */}
          <aside className="uc-agent-pane" aria-label="Agent diagnostics">
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
                  No coded 5-minute setup fired on the last completed bar. Waiting for price structure trigger.
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

            <section className="uc-box">
              <span className="label">What the Agent Is Waiting For</span>
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
                <span className="micro text-muted">Monitoring 15m trend, 5m setups &amp; 1m EMA9 trigger.</span>
              )}
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
};
