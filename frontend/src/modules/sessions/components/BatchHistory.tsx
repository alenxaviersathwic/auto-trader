import React, { useState } from "react";
import { History, Loader2, ScanSearch } from "lucide-react";
import { useAnalyseSessionBatch, useSessionBatches } from "../hooks/useSessions";
import { BatchVerdict, ManagerVerdict, SessionBatch, SessionPick } from "../types/sessions.types";
import { formatSignedRupee } from "../../opportunities/components/formatters";

const PAGE_SIZE = 10;
const hms = (iso: string): string =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false });

const BATCH_TONE: Record<BatchVerdict, { cls: string; pill: string; label: string }> = {
  SUCCESS: { cls: "te-batch--success", pill: "te-pill--green", label: "SUCCESS" },
  FAILURE: { cls: "te-batch--failure", pill: "te-pill--red", label: "FAILURE" },
  MIXED: { cls: "te-batch--mixed", pill: "te-pill--amber", label: "MIXED" },
  NO_MOVE: { cls: "", pill: "", label: "NO MOVE" },
  PENDING: { cls: "", pill: "te-pill--blue", label: "PENDING" },
};

const PICK_TONE: Record<ManagerVerdict, { pill: string; label: string }> = {
  TAKEN_WIN: { pill: "te-pill--green", label: "TAKEN · WIN" },
  TAKEN_LOSS: { pill: "te-pill--red", label: "TAKEN · LOSS" },
  TAKEN_RUNNING: { pill: "te-pill--cyan", label: "TAKEN · LIVE" },
  LOCKED_NOT_ENTERED: { pill: "te-pill--amber", label: "LOCKED ONLY" },
  MISSED_WINNER: { pill: "te-pill--amber", label: "MISSED WINNER" },
  GOOD_SKIP: { pill: "te-pill--green", label: "GOOD SKIP" },
  NO_MOVE: { pill: "", label: "NO MOVE" },
  PENDING: { pill: "te-pill--blue", label: "PENDING" },
};

const PickRow: React.FC<{ p: SessionPick }> = ({ p }) => {
  const a = p.outcomeAnalysis;
  const tone = a ? PICK_TONE[a.managerVerdict] : null;
  return (
    <div className="te-batch__row">
      <div className="te-row__main">
        <span className="te-row__title">
          <span className="mono">
            {p.underlyingCode} {p.strike} {p.optionType}
          </span>
          {p.strategy && <span className="te-pill">{p.strategy.replace(/_/g, " ")}</span>}
        </span>
        <span className="te-row__sub">
          ₹{p.entry.toFixed(2)} → stop ₹{p.stop.toFixed(2)} / target ₹{p.target.toFixed(2)} · {p.pickState}
        </span>
      </div>
      <span className="te-row__sub">
        {a ? a.note : "Not analysed yet"}
        {a?.candleError ? ` (${a.candleError})` : ""}
      </span>
      {tone ? <span className={`te-pill ${tone.pill}`}>{tone.label}</span> : <span className="te-pill">—</span>}
    </div>
  );
};

const BatchCard: React.FC<{ b: SessionBatch; analysing: boolean; onAnalyse: (key: string) => void }> = ({
  b,
  analysing,
  onAnalyse,
}) => {
  const tone = b.verdict ? BATCH_TONE[b.verdict] : null;
  const takenPnl = b.picks.reduce((sum, p) => sum + (p.outcomeAnalysis?.trade?.netPnl ?? 0), 0);
  return (
    <article className={`te-batch ${tone?.cls ?? ""}`}>
      <div className="te-batch__head">
        <div className="te-batch__title">
          <span className="te-batch__no">Batch #{b.batchNo}</span>
          <span className="te-pill">{hms(b.offeredAt)} IST</span>
          <span className="te-pill">
            {b.summary.picks} pick{b.summary.picks === 1 ? "" : "s"}
          </span>
          {b.summary.entered > 0 && <span className="te-pill te-pill--cyan">{b.summary.entered} entered</span>}
          {tone && <span className={`te-pill ${tone.pill}`}>{tone.label}</span>}
          {b.verdict && b.summary.taken ? (
            <span className={`mono micro ${takenPnl >= 0 ? "text-green" : "text-red"}`}>{formatSignedRupee(takenPnl, true)}</span>
          ) : null}
        </div>
        <button
          type="button"
          className="te-btn te-btn--ghost te-btn--sm"
          onClick={() => onAnalyse(b.batchKey)}
          disabled={analysing}
          title="Check every pick against real 1-minute candles and the trades taken from it"
        >
          {analysing ? <Loader2 size={12} className="sp-spin" /> : <ScanSearch size={12} />}
          {analysing ? "Analysing…" : b.verdict ? "Re-analyse" : "Analyse"}
        </button>
      </div>
      {b.summary.note && <div className="te-batch__note">{b.summary.note}</div>}
      <div className="te-batch__rows">
        {b.picks.map((p) => (
          <PickRow key={p.id} p={p} />
        ))}
      </div>
    </article>
  );
};

/** History tab: every loop pass ("batch") with its picks, and the session manager's success / failure check. */
export const BatchHistory: React.FC<{ sessionId: number }> = ({ sessionId }) => {
  const [page, setPage] = useState(0);
  const filter = { page, limit: PAGE_SIZE, sortBy: "createdAt", sortDir: "desc" as const };
  const { data, isLoading } = useSessionBatches(sessionId, filter);
  const analyse = useAnalyseSessionBatch(sessionId);
  const batches = data?.list ?? [];

  if (isLoading) return <div className="te-empty">Loading batches…</div>;
  if (batches.length === 0) {
    return (
      <div className="te-empty">
        <History size={14} /> No batches yet. A batch is every setup one loop pass offered to this session.
      </div>
    );
  }
  return (
    <div className="te-desk">
      {analyse.isError && (
        <div className="te-notice">{analyse.error instanceof Error ? analyse.error.message : "Analysis failed"}</div>
      )}
      {batches.map((b) => (
        <BatchCard
          key={b.batchKey}
          b={b}
          analysing={analyse.isPending && analyse.variables === b.batchKey}
          onAnalyse={(key) => analyse.mutate(key)}
        />
      ))}
      {(data?.totalPages ?? 0) > 1 && (
        <div className="te-tabs">
          <button type="button" className="te-btn te-btn--ghost te-btn--sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            Newer
          </button>
          <span className="micro text-muted">
            Page {page + 1} of {data?.totalPages}
          </span>
          <button
            type="button"
            className="te-btn te-btn--ghost te-btn--sm"
            disabled={page + 1 >= (data?.totalPages ?? 0)}
            onClick={() => setPage((p) => p + 1)}
          >
            Older
          </button>
        </div>
      )}
    </div>
  );
};
