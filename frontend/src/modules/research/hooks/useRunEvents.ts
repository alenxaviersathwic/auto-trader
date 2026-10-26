import { useEffect, useRef, useState } from "react";
import { ResearchRunEvent } from "../types/research.types";

export interface LiveRunProgress {
  runId: number;
  state: "QUEUED" | "RUNNING" | "COMPLETED" | "PARTIAL" | "FAILED" | "CANCELLED";
  currentNode: string | null;
  progressPct: number;
  nodeDescription: string;
  stats: Record<string, any>;
  events: ResearchRunEvent[];
  error?: string | null;
}

const NODE_LABELS: Record<string, string> = {
  load_context: "Loading active context & sources",
  plan_queries: "Planning freshness search queries",
  discover_stocks: "Matching stocks to universe",
  search_and_fetch: "Fetching news pages & RSS feeds",
  clean_filter_dedupe: "Cleaning, filtering freshness & deduplicating",
  embed_chunks: "Generating vector embeddings for chunks",
  extract_claims: "Extracting factual claims with LLM",
  verify_claims: "Verifying quotes against original text",
  negative_sweep: "Scanning risk terms & performing negative sweep",
  classify_status: "Classifying news clearance status",
  score_rank: "Scoring and ranking supported underlyings",
  write_briefs: "Synthesizing cited research briefs",
  verify_citations: "Verifying cited claims integrity",
  persist: "Persisting candidates and brief embeddings",
  finalize: "Finalizing research run results",
};

export function useRunEvents(runId: number | null) {
  const [progress, setProgress] = useState<LiveRunProgress>({
    runId: runId ?? 0,
    state: "IDLE" as any,
    currentNode: null,
    progressPct: 0,
    nodeDescription: "Idle",
    stats: {},
    events: [],
  });

  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!runId || runId <= 0) {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      return;
    }

    setProgress((prev) => ({
      ...prev,
      runId,
      state: "RUNNING",
      currentNode: "load_context",
      nodeDescription: "Starting research runner...",
      progressPct: 5,
    }));

    const url = `/api/v1/research/runs/${runId}/events`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    const handleEvent = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data);
        const eventType = payload.event;
        const data = payload.data || {};

        if (eventType === "run.started") {
          setProgress((prev) => ({
            ...prev,
            state: "RUNNING",
            progressPct: Math.max(prev.progressPct, 5),
            nodeDescription: "Research run started",
          }));
        } else if (eventType === "node.started") {
          const node = data.node || "";
          const desc = NODE_LABELS[node] || node;
          setProgress((prev) => ({
            ...prev,
            currentNode: node,
            nodeDescription: desc,
          }));
        } else if (eventType === "node.progress") {
          const pct = typeof data.progressPct === "number" ? data.progressPct : undefined;
          const msg = data.message || undefined;
          setProgress((prev) => ({
            ...prev,
            progressPct: pct !== undefined ? pct : prev.progressPct,
            nodeDescription: msg || prev.nodeDescription,
          }));
        } else if (eventType === "node.finished") {
          const pct = typeof data.progressPct === "number" ? data.progressPct : undefined;
          setProgress((prev) => ({
            ...prev,
            progressPct: pct !== undefined ? pct : prev.progressPct,
          }));
        } else if (eventType === "run.warning") {
          setProgress((prev) => {
            const newEv: ResearchRunEvent = {
              id: Date.now(),
              runId,
              seq: prev.events.length > 0 ? prev.events[0].seq + 1 : 1,
              node: data.node || "runner",
              level: "WARN",
              message: data.message || "Warning during run execution",
              data: data.data || {},
              createdAt: new Date().toISOString(),
            };
            return {
              ...prev,
              events: [newEv, ...prev.events],
            };
          });
        } else if (eventType === "run.completed") {
          setProgress((prev) => ({
            ...prev,
            state: data.state || "COMPLETED",
            progressPct: 100,
            nodeDescription: data.state === "PARTIAL" ? "Finished with partial results" : "Completed successfully",
            stats: data.stats || prev.stats,
          }));
          es.close();
        } else if (eventType === "run.failed") {
          setProgress((prev) => ({
            ...prev,
            state: "FAILED",
            nodeDescription: `Failed: ${data.error || "Unknown error"}`,
            error: data.error,
          }));
          es.close();
        }
      } catch (err) {
        console.error("Failed to parse SSE event:", err);
      }
    };

    es.onmessage = handleEvent;

    // Specific event listeners if named
    const eventNames = [
      "run.started",
      "node.started",
      "node.progress",
      "node.finished",
      "run.warning",
      "run.completed",
      "run.failed",
    ];

    eventNames.forEach((name) => {
      es.addEventListener(name, handleEvent as EventListener);
    });

    es.onerror = () => {
      // Reconnect handled automatically by EventSource, or closed when finished
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [runId]);

  return progress;
}
