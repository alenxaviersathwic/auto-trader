import React from "react";
import { useNavigate, useParams } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { UNDERLYING_NAMES } from "../components/underlyingNames";
import { SuggestionCard } from "../components/SuggestionCard";
import { useLatestSuggestions, useSuggestionLoop } from "../hooks/useSuggestion";

export const SuggestionDetailPage: React.FC = () => {
  const { underlying } = useParams({ strict: false }) as { underlying?: string };
  const navigate = useNavigate();
  const loop = useSuggestionLoop();
  const code = (underlying ?? "").toUpperCase();
  const { data: latest } = useLatestSuggestions(loop.running, code);
  const items = latest?.list ?? [];

  return (
    <div className="page-container sp-page">
      <div className="sp-header">
        <div>
          <div className="sp-eyebrow">Suggestion Engine</div>
          <div className="sp-title-row">
            <h1 className="sp-title">{code}</h1>
            <span className="sp-muted">{UNDERLYING_NAMES[code] ?? ""}</span>
            <span className="badge badge--green">{items.length} Suggestions</span>
          </div>
        </div>
        <div className="sp-actions">
          <button type="button" className="sp-btn" onClick={() => navigate({ to: "/suggestion" })}>
            <ArrowLeft size={14} /> Back
          </button>
        </div>
      </div>
      {items.length === 0 ? (
        <div className="sp-empty">
          <div className="sp-empty-title">No current suggestions for {code}</div>
          <p className="sp-muted">Start this underlying from the Suggestion Engine page.</p>
        </div>
      ) : (
        <div className="sp-stack">
          {items.map((s) => (
            <SuggestionCard key={s.id} suggestion={s} />
          ))}
        </div>
      )}
    </div>
  );
};
