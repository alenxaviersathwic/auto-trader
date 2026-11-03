import React, { useState } from "react";
import { Plus, CheckCircle2, AlertCircle, X } from "lucide-react";
import { useSessionSearch, useCreateSession, useUpdateSession, useDeleteSession } from "../hooks/useSessions";
import { TradingSession, TradingSessionSearchFilter } from "../types/sessions.types";
import { SessionDialog } from "../components/SessionDialog";

function statusBadgeClass(status: TradingSession["sessionStatus"]): string {
  if (status === "ACTIVE") return "badge badge--green";
  if (status === "CLOSED") return "badge badge--slate";
  return "badge badge--amber"; // EXPIRED
}

export const SessionsPage: React.FC = () => {
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

  const handleCreate = async (payload: Parameters<typeof createMutation.mutateAsync>[0]) => {
    const created = await createMutation.mutateAsync(payload);
    showToast("success", `Session "${created.name}" created`);
    return created;
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
          <p className="text-secondary micro">{data?.totalItems ?? 0} session{(data?.totalItems ?? 0) === 1 ? "" : "s"}</p>
        </div>
        <div className="page-actions">
          <button type="button" className="btn btn--primary" onClick={() => setIsDialogOpen(true)}>
            <Plus size={16} />
            <span>New Session</span>
          </button>
        </div>
      </div>

      <div className="content-body">
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Trade Date</th>
                <th>Scope</th>
                <th>Underlyings</th>
                <th>Capital</th>
                <th>Type</th>
                <th>Routing</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={9} className="text-muted">Loading sessions...</td>
                </tr>
              )}
              {!isLoading && sessions.length === 0 && (
                <tr>
                  <td colSpan={9} className="text-muted">No trading sessions yet. Create one to get started.</td>
                </tr>
              )}
              {sessions.map((s) => (
                <tr key={s.id}>
                  <td className="text-primary">{s.name}</td>
                  <td className="mono">{s.tradeDate}</td>
                  <td>{s.scope}</td>
                  <td className="micro">{(s.scope === "INDEX" ? s.underlyings : s.commodityItems).join(", ")}</td>
                  <td className="mono">₹{Number(s.capital).toLocaleString("en-IN")}</td>
                  <td>{s.sessionType}</td>
                  <td>{s.routeThroughUpstox ? "LIVE" : "Simulated"}</td>
                  <td><span className={statusBadgeClass(s.sessionStatus)}>{s.sessionStatus}</span></td>
                  <td>
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
              ))}
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
