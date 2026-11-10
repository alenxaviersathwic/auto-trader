import { useEffect, useState } from "react";
import { ActiveTrade, TradeLiveSnapshot } from "../types/trades.types";

export type TradeStreamConnection = "connecting" | "live" | "reconnecting" | "ended" | "off";

export interface TradeStreamHandle {
  trade: ActiveTrade | null;
  connection: TradeStreamConnection;
  error: string | null;
  running: boolean;
  clockOffsetMs: number;
}

/**
 * Subscribes to GET /api/v1/trades/{id}/stream (SSE).
 * Pushes `trade` whenever the server-side Trader pilot updates LTP, SL, Target, telemetry, or exits.
 */
export function useTradeStream(tradeId: number, enabled: boolean): TradeStreamHandle {
  const [trade, setTrade] = useState<ActiveTrade | null>(null);
  const [connection, setConnection] = useState<TradeStreamConnection>("off");
  const [clockOffsetMs, setClockOffsetMs] = useState(0);

  useEffect(() => {
    if (!enabled || tradeId <= 0) {
      setConnection("off");
      return;
    }
    setConnection("connecting");
    const es = new EventSource(`/api/v1/trades/${tradeId}/stream`);
    const syncClock = (serverTime: string) => setClockOffsetMs(Date.parse(serverTime) - Date.now());

    es.onopen = () => setConnection("live");
    es.onerror = () =>
      setConnection(es.readyState === EventSource.CLOSED ? "ended" : "reconnecting");

    es.addEventListener("trade", (e) => {
      try {
        const snap = JSON.parse((e as MessageEvent).data) as TradeLiveSnapshot;
        setTrade(snap.trade);
        syncClock(snap.serverTime);
        setConnection(snap.trade.tradeState === "RUNNING" ? "live" : "ended");
      } catch {
        /* ignore malformed frame */
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
      es.close();
      setConnection("ended");
    });

    return () => es.close();
  }, [tradeId, enabled]);

  const error = connection === "reconnecting" ? "Stream lost, reconnecting to Trader pilot…" : null;
  return {
    trade,
    connection,
    error,
    running: connection === "live",
    clockOffsetMs,
  };
}

