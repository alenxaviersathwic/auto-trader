import React, { useState } from "react";
import { useNavigate, useParams } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { UNDERLYING_NAMES } from "../components/underlyingNames";
import { OpportunityCard } from "../components/OpportunityCard";
import { OpportunityCheckItem } from "../types/opportunities.types";
import {
  useCheckOpportunity,
  useLatestOpportunities,
  useOpportunityLoop,
} from "../hooks/useOpportunities";

export const OpportunityDetailPage: React.FC = () => {
  const { underlying } = useParams({ strict: false }) as { underlying?: string };
  const navigate = useNavigate();
  const loop = useOpportunityLoop();
  const code = (underlying ?? "").toUpperCase();
  const { data: latest } = useLatestOpportunities(loop.running, code);
  const items = latest?.list ?? [];

  const [checked, setChecked] = useState<Record<number, OpportunityCheckItem>>({});
  const [checkingId, setCheckingId] = useState<number | null>(null);
  const checkOpportunity = useCheckOpportunity();

  const handleCheck = (opportunityId: number) => {
    setCheckingId(opportunityId);
    checkOpportunity.mutate(opportunityId, {
      onSuccess: (res) => setChecked((prev) => ({ ...prev, [opportunityId]: res })),
      onSettled: () => setCheckingId(null),
    });
  };

  return (
    <div className="page-container sp-page">
      <div className="sp-header">
        <div>
          <div className="sp-eyebrow">Opportunities</div>
          <div className="sp-title-row">
            <h1 className="sp-title">{code}</h1>
            <span className="sp-muted">{UNDERLYING_NAMES[code] ?? ""}</span>
            <span className="badge badge--green">{items.length} Opportunities</span>
          </div>
        </div>
        <div className="sp-actions">
          <button type="button" className="sp-btn" onClick={() => navigate({ to: "/opportunities" })}>
            <ArrowLeft size={14} /> Back
          </button>
        </div>
      </div>
      {items.length === 0 ? (
        <div className="sp-empty">
          <div className="sp-empty-title">No current opportunities for {code}</div>
          <p className="sp-muted">Start this underlying from the Opportunities page.</p>
        </div>
      ) : (
        <div className="sp-stack">
          {items.map((s) => (
            <OpportunityCard
              key={s.id}
              opportunity={s}
              checkResult={checked[s.id]}
              isChecking={checkingId === s.id}
              onCheck={handleCheck}
              defaultExpanded
            />
          ))}
        </div>
      )}
    </div>
  );
};
