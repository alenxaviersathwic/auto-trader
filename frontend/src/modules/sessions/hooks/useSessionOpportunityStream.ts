import { useEffect, useRef, useState } from "react";
import { Opportunity } from "../../opportunities/types/opportunities.types";

export interface OpportunityBatch {
  key: string;
  underlyingCode: string;
  iterationNo: number;
  count: number;
  note: string | null;
  receivedAt: string;
  opportunities: Opportunity[];
}

export interface StreamErrorEvent {
  key: string;
  underlyingCode: string;
  iterationNo: number;
  error: string;
  receivedAt: string;
}

export type StreamConnectionState = "idle" | "connecting" | "open" | "closed" | "error";

const MAX_BATCHES = 50;
const MAX_ERRORS = 20;

/**
 * Subscribes to live opportunity batches for a fixed set of underlying codes via
 * GET /opportunities/stream?underlyings=... (Server-Sent Events). Any card session
 * already running for one of these underlyings pushes its next iteration here the
 * moment it lands -- this hook does not start/stop those card sessions itself.
 */
export function useSessionOpportunityStream(underlyings: string[]) {
  const codes = underlyings.filter(Boolean).map((c) => c.toUpperCase());
  const key = codes.slice().sort().join(",");

  const [connectionState, setConnectionState] = useState<StreamConnectionState>("idle");
  const [batches, setBatches] = useState<OpportunityBatch[]>([]);
  const [errors, setErrors] = useState<StreamErrorEvent[]>([]);
  const seqRef = useRef(0);

  useEffect(() => {
    if (codes.length === 0) {
      setConnectionState("idle");
      return;
    }

    setConnectionState("connecting");
    setBatches([]);
    setErrors([]);

    const url = `/api/v1/opportunities/stream?underlyings=${encodeURIComponent(codes.join(","))}`;
    const es = new EventSource(url);

    es.addEventListener("connected", () => setConnectionState("open"));

    es.addEventListener("opportunities.batch", (evt: MessageEvent) => {
      const data = JSON.parse(evt.data) as {
        underlyingCode: string;
        iterationNo: number;
        count: number;
        note: string | null;
        opportunities: Opportunity[];
      };
      setConnectionState("open");
      seqRef.current += 1;
      setBatches((prev) =>
        [
          {
            key: `${data.underlyingCode}-${data.iterationNo}-${seqRef.current}`,
            underlyingCode: data.underlyingCode,
            iterationNo: data.iterationNo,
            count: data.count,
            note: data.note,
            receivedAt: new Date().toISOString(),
            opportunities: data.opportunities,
          },
          ...prev,
        ].slice(0, MAX_BATCHES)
      );
    });

    es.addEventListener("opportunities.error", (evt: MessageEvent) => {
      const data = JSON.parse(evt.data) as { underlyingCode: string; iterationNo: number; error: string };
      seqRef.current += 1;
      setErrors((prev) =>
        [
          {
            key: `${data.underlyingCode}-${data.iterationNo}-${seqRef.current}`,
            underlyingCode: data.underlyingCode,
            iterationNo: data.iterationNo,
            error: data.error,
            receivedAt: new Date().toISOString(),
          },
          ...prev,
        ].slice(0, MAX_ERRORS)
      );
    });

    es.onerror = () => setConnectionState("error");

    return () => {
      es.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return { connectionState, batches, errors, underlyingCodes: codes };
}
