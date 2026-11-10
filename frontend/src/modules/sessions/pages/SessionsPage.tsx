import React, { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Plus, CheckCircle2, AlertCircle, X, Zap } from "lucide-react";
import { useSessionSearch, useCreateSession, useUpdateSession, useDeleteSession } from "../hooks/useSessions";
import { TradingSession, TradingSessionSearchFilter } from "../types/sessions.types";
import { SessionDialog } from "../components/SessionDialog";
import { formatRupee } from "../../opportunities/components/formatters";

const signedRupee = (n: number): string =>
  n === 0 ? "₹0.00" : `${n > 0 ? "+" : "-"}${formatRupee(Math.abs(n))}`;

const hhmm = (iso: string): string =>
  new Date(iso).toLocaleTimeString("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

function statusBadgeClass(status: TradingSession["sessionStatus"]): string {
  if (status === "ACTIVE") return "badge badge--green";
  if (status === "CLOSED") return "badge badge--slate";
  return "badge badge--amber";
}

function sessionTypeBadgeClass(type: TradingSession["sessionType"]): string {
  if (type === "FULL_AUTO") return "badge badge--green";
  if (type === "SEMI_AUTO") return "badge badge--amber";
  return "badge badge--blue";
}

export const SessionsPage: React.FC = () => {
  const navigate = useNavigate();
  const [filter] = useState<TradingSessionSearchFilter>({
    page: 0,
    limit: 20,
    sortBy: "createdAt",
    sortDir: "desc",
    status: "ACTIVE",
  });

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const showToast = (type: "success" | "error", message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 4500);
  };

  const { data, isLoading } = useSessionSearch(filter);
  const createMutation = useCreateSession();
  const updateMutation = useUpdateSession();
  const deleteMutation = useDeleteSession();

  const sessions = data?.list || [];
  const activeCount = sessions.filter((s) => s.sessionStatus === "ACTIVE").length;
  const liveUpstoxCount = sessions.filter((s) => s.routeThroughUpstox).length;
  const totalCapital = sessions.reduce((acc, s) => acc + Number(s.capital || 0), 0);
  const netRealizedPnl = sessions.reduce((acc, s) => acc + Number(s.realizedPnl || 0), 0);

  const handleCreate = async (payload: Parameters<typeof createMutation.mutateAsync>[0]) => {
    const created = await createMutation.mutateAsync(payload);
    showToast("success", `Session "${created.name}" created`);
    return created;
  };

  const handleToggleUpstox = async (session: TradingSession) => {
    const nextState = !session.routeThroughUpstox;
    try {
      await updateMutation.mutateAsync({
        id: session.id,
        payload: { routeThroughUpstox: nextState },
      });
      showToast(
        "success",
        `${session.name}: Upstox live order routing ${nextState ? "ENABLED" : "DISABLED (Simulated)"}`,
      );
    } catch (err: any) {
      showToast("error", err?.message || "Failed to update Upstox routing");
    }
  };

  const handleClose = async (session: TradingSession) => {
    if (!window.confirm(`Close session "${session.name}"? It will stop accepting new activity.`)) return;
    try {
      await updateMutation.mutateAsync({ id: session.id, payload: { sessionStatus: "CLOSED" } });
      showToast("success", `Session "${session.name}" closed`);
    } catch (err: any) {
      showToast("error", err?.message || "Failed to close session");
    }
  };

  const handleDelete = async (session: TradingSession) => {
    if (!window.confirm(`Delete session "${session.name}"? This cannot be undone.`)) return;
    try {
      await deleteMutation.mutateAsync(session.id);
      showToast("success", `Session "${session.name}" deleted`);
    } catch (err: any) {
      showToast("error", err?.message || "Failed to delete session");
    }
  };

  return (
    <div className="page-container">
      {toast && (
        <div className={`toast-notification toast-${toast.type}`}>
          {toast.type === "success" ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
          <span>{toast.message}</span>
          <button type="button" className="toast-close" onClick={() => setToast(null)}>
            <X size={14} />
          </button>
        </div>
      )}

      <div className="page-header">
        <div>
          <h1 className="page-title">Trading Sessions</h1>
          <p className="text-secondary micro">
            Manage manual, semi-auto &amp; full-auto trading sessions and toggle live Upstox order execution
          </p>
        </div>
        <div className="page-actions">
          <button type="button" className="btn btn--primary" onClick={() => setIsDialogOpen(true)}>
            <Plus size={16} />
            <span>New Session</span>
          </button>
        </div>
      </div>

      <div className="content-body sl-page">
        {/* Executive KPI Strip */}
        <div className="sl-strip">
          <div className="sl-stat">
            <span className="label">TOTAL SESSIONS</span>
            <span className="sl-stat__value">{data?.totalItems ?? 0}</span>
            <span className="micro text-secondary">{activeCount} currently active</span>
          </div>
          <div className="sl-stat">
            <span className="label">UPSTOX LIVE ROUTED</span>
            <span className={`sl-stat__value ${liveUpstoxCount > 0 ? "text-green" : ""}`}>
              {liveUpstoxCount} / {sessions.length}
            </span>
            <span className="micro text-secondary">Direct broker order API</span>
          </div>
          <div className="sl-stat">
            <span className="label">CAPITAL ALLOCATED</span>
            <span className="sl-stat__value">{formatRupee(totalCapital)}</span>
            <span className="micro text-secondary">Across listed sessions</span>
          </div>
          <div className="sl-stat">
            <span className="label">REALIZED NET P&amp;L</span>
            <span
              className={`sl-stat__value ${
                netRealizedPnl > 0 ? "text-green" : netRealizedPnl < 0 ? "text-red" : ""
              }`}
            >
              {signedRupee(netRealizedPnl)}
            </span>
            <span className="micro text-secondary">Closed trader positions</span>
          </div>
          <div className="sl-stat">
            <span className="label">PARALLEL TRADER CAP</span>
            <span className="sl-stat__value">3 / Session</span>
            <span className="micro text-secondary">Dedicated 3s loop per pick</span>
          </div>
        </div>

        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Trade Date</th>
                <th>Hours (IST)</th>
                <th>Underlyings</th>
                <th className="num">Capital</th>
                <th className="num">Realized P&amp;L</th>
                <th>Mode</th>
                <th>Upstox Order Routing</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={10} className="text-muted">
                    Loading sessions...
                  </td>
                </tr>
              )}
              {!isLoading && sessions.length === 0 && (
                <tr>
                  <td colSpan={10} className="text-muted">
                    No trading sessions yet. Create one to get started.
                  </td>
                </tr>
              )}
              {sessions.map((s) => {
                const pnl = Number(s.realizedPnl || 0);
                return (
                  <tr
                    key={s.id}
                    onClick={() => navigate({ to: "/sessions/$id", params: { id: String(s.id) } })}
                    style={{ cursor: "pointer" }}
                  >
                    <td className="text-primary" style={{ fontWeight: 600 }}>
                      {s.name}
                    </td>
                    <td className="mono">{s.tradeDate}</td>
                    <td className="mono">
                      {hhmm(s.startAt)}–{hhmm(s.closeAt)}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                        <span className="badge badge--slate">{s.scope}</span>
                        {(s.scope === "INDEX" ? s.underlyings : s.commodityItems).map((u) => (
                          <span key={u} className="badge badge--blue">
                            {u}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="num mono">{formatRupee(s.capital)}</td>
                    <td
                      className={`num mono ${
                        pnl > 0 ? "text-green" : pnl < 0 ? "text-red" : "text-secondary"
                      }`}
                    >
                      {signedRupee(pnl)}
                    </td>
                    <td>
                      <span className={sessionTypeBadgeClass(s.sessionType)}>{s.sessionType}</span>
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        className={`upstox-switch-btn ${
                          s.routeThroughUpstox ? "upstox-switch-btn--live" : ""
                        }`}
                        onClick={() => handleToggleUpstox(s)}
                        disabled={updateMutation.isPending}
                        title="Toggle direct Upstox order API execution"
                      >
                        <div
                          className={`upstox-switch-track ${
                            s.routeThroughUpstox ? "upstox-switch-track--on" : ""
                          }`}
                        >
                          <div className="upstox-switch-thumb" />
                        </div>
                        <Zap size={12} />
                        <span>{s.routeThroughUpstox ? "UPSTOX LIVE" : "SIMULATED"}</span>
                      </button>
                    </td>
                    <td>
                      <span className={statusBadgeClass(s.sessionStatus)}>{s.sessionStatus}</span>
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <div className="page-actions">
                        {s.sessionStatus === "ACTIVE" && (
                          <button type="button" className="btn btn--ghost" onClick={() => handleClose(s)}>
                            Close
                          </button>
                        )}
                        <button type="button" className="btn btn--ghost" onClick={() => handleDelete(s)}>
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <SessionDialog
        isOpen={isDialogOpen}
        onClose={() => setIsDialogOpen(false)}
        onCreate={handleCreate}
      />
    </div>
  );
};
