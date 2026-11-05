import React from "react";
import { formatRupee } from "../../opportunities/components/formatters";

interface Props {
  stop: number;
  entry: number;
  entryMax: number;
  target: number;
  stopPct?: number;
  targetPct?: number;
  /** Live price to mark on the scale (Trade Lock popup). */
  marker?: number | null;
}

/** Stop loss, entry area and target on ONE price scale, so the room to lose and to gain is visible at a glance. */
export const PriceLadder: React.FC<Props> = ({ stop, entry, entryMax, target, stopPct, targetPct, marker }) => {
  const pad = (target - stop) * 0.04;
  const lo = Math.min(stop, marker ?? stop) - pad;
  const hi = Math.max(target, marker ?? target) + pad;
  const at = (v: number) => `${(Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo) * 100}%`;
  const w = (a: number, b: number) => `${Math.max(0, (Math.min(hi, b) - Math.max(lo, a)) / (hi - lo)) * 100}%`;
  const mid = (entry + entryMax) / 2;

  return (
    <div className="sl-ladder" aria-label="Price ladder: stop loss, entry area, target">
      <div className="sl-ladder__track">
        <div className="sl-ladder__seg sl-ladder__seg--risk" style={{ left: at(stop), width: w(stop, entry) }} />
        <div className="sl-ladder__seg sl-ladder__seg--zone" style={{ left: at(entry), width: w(entry, entryMax) }} />
        <div className="sl-ladder__seg sl-ladder__seg--reward" style={{ left: at(entryMax), width: w(entryMax, target) }} />
        {marker != null && (
          <div
            className={`sl-ladder__marker ${marker > entryMax ? "sl-ladder__marker--warn" : ""}`}
            style={{ left: at(marker) }}
          />
        )}
        <div className="sl-ladder__tick sl-ladder__tick--bottom" style={{ left: at(stop) }}>
          <span className="sl-ladder__price text-red">{formatRupee(stop)}</span>
          <span className="sl-ladder__note">Stop loss{stopPct != null ? ` −${stopPct.toFixed(1)}%` : ""}</span>
        </div>
        <div className="sl-ladder__tick sl-ladder__tick--bottom" style={{ left: at(mid) }}>
          <span className="sl-ladder__price">
            {formatRupee(entry)} – {formatRupee(entryMax)}
          </span>
          <span className="sl-ladder__note">Entry area</span>
        </div>
        <div className="sl-ladder__tick sl-ladder__tick--bottom" style={{ left: at(target) }}>
          <span className="sl-ladder__price text-green">{formatRupee(target)}</span>
          <span className="sl-ladder__note">Target{targetPct != null ? ` +${targetPct.toFixed(1)}%` : ""}</span>
        </div>
      </div>
    </div>
  );
};
