import React, { useState } from "react";
import { useApplyDayShift } from "../hooks/useStrategies";
import { DayShiftResult } from "../types/strategies.types";

interface DayShiftModalProps {
  onClose: () => void;
}

/**
 * Holiday shift for all strategies at once:
 * every strategy scheduled on "Holiday date" gets BLOCK there and RUN on "Shift to" (if given).
 */
export const DayShiftModal: React.FC<DayShiftModalProps> = ({ onClose }) => {
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<DayShiftResult | null>(null);
  const mutation = useApplyDayShift();

  const sameDate = Boolean(fromDate && toDate && fromDate === toDate);

  const submit = () => {
    if (!fromDate || sameDate) return;
    mutation.mutate(
      { fromDate, toDate: toDate || null, reason: reason.trim() || null },
      { onSuccess: (res) => setResult(res) }
    );
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-title">Holiday shift</div>
        <div className="modal-body">
          {result ? (
            <div className="flex flex-col gap-2">
              <span>
                Applied to <span className="mono">{result.affectedCount}</span> strateg
                {result.affectedCount === 1 ? "y" : "ies"}.
              </span>
              {result.strategyCodes.length > 0 && (
                <span className="micro mono text-muted">{result.strategyCodes.join(", ")}</span>
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <span className="micro text-muted">
                Every strategy scheduled to run on the holiday date is blocked on that date and, if you set one,
                runs on the shift date instead.
              </span>
              <div className="form-group">
                <label className="form-label">Holiday date</label>
                <input type="date" className="input mono" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Shift to (optional)</label>
                <input
                  type="date"
                  className={`input mono ${sameDate ? "input--error" : ""}`}
                  value={toDate}
                  onChange={(e) => setToDate(e.target.value)}
                />
                {sameDate && <span className="form-error">Shift date must differ from holiday date</span>}
              </div>
              <div className="form-group">
                <label className="form-label">Reason</label>
                <input
                  type="text"
                  className="input"
                  maxLength={200}
                  placeholder="e.g. Guru Nanak Jayanti — weekly expiry moved"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </div>
            </div>
          )}
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            {result ? "Close" : "Cancel"}
          </button>
          {!result && (
            <button
              type="button"
              className="btn btn--primary"
              disabled={!fromDate || sameDate || mutation.isPending}
              onClick={submit}
            >
              {mutation.isPending ? "Applying..." : "Apply shift"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
