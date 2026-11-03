import React from "react";
import { useNavigate, useParams } from "@tanstack/react-router";
import { ArrowLeft, Radio, AlertTriangle } from "lucide-react";
import { useSessionDetail } from "../hooks/useSessions";
import { useSessionOpportunityStream } from "../hooks/useSessionOpportunityStream";
import { OpportunityCard } from "../../opportunities/components/OpportunityCard";
import { UNDERLYING_NAMES } from "../../opportunities/components/underlyingNames";
import { TradingSession } from "../types/sessions.types";

function statusBadgeClass(status: TradingSession["sessionStatus"]): string {
  if (status === "ACTIVE") return "badge badge--green";
  if (status === "CLOSED") return "badge badge--slate";
  return "badge badge--amber"; // EXPIRED
}

function connectionBadge(state: ReturnType<typeof useSessionOpportunityStream>["connectionState"]) {
  switch (state) {
    case "open":
      return { cls: "badge badge--green", label: "Live" };
    case "connecting":
      return { cls: "badge badge--amber", label: "Connecting" };
    case "error":
      return { cls: "badge badge--red", label: "Disconnected" };
    default:
      return { cls: "badge badge--slate", label: "Idle" };
  }
}

export const SessionDetailPage: React.FC = () => {
  const { id } = useParams({ strict: false }) as { id: string };
  const navigate = useNavigate();
  const sessionId = Number(id);

  const { data: session, isLoading } = useSessionDetail(sessionId);

  const underlyings = session
    ? session.scope === "INDEX"
      ? session.underlyings
      : session.commodityItems
    : [];

  const { connectionState, batches, errors } = useSessionOpportunityStream(underlyings);
  const conn = connectionBadge(connectionState);

  if (isLoading || !session) {
    return (
      <div className="page-container">
        <div className="empty-state">
          <div className="empty-state__title">Loading session...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <button type="button" className="btn btn--ghost" onClick={() => navigate({ to: "/sessions" })}>
            <ArrowLeft size={14} />
            <span>Back</span>
          </button>
          <h1 className="page-title" style={{ marginTop: "var(--space-2)" }}>{session.name}</h1>
          <p className="text-secondary micro">
            {session.tradeDate} · {session.scope} · {session.sessionType}
          </p>
        </div>
        <div className="page-actions">
          <span className={conn.cls}>
            <Radio size={12} />
            <span>{conn.label}</span>
          </span>
          <span className={statusBadgeClass(session.sessionStatus)}>{session.sessionStatus}</span>
        </div>
      </div>

      <div className="content-body">
        <div className="card" style={{ display: "flex", gap: "var(--space-6)", flexWrap: "wrap" }}>
          <div>
            <div className="label">Capital</div>
            <div className="mono text-primary">₹{Number(session.capital).toLocaleString("en-IN")}</div>
          </div>
          <div>
            <div className="label">Max Loss / Session</div>
            <div className="mono text-primary">{session.maxLossPercentage}%</div>
          </div>
          <div>
            <div className="label">Routing</div>
            <div className="text-primary">{session.routeThroughUpstox ? "Live (Upstox)" : "Simulated"}</div>
          </div>
          <div>
            <div className="label">Watching</div>
            <div className="text-primary micro">
              {underlyings.map((u) => `${u} (${UNDERLYING_NAMES[u] ?? u})`).join(", ") || "None selected"}
            </div>
          </div>
        </div>

        {errors.length > 0 && (
          <div className="card" style={{ borderColor: "var(--bearish-red)" }}>
            <div className="section-title" style={{ color: "var(--bearish-red)" }}>Stream Errors</div>
            {errors.map((e) => (
              <div key={e.key} className="micro text-secondary" style={{ display: "flex", gap: "var(--space-2)" }}>
                <AlertTriangle size={12} style={{ color: "var(--bearish-red)" }} />
                <span className="mono">{e.underlyingCode}</span>
                <span>#{e.iterationNo}</span>
                <span>{e.error}</span>
              </div>
            ))}
          </div>
        )}

        <div className="section-title">Live Opportunity Batches</div>

        {batches.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state__icon">
              <Radio size={36} />
            </div>
            <div className="empty-state__title">Waiting for the next batch</div>
            <div className="empty-state__body">
              Make sure a card session is running for {underlyings.join(", ") || "this session's underlyings"} from
              the Opportunities page -- this view only listens for batches, it does not start them.
            </div>
          </div>
        ) : (
          <div className="sp-stack">
            {batches.map((batch, idx) => (
              <div key={batch.key} className="card card--flat">
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-3)",
                    marginBottom: "var(--space-3)",
                  }}
                >
                  <span className="badge badge--blue mono">{batch.underlyingCode}</span>
                  <span className="micro text-muted">Iteration #{batch.iterationNo}</span>
                  <span className="micro text-muted mono">
                    {new Date(batch.receivedAt).toLocaleTimeString("en-IN", { hour12: false })} IST
                  </span>
                  <span className="micro text-muted">
                    {batch.count} opportunit{batch.count === 1 ? "y" : "ies"}
                  </span>
                  {batch.note && <span className="micro text-muted">· {batch.note}</span>}
                </div>
                {batch.opportunities.length > 0 && (
                  <div className="sp-stack">
                    {batch.opportunities.map((o) => (
                      <OpportunityCard key={o.id} opportunity={o} defaultExpanded={idx === 0} />
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
