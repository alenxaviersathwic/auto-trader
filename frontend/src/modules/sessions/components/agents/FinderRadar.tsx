import React, { useEffect, useRef, useState } from "react";
import { Radar } from "lucide-react";

export interface FinderStatus {
  code: string;
  note: string;
  error: boolean;
  /** RUNNING master (the scanner is on for this index). */
  on: boolean;
  scans: number;
  lastStartedAt: string | null;
  lastCompletedAt: string | null;
  lastDurationMs: number | null;
  /** Seconds the scanner waits between passes. */
  gapSeconds: number;
}

interface Props {
  finders: FinderStatus[];
  /** The index the scan loop is on at this moment, if it reports one. */
  currentCode: string | null;
  /** Who is doing the finding: the session manager's opportunity trader. */
  traderName: string;
  active: boolean;
}

const FLASH_MS = 6000;
const STUCK_MS = 60000;
/** A scan takes ~100-300 ms; hold the sweep on a tile at least this long so the eye can follow it hop across. */
const HOLD_MS = 1200;

/** Codes the loop reported as current within the last HOLD_MS. */
function useHeld(code: string | null): Set<string> {
  const until = useRef(new Map<string, number>());
  const [, bump] = useState(0);
  useEffect(() => {
    if (!code) return;
    until.current.set(code, Date.now() + HOLD_MS);
    bump((n) => n + 1);
    const t = window.setTimeout(() => bump((n) => n + 1), HOLD_MS + 20);
    return () => window.clearTimeout(t);
  }, [code]);
  const now = Date.now();
  const held = new Set<string>();
  until.current.forEach((u, c) => (u > now ? held.add(c) : until.current.delete(c)));
  if (code) held.add(code);
  return held;
}

function useNow(ms: number, on: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!on) return;
    const t = window.setInterval(() => setNow(Date.now()), ms);
    return () => window.clearInterval(t);
  }, [ms, on]);
  return now;
}

const ago = (ms: number): string => (ms < 1500 ? "now" : ms < 60000 ? `${Math.round(ms / 1000)}s ago` : `${Math.round(ms / 60000)}m ago`);

/**
 * The opportunity finders at work: one tile per index. The one being scanned right now gets a radar sweep, a tile
 * whose scan just finished flashes, the rest show how long ago they last looked. Timing comes from the scanner's own
 * start / finish stamps, so nothing here is simulated.
 */
export const FinderRadar: React.FC<Props> = ({ finders, currentCode, traderName, active }) => {
  const now = useNow(1000, active);
  const held = useHeld(active ? currentCode : null);
  const tiles = finders.map((f) => {
    const started = f.lastStartedAt ? Date.parse(f.lastStartedAt) : 0;
    const done = f.lastCompletedAt ? Date.parse(f.lastCompletedAt) : 0;
    const scanning = active && f.on && (held.has(f.code) || (started > done && now - started < STUCK_MS));
    return { ...f, scanning, sinceDone: done ? now - done : null, done };
  });
  const busy = tiles.filter((t) => t.scanning).map((t) => t.code);
  const on = tiles.filter((t) => t.on).length;
  const latest = tiles.reduce<(typeof tiles)[number] | null>((a, t) => (t.done && (!a || t.done > a.done) ? t : a), null);
  // Between passes: roughly when the next one starts (last finish + the scanner's gap). Approximate, so it says "~".
  const gapMs = (tiles.find((t) => t.on)?.gapSeconds ?? 20) * 1000;
  const waitLeft = latest?.sinceDone != null ? Math.max(0, gapMs - latest.sinceDone) : null;

  return (
    <div className={`fr ${active && on > 0 ? "fr--live" : ""}`}>
      <div className="fr__head" aria-live="polite">
        <span className={`fr__radar ${busy.length ? "fr__radar--busy" : ""}`} aria-hidden="true">
          <Radar size={13} />
        </span>
        {!active || on === 0 ? (
          <span className="text-muted">Opportunity finders are off</span>
        ) : busy.length ? (
          <span>
            <strong>{traderName}</strong> scanning <strong className="mono">{busy.join(", ")}</strong>
            <span className="fr__dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
          </span>
        ) : (
          <span>
            <strong>{traderName}</strong> watching {on} finder{on === 1 ? "" : "s"}
            {latest?.sinceDone != null && <span className="text-muted"> · last pass {ago(latest.sinceDone)}</span>}
            {waitLeft != null && waitLeft > 0 && (
              <span className="text-muted"> · next in ~{Math.ceil(waitLeft / 1000)}s</span>
            )}
          </span>
        )}
      </div>
      {active && on > 0 && !busy.length && waitLeft != null && (
        <div className="fr__gap" aria-hidden="true">
          <span className="fr__gap-fill" style={{ width: `${Math.min(100, (1 - waitLeft / gapMs) * 100)}%` }} />
        </div>
      )}

      <div className="fr__grid">
        {tiles.map((t) => {
          const flash = !t.scanning && t.sinceDone != null && t.sinceDone < FLASH_MS;
          const cls = [
            "fr-tile",
            t.scanning && "fr-tile--scanning",
            !t.on && "fr-tile--off",
            t.error && "fr-tile--err",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <div key={t.code} className={cls} title={t.note}>
              {t.scanning && <span className="fr-tile__sweep" aria-hidden="true" />}
              {flash && <span key={t.lastCompletedAt ?? ""} className="fr-tile__flash" aria-hidden="true" />}
              <div className="fr-tile__top">
                <span className={`fr-tile__dot ${t.scanning ? "fr-tile__dot--busy" : t.on ? "fr-tile__dot--on" : ""}`} />
                <span className="fr-tile__code">{t.code}</span>
                <span className="fr-tile__when">
                  {!t.on ? "stopped" : t.scanning ? "scanning" : t.sinceDone != null ? ago(t.sinceDone) : "--"}
                </span>
              </div>
              <span className="fr-tile__note">{t.note}</span>
              <span className="fr-tile__meta mono">
                {t.scans} scans{t.lastDurationMs != null ? ` · ${t.lastDurationMs} ms` : ""}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
