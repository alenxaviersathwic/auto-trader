import React, { useState } from "react";
import {
  AlertTriangle,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Layers,
  Lock,
  Shield,
  Sparkles,
  Timer,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { SessionPick } from "../types/sessions.types";
import { useCountdown } from "../hooks/useSessionLoop";
import { formatExpiry } from "../../opportunity-finder/components/formatters";

const px = (n: number): string => n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const inr = (n: number): string => `₹${Math.round(n).toLocaleString("en-IN")}`;
const hm = (iso: string): string =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });

/** 15-minute trend and 1-minute trigger the setup was confirmed on (missing on picks saved before 17 Nov 2026). */
const TimeframeChips: React.FC<{ pick: SessionPick }> = ({ pick }) => {
  const tf = pick.timeframes;
  if (!tf) return null;
  const want = pick.optionType === "CE" ? "UP" : "DOWN";
  const t15 = tf["15m"];
  const m1 = tf["1m"];
  return (
    <>
      {t15 && (
        <span
          className={`te-pill ${t15.trend === want ? "te-pill--green" : t15.trend === "FLAT" ? "te-pill--amber" : "te-pill--red"}`}
          title={`15-minute trend ${t15.trend}${t15.source === "15m+prev" ? " (EMAs include the previous session's 15-minute bars)" : ""}`}
        >
          15m {t15.trend}
        </span>
      )}
      {m1 && m1.close != null && (
        <span
          className="te-pill te-pill--green"
          title={`1-minute close ${px(m1.close)} ${pick.optionType === "CE" ? "above" : "below"} EMA9 ${px(m1.ema9 ?? 0)}; trigger ${px(m1.trigger ?? 0)}`}
        >
          1m ✓ {m1.trigger != null ? `${pick.optionType === "CE" ? ">" : "<"} ${Math.round(m1.trigger).toLocaleString("en-IN")}` : ""}
        </span>
      )}
    </>
  );
};

interface Props {
  pick: SessionPick;
  clockOffsetMs: number;
  locking: boolean;
  best: boolean;
  defaultExpanded?: boolean;
  onLock: (pickId: number) => void;
}

/** One open setup, after trading-engine's suggestion card: collapsible, with the stop / entry / target range. */
export const SuggestionCard: React.FC<Props> = ({ pick: p, clockOffsetMs, locking, best, defaultExpanded, onLock }) => {
  const [open, setOpen] = useState(Boolean(defaultExpanded));
  const left = useCountdown(p.expiresAt, clockOffsetMs);
  const live = p.pickState === "OFFERED" && left > 0;
  const ce = p.optionType === "CE";
  const lo = Math.min(p.stop, p.entry);
  const span = Math.max(0.01, p.target - lo);
  const pos = (v: number) => Math.max(0, Math.min(100, ((v - lo) / span) * 100));
  const conf = Math.max(0, Math.min(100, p.winProbPct));
  const toggle = () => setOpen((o) => !o);

  return (
    <article className={`te-card ${ce ? "te-card--ce" : "te-card--pe"} ${best ? "te-card--best" : ""} ${live ? "" : "te-card--dead"}`}>
      <div
        className="te-card__head"
        role="button"
        tabIndex={0}
        aria-expanded={open}
        onClick={toggle}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggle();
          }
        }}
      >
        <div className="te-card__head-left">
          <span className="te-symbol">
            <span className="te-symbol__market">{p.underlyingCode}</span>
            <span className="te-symbol__strike">{p.strike.toLocaleString("en-IN")}</span>
          </span>
          <span className={`te-pill ${ce ? "te-pill--green" : "te-pill--red"}`}>
            {ce ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
            {p.optionType}
          </span>
          <span className="te-pill te-pill--amber">
            <CalendarDays size={10} /> EXP {formatExpiry(p.expiry)}
          </span>
          {p.strategy && <span className="te-pill">{p.strategy.replace(/_/g, " ")}</span>}
          <TimeframeChips pick={p} />
          {best && (
            <span className="te-pill te-pill--cyan">
              <Sparkles size={10} /> MANAGER PICK
            </span>
          )}
          {live ? (
            <span className="te-pill te-pill--green">
              <span className="te-dot" /> {Math.ceil(left)}s
            </span>
          ) : (
            <span className="te-pill">CLOSED</span>
          )}
        </div>
        <div className="te-card__head-right">
          {!open && (
            <div className="te-quick">
              <span className="te-quick__item">
                <span className="te-tiny-label">ENTRY</span>
                <span className="te-tiny-val">₹{px(p.entry)}</span>
              </span>
              <span className="te-quick__item">
                <span className="te-tiny-label">TARGET</span>
                <span className="te-tiny-val text-green">₹{px(p.target)} +{p.targetPct.toFixed(1)}%</span>
              </span>
              <span className="te-quick__item">
                <span className="te-tiny-label">R:R</span>
                <span className="te-tiny-val">{p.rewardRisk.toFixed(2)}</span>
              </span>
              <span className="te-quick__item">
                <span className="te-tiny-label">NET</span>
                <span className="te-tiny-val">{inr(p.expectedNet)}</span>
              </span>
            </div>
          )}
          <span className="te-collapse" aria-hidden="true">
            {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />} {open ? "Collapse" : "Expand"}
          </span>
        </div>
      </div>

      <div className="te-conf">
        <Sparkles size={13} className="text-muted" />
        <span className="te-conf__label">Model confidence</span>
        <div className="te-conf__track" title="The model's own figure, not a measured win rate">
          <div className="te-conf__fill" style={{ width: `${conf}%` }} />
        </div>
        <span className="te-conf__val">{conf.toFixed(0)}%</span>
      </div>

      {open && (
        <div className="te-card__body">
          <div className="te-range">
            <div className="te-range__labels">
              <div className="te-range__item te-range__item--sl">
                <span className="te-range__sub">Stop loss</span>
                <span className="te-range__val">₹{px(p.stop)}</span>
                <span className="te-range__pct">−{p.stopPct.toFixed(1)}%</span>
              </div>
              <div className="te-range__item te-range__item--entry">
                <span className="te-range__sub">Entry area</span>
                <span className="te-range__val">
                  ₹{px(p.entry)} – {px(p.entryMax)}
                </span>
              </div>
              <div className="te-range__item te-range__item--target">
                <span className="te-range__sub">Target</span>
                <span className="te-range__val">₹{px(p.target)}</span>
                <span className="te-range__pct">+{p.targetPct.toFixed(1)}%</span>
              </div>
            </div>
            <div className="te-range__track">
              <div className="te-range__risk" style={{ left: `${pos(p.stop)}%`, width: `${pos(p.entry) - pos(p.stop)}%` }} />
              <div className="te-range__gain" style={{ left: `${pos(p.entry)}%`, width: `${pos(p.target) - pos(p.entry)}%` }} />
              <div className="te-range__pin" style={{ left: `${pos(p.stop)}%`, background: "var(--bearish-red)" }} />
              <div className="te-range__pin" style={{ left: `${pos(p.entry)}%`, background: "var(--cyan)" }} />
              <div className="te-range__pin" style={{ left: `${pos(p.target)}%`, background: "var(--bullish-green)" }} />
            </div>
            <div className="te-range__foot">
              <span>Do not buy above ₹{px(p.entryMax)}: reward drops below 1.2× risk</span>
              <span className="te-pill te-pill--blue">R:R {p.rewardRisk.toFixed(2)}</span>
            </div>
          </div>

          <div className="te-metrics">
            <div className="te-metric">
              <span className="te-metric__label">Expected after charges</span>
              <span className="te-metric__value text-green">{inr(p.expectedNet)}</span>
            </div>
            <div className="te-metric">
              <span className="te-metric__label">Stopped / target</span>
              <span className="te-metric__value">
                <span className="text-red">−{inr(p.riskAmount)}</span> <span className="text-green">+{inr(p.rewardAmount)}</span>
              </span>
            </div>
          </div>

          <div className="te-tiles">
            <div className="te-tile">
              <span className="te-metric__label">
                <Clock size={12} /> Valid until
              </span>
              <span className="te-tile__value mono">{hm(p.expiresAt)} IST</span>
            </div>
            <div className="te-tile">
              <span className="te-metric__label">
                <Timer size={12} /> Hold up to
              </span>
              <span className="te-tile__value mono">{hm(p.holdUntil)} IST</span>
            </div>
            <div className="te-tile">
              <span className="te-metric__label">
                <Shield size={12} /> Trader
              </span>
              <span className="te-tile__value">{p.traderName ?? "—"}</span>
            </div>
          </div>

          {(p.reasons.length > 0 || p.risks.length > 0) && (
            <ul className="te-points">
              {p.reasons.slice(0, 4).map((r, i) => (
                <li key={`r${i}`}>
                  <CheckCircle2 size={13} className="text-green" />
                  <span>{String(r)}</span>
                </li>
              ))}
              {p.risks.slice(0, 3).map((r, i) => (
                <li key={`k${i}`}>
                  <AlertTriangle size={13} className="text-amber" />
                  <span>{String(r)}</span>
                </li>
              ))}
            </ul>
          )}

          <div className="te-actionbar">
            <div className="te-actionbar__left">
              <span className="te-action-pill">
                <Layers size={13} /> Qty <strong>{p.quantity}</strong> ({p.lots} × {p.lotUnits})
              </span>
              <span className="te-action-pill">
                Capital <strong>{inr(p.capitalRequired)}</strong> · {p.usagePct.toFixed(0)}% of free
              </span>
            </div>
            <button
              type="button"
              className="te-btn te-btn--primary"
              disabled={!live || locking}
              onClick={(e) => {
                e.stopPropagation();
                onLock(p.id);
              }}
            >
              <Lock size={13} /> {locking ? "Locking…" : live ? "Lock trade" : "Closed"}
            </button>
          </div>
        </div>
      )}
    </article>
  );
};
