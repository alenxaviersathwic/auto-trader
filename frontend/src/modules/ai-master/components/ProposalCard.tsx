import React, { useState } from "react";
import {
  Proposal, ConfirmMode, Complication
} from "../types/master.types";
import {
  CheckCircle2, XCircle, AlertTriangle, Info, RefreshCw,
  ChevronDown, ChevronUp, Zap
} from "lucide-react";

interface Props {
  proposal: Proposal;
  onConfirm: (id: number, mode: ConfirmMode, acked: string[], typed?: string) => void;
  onReject: (id: number, reason?: string) => void;
  onRevalidate: (id: number) => void;
  isConfirming?: boolean;
  isRejecting?: boolean;
}

const SEVERITY_ICON: Record<string, React.ReactNode> = {
  BLOCKER: <XCircle size={14} className="text-error" />,
  WARNING: <AlertTriangle size={14} className="text-warning" />,
  INFO: <Info size={14} className="text-info" />,
};

const CONFIRM_MODES: Array<{ value: ConfirmMode; label: string; desc: string }> = [
  { value: "ADD_AS_DRAFT", label: "Add as Draft", desc: "Save strategy/rule as inactive draft" },
  { value: "ADD_AND_ACTIVATE", label: "Add & Activate", desc: "Save and immediately activate" },
  { value: "APPLY", label: "Apply Changes", desc: "Apply edits to existing record" },
];

export const ProposalCard: React.FC<Props> = ({
  proposal,
  onConfirm,
  onReject,
  onRevalidate,
  isConfirming,
  isRejecting,
}) => {
  const [mode, setMode] = useState<ConfirmMode>("ADD_AS_DRAFT");
  const [acked, setAcked] = useState<Set<string>>(new Set());
  const [typedPhrase, setTypedPhrase] = useState("");
  const [showDiff, setShowDiff] = useState(false);
  const [showPayload, setShowPayload] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [showReject, setShowReject] = useState(false);

  const blockers = proposal.complications.filter((c) => c.severity === "BLOCKER");
  const warnings = proposal.complications.filter((c) => c.severity === "WARNING");
  const infos = proposal.complications.filter((c) => c.severity === "INFO");

  const allBlockersAcked = blockers.every((b) => acked.has(b.code));
  const isExpired = new Date(proposal.expiresAt) < new Date();
  const needsTypedPhrase = blockers.length > 0;

  const toggleAck = (code: string) => {
    setAcked((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  const canConfirm =
    !isExpired &&
    allBlockersAcked &&
    (!needsTypedPhrase || typedPhrase.trim().toLowerCase() === "confirm");

  const kindLabel: Record<string, string> = {
    CREATE_STRATEGY: "Create Strategy",
    UPDATE_STRATEGY: "Update Strategy",
    CREATE_RULE: "Create Rule",
    UPDATE_RULE: "Update Rule",
    DELETE_STRATEGY: "Delete Strategy",
    DELETE_RULE: "Delete Rule",
  };

  const statusColor: Record<string, string> = {
    PENDING: "proposal-status--pending",
    CONFIRMED: "proposal-status--confirmed",
    REJECTED: "proposal-status--rejected",
    EXPIRED: "proposal-status--expired",
    EXECUTED: "proposal-status--confirmed",
    FAILED: "proposal-status--rejected",
  };

  return (
    <div className={`proposal-card${isExpired ? " proposal-card--expired" : ""}`}>
      {/* Header */}
      <div className="proposal-card-header">
        <div className="proposal-kind-badge">
          <Zap size={13} />
          {kindLabel[proposal.kind] ?? proposal.kind}
        </div>
        <span className={`proposal-status-pill ${statusColor[proposal.proposalStatus] ?? ""}`}>
          {proposal.proposalStatus}
        </span>
      </div>

      {/* Back-translation */}
      <div className="proposal-back-translation">
        <p className="proposal-label">What Master understood:</p>
        <p className="proposal-text">&ldquo;{proposal.backTranslation}&rdquo;</p>
      </div>

      {/* Assumptions */}
      {proposal.assumptions.length > 0 && (
        <div className="proposal-assumptions">
          <p className="proposal-label">Assumptions made:</p>
          <ul>
            {proposal.assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Complications */}
      {proposal.complications.length > 0 && (
        <div className="proposal-complications">
          <p className="proposal-label">Complications:</p>
          {[...blockers, ...warnings, ...infos].map((c: Complication) => (
            <div key={c.code} className="complication-row">
              {SEVERITY_ICON[c.severity]}
              <div className="complication-content">
                <span className="complication-msg">{c.message}</span>
                <span className="complication-code">{c.code}</span>
              </div>
              {c.severity === "BLOCKER" && (
                <label className="complication-ack">
                  <input
                    type="checkbox"
                    checked={acked.has(c.code)}
                    onChange={() => toggleAck(c.code)}
                  />
                  Acknowledge
                </label>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Diff / Payload toggles */}
      <div className="proposal-toggles">
        {proposal.diff && (
          <button className="proposal-toggle-btn" onClick={() => setShowDiff(!showDiff)}>
            {showDiff ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            Diff
          </button>
        )}
        <button className="proposal-toggle-btn" onClick={() => setShowPayload(!showPayload)}>
          {showPayload ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          Payload
        </button>
      </div>

      {showDiff && proposal.diff && (
        <pre className="proposal-code">{JSON.stringify(proposal.diff, null, 2)}</pre>
      )}
      {showPayload && (
        <pre className="proposal-code">{JSON.stringify(proposal.payload, null, 2)}</pre>
      )}

      {/* Actions — only for PENDING */}
      {proposal.proposalStatus === "PENDING" && !isExpired && (
        <div className="proposal-actions">
          {/* Mode selector */}
          <div className="proposal-mode-select">
            {CONFIRM_MODES.map((m) => (
              <label key={m.value} className={`proposal-mode-btn${mode === m.value ? " active" : ""}`}>
                <input
                  type="radio"
                  name={`mode-${proposal.id}`}
                  value={m.value}
                  checked={mode === m.value}
                  onChange={() => setMode(m.value)}
                />
                <span className="proposal-mode-label">{m.label}</span>
                <span className="proposal-mode-desc">{m.desc}</span>
              </label>
            ))}
          </div>

          {/* Typed confirmation if blockers exist */}
          {needsTypedPhrase && (
            <div className="proposal-typed-confirm">
              <p className="proposal-label">
                Type <strong>confirm</strong> to acknowledge all blockers:
              </p>
              <input
                className="proposal-typed-input"
                placeholder="confirm"
                value={typedPhrase}
                onChange={(e) => setTypedPhrase(e.target.value)}
              />
            </div>
          )}

          <div className="proposal-btn-row">
            <button
              id={`proposal-confirm-${proposal.id}`}
              className="btn-confirm"
              disabled={!canConfirm || isConfirming}
              onClick={() => onConfirm(proposal.id, mode, Array.from(acked), typedPhrase || undefined)}
            >
              <CheckCircle2 size={14} />
              {isConfirming ? "Confirming…" : "Confirm"}
            </button>

            <button
              className="btn-outline-muted"
              onClick={() => onRevalidate(proposal.id)}
              title="Recheck proposal against latest registry"
            >
              <RefreshCw size={13} />
            </button>

            <button
              className="btn-reject-toggle"
              onClick={() => setShowReject(!showReject)}
            >
              <XCircle size={13} />
              Reject
            </button>
          </div>

          {showReject && (
            <div className="proposal-reject-panel">
              <textarea
                className="proposal-reject-input"
                placeholder="Reason (optional)"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                rows={2}
              />
              <button
                className="btn-reject-confirm"
                disabled={isRejecting}
                onClick={() => onReject(proposal.id, rejectReason || undefined)}
              >
                {isRejecting ? "Rejecting…" : "Confirm Reject"}
              </button>
            </div>
          )}
        </div>
      )}

      {isExpired && (
        <div className="proposal-expired-msg">
          ⚠ This proposal has expired. Ask Master to re-propose.
        </div>
      )}
    </div>
  );
};
