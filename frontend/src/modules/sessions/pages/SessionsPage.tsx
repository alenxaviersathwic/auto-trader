import React, { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  Clock,
  Layers,
  LayoutGrid,
  Plus,
  Search,
  Square,
  Table as TableIcon,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import { useSessionSearch, useCreateSession, useUpdateSession, useDeleteSession } from "../hooks/useSessions";
import { TradingSession, TradingSessionSearchFilter } from "../types/sessions.types";
import { SessionDialog } from "../components/SessionDialog";
import { formatCompactRupee, formatRupee } from "../../opportunities/components/formatters";

type ScopeTab = "ALL" | "INDEX" | "COMMODITY";
type ViewMode = "grid" | "table";

const hhmm = (iso: string): string =>
  new Date(iso).toLocaleTimeString("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

const signedRupee = (n: number): string =>
  n === 0 ? "₹0.00" : `${n > 0 ? "+" : "-"}${formatRupee(Math.abs(n))}`;

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
  const [scopeTab, setScopeTab] = useState<ScopeTab>("ALL");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [searchInput, setSearchInput] = useState<string>("");

  const [filter, setFilter] = useState<TradingSessionSearchFilter>({
    page: 0,
    limit: 24,
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
  const totalItems = data?.totalItems ?? 0;

  const activeCount = sessions.filter((s) => s.sessionStatus === "ACTIVE").length;
  const liveUpstoxCount = sessions.filter((s) => s.routeThroughUpstox).length;
  const totalCapital = sessions.reduce((acc, s) => acc + Number(s.capital || 0), 0);
  const netRealizedPnl = sessions.reduce((acc, s) => acc + Number(s.realizedPnl || 0), 0);

  const handleScopeChange = (nextScope: ScopeTab) => {
    setScopeTab(nextScope);
    setFilter((prev) => ({
      ...prev,
      scope: nextScope === "ALL" ? undefined : nextScope,
      page: 0,
    }));
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFilter((prev) => ({ ...prev, query: searchInput.trim() || undefined, page: 0 }));
  };

  const handleClearSearch = () => {
    setSearchInput("");
    setFilter((prev) => ({ ...prev, query: undefined, page: 0 }));
  };

  const handleStatusChip = (st: "ALL" | "ACTIVE" | "CLOSED" | "EXPIRED") => {
    setFilter((prev) => ({
      ...prev,
      sessionStatus: st === "ALL" ? undefined : st,
      page: 0,
    }));
  };

  const handleModeChip = (mode: "ALL" | "MANUAL" | "SEMI_AUTO" | "FULL_AUTO") => {
    setFilter((prev) => ({
      ...prev,
      sessionType: mode === "ALL" ? undefined : mode,
      page: 0,
    }));
  };

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
    <div className="sp-page">
      {toast && (
        <div className={`toast-notification toast-${toast.type}`}>
          {toast.type === "success" ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
          <span>{toast.message}</span>
          <button type="button" className="toast-close" onClick={() => setToast(null)}>
            <X size={14} />
          </button>
        </div>
      )}

      {/* Minimal High-Density Command & Summary Strip (matching StrategiesPage / OpportunitiesPage) */}
      <div className="sp-toolbar">
        <div className="sp-toolbar-left">
          <div className="sp-tabs" role="tablist">
            {(
              [
                { key: "ALL", label: "All Sessions" },
                { key: "INDEX", label: "Indices" },
                { key: "COMMODITY", label: "Commodities" },
              ] as const
            ).map((t) => (
              <button
                key={t.key}
                type="button"
                role="tab"
                aria-selected={scopeTab === t.key}
                className={`sp-tab ${scopeTab === t.key ? "sp-tab--active" : ""}`}
                onClick={() => handleScopeChange(t.key)}
              >
                <Layers size={13} />
                <span>{t.label}</span>
                {scopeTab === t.key && <span className="sp-tab-count mono">{totalItems}</span>}
              </button>
            ))}
          </div>

          <div className="sp-summary-strip">
            <div className="sp-stat-pill" title="Active sessions vs total sessions">
              <span className={`sp-status-dot ${activeCount > 0 ? "sp-status-dot--live" : ""}`} />
              <span className="sp-stat-label">Active</span>
              <span className="sp-stat-val mono sp-up">{activeCount}</span>
              <span className="sp-stat-sub mono">/ {totalItems}</span>
            </div>

            <div className="sp-stat-pill" title="Sessions with direct Upstox order API enabled">
              <Zap size={12} className={liveUpstoxCount > 0 ? "sp-up" : ""} />
              <span className="sp-stat-label">Upstox Live</span>
              <span className={`sp-stat-val mono ${liveUpstoxCount > 0 ? "sp-up" : ""}`}>
                {liveUpstoxCount}
              </span>
            </div>

            <div className="sp-stat-pill" title="Total capital allocated across sessions">
              <span className="sp-stat-label">Capital</span>
              <span className="sp-stat-val mono">{formatCompactRupee(totalCapital)}</span>
            </div>

            <div className="sp-stat-pill" title="Net realized P&L across sessions">
              <span className="sp-stat-label">Net P&amp;L</span>
              <span
                className={`sp-stat-val mono ${
                  netRealizedPnl > 0 ? "sp-up" : netRealizedPnl < 0 ? "sp-down" : ""
                }`}
              >
                {signedRupee(netRealizedPnl)}
              </span>
            </div>
          </div>
        </div>

        <div className="sp-actions">
          <button
            type="button"
            className="sp-btn"
            onClick={() => navigate({ to: "/trades" })}
          >
            <Activity size={13} /> Active Trader Cockpit
          </button>
          <button
            type="button"
            className="sp-btn sp-btn--run"
            onClick={() => setIsDialogOpen(true)}
          >
            <Plus size={14} strokeWidth={2.5} /> New Session
          </button>
        </div>
      </div>

      {/* Controls Bar: Search, Status Filter Chips, Mode Chips, View Toggle */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "12px",
          flexWrap: "wrap",
          background: "var(--bg-card)",
          padding: "10px 14px",
          borderRadius: "var(--radius-md)",
          border: "1px solid var(--border-subtle)",
        }}
      >
        <form
          onSubmit={handleSearchSubmit}
          style={{ position: "relative", flex: "1", minWidth: "220px", maxWidth: "320px" }}
        >
          <Search
            size={14}
            color="var(--text-muted)"
            style={{ position: "absolute", left: "10px", top: "50%", transform: "translateY(-50%)" }}
          />
          <input
            type="text"
            className="input"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search session name..."
            style={{ paddingLeft: "30px", height: "32px", fontSize: "0.78rem" }}
          />
          {searchInput && (
            <button
              type="button"
              onClick={handleClearSearch}
              style={{
                position: "absolute",
                right: "8px",
                top: "50%",
                transform: "translateY(-50%)",
                background: "transparent",
                border: 0,
                color: "var(--text-muted)",
                cursor: "pointer",
              }}
            >
              <X size={13} />
            </button>
          )}
        </form>

        <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
          <div className="toggle-chip-group">
            {(["ALL", "ACTIVE", "CLOSED", "EXPIRED"] as const).map((st) => {
              const isSelected = (filter.sessionStatus ?? "ALL") === st;
              return (
                <button
                  key={st}
                  type="button"
                  className={`toggle-chip ${isSelected ? "toggle-chip--active" : ""}`}
                  onClick={() => handleStatusChip(st)}
                >
                  {st}
                </button>
              );
            })}
          </div>

          <div
            style={{
              width: "1px",
              height: "18px",
              background: "var(--border-subtle)",
              margin: "0 2px",
            }}
          />

          <div className="toggle-chip-group">
            {(["ALL", "MANUAL", "SEMI_AUTO", "FULL_AUTO"] as const).map((m) => {
              const isSelected = (filter.sessionType ?? "ALL") === m;
              return (
                <button
                  key={m}
                  type="button"
                  className={`toggle-chip ${isSelected ? "toggle-chip--active" : ""}`}
                  onClick={() => handleModeChip(m)}
                >
                  {m === "ALL" ? "ALL MODES" : m}
                </button>
              );
            })}
          </div>

          <div
            style={{
              width: "1px",
              height: "18px",
              background: "var(--border-subtle)",
              margin: "0 2px",
            }}
          />

          <div style={{ display: "inline-flex", gap: "4px" }}>
            <button
              type="button"
              className={`toggle-chip ${viewMode === "grid" ? "toggle-chip--active" : ""}`}
              onClick={() => setViewMode("grid")}
              title="Grid View"
            >
              <LayoutGrid size={13} />
            </button>
            <button
              type="button"
              className={`toggle-chip ${viewMode === "table" ? "toggle-chip--active" : ""}`}
              onClick={() => setViewMode("table")}
              title="Table View"
            >
              <TableIcon size={13} />
            </button>
          </div>
        </div>
      </div>

      {/* Empty / Loading States */}
      {isLoading ? (
        <div className="sp-empty">
          <div className="sp-empty-title">Loading trading sessions…</div>
        </div>
      ) : sessions.length === 0 ? (
        <div className="sp-empty">
          <Activity size={26} />
          <div className="sp-empty-title">No trading sessions found</div>
          <p className="sp-muted">
            Create a session to start scanning opportunities and launching active Trader loops.
          </p>
          <button
            type="button"
            className="sp-btn sp-btn--run"
            style={{ marginTop: "8px" }}
            onClick={() => setIsDialogOpen(true)}
          >
            <Plus size={14} /> Create First Session
          </button>
        </div>
      ) : viewMode === "grid" ? (
        /* Grid Cards View (matching OpportunitiesPage / StrategiesPage cards) */
        <div className="sp-grid">
          {sessions.map((s) => {
            const isRunning = s.sessionStatus === "ACTIVE";
            const pnl = Number(s.realizedPnl || 0);
            const currentCap = Number(s.currentCapital || s.capital || 0);
            const maxLossAmt = (Number(s.capital || 0) * Number(s.maxLossPercentage || 3)) / 100;
            const underlyings = s.scope === "INDEX" ? s.underlyings : s.commodityItems;
            const tone = pnl > 0 ? "sp-card--bull" : pnl < 0 ? "sp-card--bear" : "";

            return (
              <div
                key={s.id}
                className={`sp-card ${tone} ${isRunning ? "sp-card--running" : ""}`}
                onClick={() => navigate({ to: "/sessions/$id", params: { id: String(s.id) } })}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    navigate({ to: "/sessions/$id", params: { id: String(s.id) } });
                  }
                }}
              >
                {/* Card Top Header */}
                <div className="sp-card-top">
                  <div className="sp-card-title-group">
                    <div className="sp-symbol-row" style={{ flexWrap: "wrap", gap: "6px" }}>
                      <span
                        className={`sp-symbol ${
                          s.scope === "INDEX" ? "sp-symbol--index" : "sp-symbol--commodity"
                        }`}
                      >
                        {s.scope}
                      </span>
                      <h2 className="sp-name">{s.name}</h2>
                      <span className={sessionTypeBadgeClass(s.sessionType)}>{s.sessionType}</span>
                    </div>
                  </div>

                  <div className="sp-card-badges" onClick={(e) => e.stopPropagation()}>
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
                      <Zap size={11} />
                      <span>{s.routeThroughUpstox ? "UPSTOX LIVE" : "SIMULATED"}</span>
                    </button>
                  </div>
                </div>

                {/* Underlyings Strip */}
                <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", padding: "2px 0" }}>
                  {underlyings.map((code) => (
                    <span key={code} className="badge badge--blue mono">
                      {code}
                    </span>
                  ))}
                </div>

                {/* 4-Column Compact Telemetry Strip */}
                <div className="sp-metrics">
                  <div className="sp-metric-cell">
                    <div className="sp-metric-label">Status</div>
                    <div className="sp-metric-value">
                      {isRunning ? (
                        <span className="sp-state-pill sp-state-pill--running">
                          <span className="sp-pulse-dot" /> ACTIVE
                        </span>
                      ) : (
                        <span className="sp-state-pill sp-state-pill--stopped">
                          {s.sessionStatus}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="sp-metric-cell">
                    <div className="sp-metric-label">Capital</div>
                    <div className="sp-metric-value mono">{formatCompactRupee(s.capital)}</div>
                  </div>

                  <div className="sp-metric-cell">
                    <div className="sp-metric-label">Current Equity</div>
                    <div className="sp-metric-value mono">{formatCompactRupee(currentCap)}</div>
                  </div>

                  <div className="sp-metric-cell">
                    <div className="sp-metric-label">Realized P&amp;L</div>
                    <div
                      className={`sp-metric-value mono ${
                        pnl > 0 ? "sp-up" : pnl < 0 ? "sp-down" : ""
                      }`}
                    >
                      {signedRupee(pnl)}
                    </div>
                  </div>
                </div>

                {/* Card Footer */}
                <div className="sp-card-foot">
                  <div className="sp-foot-left">
                    <span className="sp-foot-time mono">
                      <Clock size={11} />
                      {s.tradeDate} · {hhmm(s.startAt)}–{hhmm(s.closeAt)} IST
                    </span>
                    <span className="sp-dot">·</span>
                    <span className="mono micro text-secondary">
                      Max Loss {s.maxLossPercentage}% ({formatCompactRupee(maxLossAmt)})
                    </span>
                  </div>

                  <div
                    style={{ display: "flex", alignItems: "center", gap: "8px" }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {isRunning && (
                      <button
                        type="button"
                        className="sp-card-action sp-card-action--stop"
                        onClick={() => handleClose(s)}
                        title="Close session"
                      >
                        <Square size={10} /> Close
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn--ghost"
                      style={{ padding: "2px 6px" }}
                      onClick={() => handleDelete(s)}
                      title="Delete session"
                    >
                      <Trash2 size={12} />
                    </button>
                    <span
                      className="sp-inspect-link"
                      onClick={() => navigate({ to: "/sessions/$id", params: { id: String(s.id) } })}
                    >
                      <span>Open</span>
                      <ChevronRight size={13} />
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* Table View */
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
      )}

      <SessionDialog
        isOpen={isDialogOpen}
        onClose={() => setIsDialogOpen(false)}
        onCreate={handleCreate}
      />
    </div>
  );
};
