import { useCallback, useEffect, useState } from "react";
import { SessionLoop } from "../types/sessions.types";

export type LoopConnection = "connecting" | "live" | "reconnecting" | "ended" | "off";

export interface SessionLoopHandle {
  /** Newest state pushed by the server-side loop (null until the first event). */
  data: SessionLoop | null;
  connection: LoopConnection;
  error: string | null;
  running: boolean;
  /** serverTime - clientTime, so countdowns follow the server's clock, not the browser's */
  clockOffsetMs: number;
}

/**
 * Subscribes to GET /sessions/{id}/stream (Server-Sent Events). The loop itself runs on the server from the moment
 * the session is created; it pushes a `loop` event whenever the pick, capital or scan result changes, plus a
 * `heartbeat` that keeps the clock offset fresh. EventSource reconnects by itself and the server re-sends the
 * current state on every (re)connect. Nothing here starts or listens to the opportunity engine.
 */
export function useSessionLoop(sessionId: number, enabled: boolean): SessionLoopHandle {
  const [data, setData] = useState<SessionLoop | null>(null);
  const [connection, setConnection] = useState<LoopConnection>("off");
  const [clockOffsetMs, setClockOffsetMs] = useState(0);

  useEffect(() => {
    if (!enabled || sessionId <= 0) {
      setConnection("off");
      return;
    }
    setConnection("connecting");
    const es = new EventSource(`/api/v1/sessions/${sessionId}/stream`);

    const syncClock = (serverTime: string) => setClockOffsetMs(Date.parse(serverTime) - Date.now());

    es.onopen = () => setConnection("live");
    es.onerror = () => setConnection(es.readyState === EventSource.CLOSED ? "ended" : "reconnecting");
    es.addEventListener("loop", (e) => {
      try {
        const loop = JSON.parse((e as MessageEvent).data) as SessionLoop;
        setData(loop);
        syncClock(loop.serverTime);
        setConnection("live");
      } catch {
        /* ignore a malformed frame; the next event replaces it */
      }
    });
    es.addEventListener("heartbeat", (e) => {
      try {
        syncClock((JSON.parse((e as MessageEvent).data) as { serverTime: string }).serverTime);
      } catch {
        /* ignore */
      }
    });
    es.addEventListener("closed", () => {
      es.close(); // the loop has ended (session closed / deleted / not today): do not reconnect
      setConnection("ended");
    });

    return () => es.close();
  }, [enabled, sessionId]);

  const error = connection === "reconnecting" ? "Connection lost, reconnecting…" : null;
  return { data, connection, error, running: connection === "live", clockOffsetMs };
}

/** Seconds left until `expiresAt` on the SERVER's clock, refreshed every 100 ms. */
export function useCountdown(expiresAt: string | null | undefined, clockOffsetMs: number): number {
  const compute = useCallback(
    () => (expiresAt ? Math.max(0, (Date.parse(expiresAt) - (Date.now() + clockOffsetMs)) / 1000) : 0),
    [expiresAt, clockOffsetMs]
  );
  const [left, setLeft] = useState(compute);
  useEffect(() => {
    setLeft(compute());
    if (!expiresAt) return;
    const id = window.setInterval(() => setLeft(compute()), 100);
    return () => window.clearInterval(id);
  }, [expiresAt, compute]);
  return left;
}
