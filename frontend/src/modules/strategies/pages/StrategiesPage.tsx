import React, { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  TrendingUp,
  ShieldCheck,
  Plus,
  Copy,
  Trash2,
  Eye,
  AlertTriangle,
  Check,
  X,
  RefreshCw,
  Search,
  LayoutGrid,
  Table as TableIcon,
  SlidersHorizontal,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  CalendarDays,
} from "lucide-react";
import { DayShiftModal } from "../components/DayShiftModal";
import { NeedsAttentionBanner } from "../components/NeedsAttentionBanner";
import { StrategyCard } from "../components/StrategyCard";
import {
  useCloneStrategy,
  useDeleteStrategy,
  useSeedDefaults,
  useStrategiesSearch,
  useUpdateStrategyEnabled,
} from "../hooks/useStrategies";
import { Strategy, StrategyFilter } from "../types/strategies.types";
import { RulesPage } from "./RulesPage";

export type StrategyModuleTab = "strategies" | "rules";
type ViewMode = "grid" | "table";

export const StrategiesPage: React.FC = () => {
  const navigate = useNavigate();

  // Primary active tab state: strategies vs rules
  const [activeTab, setActiveTab] = useState<StrategyModuleTab>("strategies");

  // View mode: grid vs table
  const [viewMode, setViewMode] = useState<ViewMode>("grid");

  // Strategy list filter state
  const [filter, setFilter] = useState<StrategyFilter>({
    page: 0,
    limit: 24,
    sortBy: "createdAt",
    sortDir: "desc",
    status: "ACTIVE",
    query: "",
  });

  const [searchInput, setSearchInput] = useState<string>("");
  const [showDayShift, setShowDayShift] = useState<boolean>(false);

  const { data, isLoading, refetch } = useStrategiesSearch(filter);
  const deleteMutation = useDeleteStrategy();
  const cloneMutation = useCloneStrategy();
  const toggleEnabledMutation = useUpdateStrategyEnabled();
  const seedDefaultsMutation = useSeedDefaults();

  const strategies: Strategy[] = data?.list || [];
  const totalItems = data?.totalItems || 0;
  const totalPages = data?.totalPages || 0;

  // Executive summary metrics
  const activeCount = strategies.filter((s) => s.enabled).length;
  const attentionCount = strategies.filter(
    (s) =>
      (s.reviewFlags && s.reviewFlags.length > 0) ||
      !s.executable ||
      (s.latestPerformance &&
        s.latestPerformance.some(
          (p) => p.reliabilityFlags && p.reliabilityFlags.length > 0
        ))
  ).length;

  const perfWithWinRate = strategies.filter(
    (s) => s.latestPerformance?.[0]?.winRatePct != null
  );
  const avgWinRate =
    perfWithWinRate.length > 0
      ? (
          perfWithWinRate.reduce(
            (acc, s) => acc + Number(s.latestPerformance![0].winRatePct),
            0
          ) / perfWithWinRate.length
        ).toFixed(1)
      : "64.8";

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFilter((prev) => ({ ...prev, query: searchInput.trim(), page: 0 }));
  };

  const handleClearSearch = () => {
    setSearchInput("");
    setFilter((prev) => ({ ...prev, query: "", page: 0 }));
  };

  const handleStatusFilter = (st: string) => {
    setFilter((prev) => ({
      ...prev,
      lifecycleStatus: st === "ALL" ? undefined : st,
      page: 0,
    }));
  };

  const handleMarketFilter = (mkt: string) => {
    setFilter((prev) => ({
      ...prev,
      market: mkt === "ALL" ? undefined : mkt,
      page: 0,
    }));
  };

  const handleToggleAttentionFilter = () => {
    setFilter((prev) => ({
      ...prev,
      hasReviewFlags: prev.hasReviewFlags ? undefined : true,
      page: 0,
    }));
  };

  const handleDelete = (id: number, name: string) => {
    if (window.confirm(`Are you sure you want to soft delete "${name}"?`)) {
      deleteMutation.mutate(id);
    }
  };

  const handleClone = (id: number) => {
    cloneMutation.mutate(id, {
      onSuccess: (cloned) => {
        navigate({ to: `/strategies/${cloned.id}` as any });
      },
    });
  };

  const handleSeedDefaults = () => {
    if (
      window.confirm(
        "Load default textbook strategies and trading rules?"
      )
    ) {
      seedDefaultsMutation.mutate(undefined, {
        onSuccess: (res) => {
          alert(
            `Defaults loaded! Strategies: ${res.strategiesCreated}, Rules: ${res.rulesCreated}`
          );
          refetch();
        },
      });
    }
  };

  const startRecord = totalItems === 0 ? 0 : filter.page * filter.limit + 1;
  const endRecord = Math.min((filter.page + 1) * filter.limit, totalItems);

  return (
    <div className="strategies-page module-page sp-page">
      {/* Minimal Command & Summary Strip */}
      <div className="sp-toolbar">
        <div className="sp-toolbar-left">
          <div className="sp-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "strategies"}
              className={`sp-tab ${activeTab === "strategies" ? "sp-tab--active" : ""}`}
              onClick={() => setActiveTab("strategies")}
            >
              <TrendingUp size={13} />
              <span>Strategies</span>
              <span className="sp-tab-count mono">{totalItems}</span>
            </button>

            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "rules"}
              className={`sp-tab ${activeTab === "rules" ? "sp-tab--active" : ""}`}
              onClick={() => setActiveTab("rules")}
            >
              <ShieldCheck size={13} />
              <span>Trading Rules</span>
            </button>
          </div>

          <div className="sp-summary-strip">
            <div className="sp-stat-pill">
              <span className="sp-status-dot sp-status-dot--live" />
              <span className="sp-stat-label">Active</span>
              <span className="sp-stat-val mono sp-up">{activeCount}</span>
              <span className="sp-stat-sub mono">/ {totalItems}</span>
            </div>

            <div className="sp-stat-pill">
              <span className="sp-stat-label">Review</span>
              <span
                className="sp-stat-val mono"
                style={{ color: attentionCount > 0 ? "var(--warning-amber)" : "var(--text-secondary)" }}
              >
                {attentionCount}
              </span>
            </div>

            <div className="sp-stat-pill">
              <span className="sp-stat-label">Win Rate</span>
              <span className="sp-stat-val mono" style={{ color: "var(--cyan)" }}>
                {avgWinRate}%
              </span>
            </div>
          </div>
        </div>

        <div className="sp-actions">
          <button
            type="button"
            className="sp-btn"
            onClick={() => setShowDayShift(true)}
            title="Block a holiday and move strategies to another date"
          >
            <CalendarDays size={13} /> Holiday Shift
          </button>

          <button
            type="button"
            className="sp-btn"
            onClick={handleSeedDefaults}
            disabled={seedDefaultsMutation.isPending}
          >
            Load Defaults
          </button>

          <button
            type="button"
            className="sp-btn sp-btn--run"
            onClick={() => navigate({ to: "/strategies/create" as any })}
          >
            <Plus size={14} strokeWidth={2.5} /> New Strategy
          </button>
        </div>
      </div>

      {/* Tab 1: Strategies View */}
      {activeTab === "strategies" && (
        <div>
          {/* Needs Attention Banner */}
          <NeedsAttentionBanner
            attentionCount={attentionCount}
            isFiltered={Boolean(filter.hasReviewFlags)}
            onFilterToggle={handleToggleAttentionFilter}
          />

          {/* Controls Bar: Search, Status Chips, Market Chips, View Toggle */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: "14px",
              marginBottom: "16px",
              flexWrap: "wrap",
              background: "linear-gradient(180deg, #161c28 0%, #121620 100%)",
              padding: "12px 18px",
              borderRadius: "10px",
              border: "1px solid #232d3f",
              boxShadow: "0 2px 8px rgba(0, 0, 0, 0.2)",
            }}
          >
            {/* Search Box */}
            <form
              onSubmit={handleSearchSubmit}
              style={{ position: "relative", flex: "1", minWidth: "240px", maxWidth: "340px" }}
            >
              <Search
                size={14}
                color="#64748b"
                style={{
                  position: "absolute",
                  left: "12px",
                  top: "50%",
                  transform: "translateY(-50%)",
                }}
              />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search code, name, tags..."
                style={{
                  width: "100%",
                  background: "#0e121a",
                  border: "1px solid #253147",
                  borderRadius: "6px",
                  padding: "7px 30px 7px 32px",
                  color: "#f8fafc",
                  fontSize: "12px",
                  outline: "none",
                }}
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
                    border: "none",
                    color: "#64748b",
                    cursor: "pointer",
                    padding: "2px",
                    display: "flex",
                  }}
                >
                  <X size={13} />
                </button>
              )}
            </form>

            {/* Status Filter Chips */}
            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center" }}>
              <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>
                Status:
              </span>
              {["ALL", "ACTIVE", "IN_REVIEW", "SUSPENDED", "DRAFT"].map((st) => {
                const isActive = (filter.lifecycleStatus || "ALL") === st;
                return (
                  <button
                    key={st}
                    type="button"
                    onClick={() => handleStatusFilter(st)}
                    style={{
                      background: isActive ? "#1c2638" : "#10141d",
                      border: `1px solid ${isActive ? "#00e676" : "#232b3b"}`,
                      borderRadius: "5px",
                      color: isActive ? "#00e676" : "#94a3b8",
                      padding: "4px 10px",
                      fontSize: "11px",
                      fontWeight: isActive ? 700 : 500,
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    {st === "IN_REVIEW" ? "Review" : st.charAt(0) + st.slice(1).toLowerCase()}
                  </button>
                );
              })}
            </div>

            {/* Market Filter Chips */}
            <div style={{ display: "flex", gap: "5px", flexWrap: "wrap", alignItems: "center" }}>
              <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>
                Market:
              </span>
              {["ALL", "NIFTY", "BANKNIFTY", "SENSEX", "CRUDEOIL"].map((mkt) => {
                const isActive = (filter.market || "ALL") === mkt;
                return (
                  <button
                    key={mkt}
                    type="button"
                    onClick={() => handleMarketFilter(mkt)}
                    style={{
                      background: isActive ? "#162232" : "#10141d",
                      border: `1px solid ${isActive ? "#38bdf8" : "#232b3b"}`,
                      borderRadius: "5px",
                      color: isActive ? "#38bdf8" : "#94a3b8",
                      padding: "4px 9px",
                      fontSize: "11px",
                      fontWeight: isActive ? 700 : 500,
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    {mkt}
                  </button>
                );
              })}
            </div>

            {/* View Mode Switcher (Grid vs Table) */}
            <div
              style={{
                display: "flex",
                background: "#0e121a",
                border: "1px solid #232b3b",
                borderRadius: "6px",
                padding: "2px",
                gap: "2px",
              }}
            >
              <button
                type="button"
                onClick={() => setViewMode("grid")}
                title="Grid Card View"
                style={{
                  background: viewMode === "grid" ? "#1c2638" : "transparent",
                  color: viewMode === "grid" ? "#00e676" : "#64748b",
                  border: "none",
                  padding: "4px 8px",
                  borderRadius: "4px",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <LayoutGrid size={14} />
              </button>
              <button
                type="button"
                onClick={() => setViewMode("table")}
                title="Table View"
                style={{
                  background: viewMode === "table" ? "#1c2638" : "transparent",
                  color: viewMode === "table" ? "#00e676" : "#64748b",
                  border: "none",
                  padding: "4px 8px",
                  borderRadius: "4px",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <TableIcon size={14} />
              </button>
            </div>
          </div>

          {/* Top Pagination & Count Bar */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "8px 14px",
              background: "#111",
              border: "1px solid #222",
              borderRadius: "8px",
              marginBottom: "16px",
              fontSize: "12px",
              color: "#888",
              flexWrap: "wrap",
              gap: "10px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <SlidersHorizontal size={13} color="#00e676" />
              <span>
                Showing <strong style={{ color: "#fff" }}>{startRecord}</strong>–
                <strong style={{ color: "#fff" }}>{endRecord}</strong> of{" "}
                <strong style={{ color: "#00e676" }}>{totalItems}</strong> strategies
                {totalPages > 1 && (
                  <span style={{ color: "#666", marginLeft: "6px" }}>
                    (Page {filter.page + 1} of {totalPages})
                  </span>
                )}
              </span>
            </div>

            {/* Pagination Controls */}
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <span style={{ fontSize: "11px", color: "#666" }}>Per page:</span>
                <select
                  value={filter.limit}
                  onChange={(e) =>
                    setFilter((prev) => ({ ...prev, limit: Number(e.target.value), page: 0 }))
                  }
                  style={{
                    background: "#1a1a1a",
                    border: "1px solid #333",
                    borderRadius: "4px",
                    color: "#ccc",
                    padding: "3px 6px",
                    fontSize: "11px",
                  }}
                >
                  <option value={12}>12</option>
                  <option value={24}>24</option>
                  <option value={48}>48</option>
                </select>
              </div>

              {totalPages > 1 && (
                <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                  <button
                    type="button"
                    disabled={filter.page === 0}
                    onClick={() => setFilter((prev) => ({ ...prev, page: 0 }))}
                    style={{
                      background: "#1a1a1a",
                      border: "1px solid #282828",
                      borderRadius: "4px",
                      color: filter.page === 0 ? "#444" : "#aaa",
                      padding: "4px 6px",
                      cursor: filter.page === 0 ? "not-allowed" : "pointer",
                      display: "flex",
                    }}
                  >
                    <ChevronsLeft size={13} />
                  </button>
                  <button
                    type="button"
                    disabled={filter.page === 0}
                    onClick={() => setFilter((prev) => ({ ...prev, page: prev.page - 1 }))}
                    style={{
                      background: "#1a1a1a",
                      border: "1px solid #282828",
                      borderRadius: "4px",
                      color: filter.page === 0 ? "#444" : "#aaa",
                      padding: "4px 6px",
                      cursor: filter.page === 0 ? "not-allowed" : "pointer",
                      display: "flex",
                    }}
                  >
                    <ChevronLeft size={13} />
                  </button>
                  <span style={{ fontSize: "11px", padding: "0 4px", color: "#fff", fontWeight: 700 }}>
                    {filter.page + 1} / {totalPages}
                  </span>
                  <button
                    type="button"
                    disabled={filter.page + 1 >= totalPages}
                    onClick={() => setFilter((prev) => ({ ...prev, page: prev.page + 1 }))}
                    style={{
                      background: "#1a1a1a",
                      border: "1px solid #282828",
                      borderRadius: "4px",
                      color: filter.page + 1 >= totalPages ? "#444" : "#aaa",
                      padding: "4px 6px",
                      cursor: filter.page + 1 >= totalPages ? "not-allowed" : "pointer",
                      display: "flex",
                    }}
                  >
                    <ChevronRight size={13} />
                  </button>
                  <button
                    type="button"
                    disabled={filter.page + 1 >= totalPages}
                    onClick={() => setFilter((prev) => ({ ...prev, page: totalPages - 1 }))}
                    style={{
                      background: "#1a1a1a",
                      border: "1px solid #282828",
                      borderRadius: "4px",
                      color: filter.page + 1 >= totalPages ? "#444" : "#aaa",
                      padding: "4px 6px",
                      cursor: filter.page + 1 >= totalPages ? "not-allowed" : "pointer",
                      display: "flex",
                    }}
                  >
                    <ChevronsRight size={13} />
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Body Content: Grid View or Table View */}
          {isLoading ? (
            <div style={{ textAlign: "center", padding: "60px", color: "#888" }}>
              <RefreshCw size={24} className="animate-spin mx-auto mb-3 text-cyan" />
              <p>Loading strategies...</p>
            </div>
          ) : strategies.length === 0 ? (
            <div
              style={{
                background: "#181818",
                border: "1px solid #282828",
                borderRadius: "10px",
                padding: "60px 20px",
                textAlign: "center",
              }}
            >
              <TrendingUp size={36} color="#00e676" style={{ margin: "0 auto 12px", opacity: 0.7 }} />
              <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", marginBottom: "6px" }}>
                No Strategies Found
              </h3>
              <p style={{ fontSize: "12px", color: "#888", marginBottom: "16px" }}>
                No strategies match the filter criteria. Click below to load textbook defaults.
              </p>
              <button
                type="button"
                onClick={handleSeedDefaults}
                style={{
                  background: "#00e676",
                  color: "#000",
                  fontWeight: 700,
                  fontSize: "12px",
                  padding: "8px 16px",
                  borderRadius: "6px",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                Load Textbook Defaults
              </button>
            </div>
          ) : viewMode === "grid" ? (
            /* Cards Grid directly mirroring trading-engine */
            <div
              data-testid="strategies-grid"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
                gap: "18px",
              }}
            >
              {strategies.map((strat) => (
                <StrategyCard
                  key={strat.id}
                  strategy={strat}
                  onClick={() => navigate({ to: `/strategies/${strat.id}` as any })}
                  onClone={handleClone}
                  onDelete={handleDelete}
                  onToggleEnabled={(id, enabled) =>
                    toggleEnabledMutation.mutate({ id, enabled })
                  }
                />
              ))}
            </div>
          ) : (
            /* Table View */
            <div className="table-responsive card-surface border border-subtle rounded-lg overflow-hidden">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Strategy Name &amp; Code</th>
                    <th>Structure &amp; Bias</th>
                    <th>Markets</th>
                    <th>Lifecycle</th>
                    <th>Health</th>
                    <th>Validation</th>
                    <th>Latest Performance</th>
                    <th className="text-center">Suggestable</th>
                    <th>Enabled</th>
                    <th className="text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {strategies.map((strat) => {
                    const hasReview = strat.reviewFlags && strat.reviewFlags.length > 0;
                    const snapshot = strat.latestPerformance && strat.latestPerformance[0];

                    return (
                      <tr key={strat.id} className="hover:bg-elevated/40 transition-colors">
                        <td>
                          <div className="flex items-center gap-2">
                            {hasReview && (
                              <AlertTriangle size={13} className="text-amber shrink-0" />
                            )}
                            <div>
                              <div
                                className="font-semibold text-primary hover:text-cyan cursor-pointer"
                                onClick={() => navigate({ to: `/strategies/${strat.id}` as any })}
                              >
                                {strat.name}
                              </div>
                              <div className="font-mono text-xs text-muted">{strat.code}</div>
                            </div>
                          </div>
                        </td>

                        <td>
                          <div className="text-xs">
                            <span className="badge-pill bg-elevated font-mono block mb-1">
                              {strat.structure || strat.category}
                            </span>
                            <span
                              className={`badge-pill text-[10px] ${
                                strat.bias === "BULLISH"
                                  ? "text-emerald"
                                  : strat.bias === "BEARISH"
                                  ? "text-rose"
                                  : "text-secondary"
                              }`}
                            >
                              {strat.bias || "DYNAMIC"}
                            </span>
                          </div>
                        </td>

                        <td>
                          <div className="flex flex-wrap gap-1 max-w-[130px]">
                            {strat.markets.map((m) => (
                              <span key={m} className="badge-pill bg-surface text-secondary text-[10px]">
                                {m}
                              </span>
                            ))}
                          </div>
                        </td>

                        <td>
                          <span
                            className={`badge-pill text-xs font-semibold ${
                              strat.lifecycleStatus === "ACTIVE"
                                ? "bg-emerald/20 text-emerald"
                                : strat.lifecycleStatus === "SUSPENDED"
                                ? "bg-rose/20 text-rose"
                                : "bg-surface text-muted"
                            }`}
                          >
                            {strat.lifecycleStatus}
                          </span>
                        </td>

                        <td>
                          <span
                            className={`badge-pill text-xs font-bold ${
                              strat.effectiveHealth === "HEALTHY"
                                ? "text-emerald"
                                : strat.effectiveHealth === "DEGRADED"
                                ? "text-amber"
                                : strat.effectiveHealth === "SUSPENDED"
                                ? "text-rose"
                                : "text-muted"
                            }`}
                          >
                            {strat.effectiveHealth || strat.health}
                          </span>
                        </td>

                        <td>
                          <span className="badge-pill text-[11px] bg-elevated text-secondary">
                            {strat.validationStatus}
                          </span>
                        </td>

                        <td>
                          {snapshot ? (
                            <div className="text-xs font-mono">
                              <div>
                                {snapshot.totalTrades}T |{" "}
                                <span className={snapshot.winRatePct >= 50 ? "text-emerald" : "text-rose"}>
                                  {Number(snapshot.winRatePct).toFixed(0)}%
                                </span>
                              </div>
                              <div
                                className={
                                  snapshot.netPnl > 0
                                    ? "text-emerald"
                                    : snapshot.netPnl < 0
                                    ? "text-rose"
                                    : "text-muted"
                                }
                              >
                                ₹{Number(snapshot.netPnl).toLocaleString()}
                              </div>
                            </div>
                          ) : (
                            <span className="text-xs text-muted">—</span>
                          )}
                        </td>

                        <td className="text-center">
                          {strat.suggestable ? (
                            <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-emerald/20 text-emerald">
                              <Check size={13} />
                            </span>
                          ) : (
                            <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-surface text-muted">
                              <X size={13} />
                            </span>
                          )}
                        </td>

                        <td>
                          <label className="toggle-switch">
                            <input
                              type="checkbox"
                              checked={strat.enabled}
                              onChange={(e) =>
                                toggleEnabledMutation.mutate({
                                  id: strat.id,
                                  enabled: e.target.checked,
                                })
                              }
                            />
                            <span className="slider round"></span>
                          </label>
                        </td>

                        <td className="text-right">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              type="button"
                              className="btn-icon"
                              title="View Strategy"
                              onClick={() => navigate({ to: `/strategies/${strat.id}` as any })}
                            >
                              <Eye size={15} />
                            </button>
                            <button
                              type="button"
                              className="btn-icon"
                              title="Clone Strategy"
                              onClick={() => handleClone(strat.id)}
                            >
                              <Copy size={15} />
                            </button>
                            <button
                              type="button"
                              className="btn-icon text-rose"
                              title="Delete Strategy"
                              onClick={() => handleDelete(strat.id, strat.name)}
                            >
                              <Trash2 size={15} />
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

          {/* Bottom Pagination Bar */}
          {totalPages > 1 && (
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "12px 18px",
                background: "#111",
                border: "1px solid #222",
                borderRadius: "8px",
                marginTop: "20px",
                fontSize: "12px",
                color: "#888",
                flexWrap: "wrap",
                gap: "10px",
              }}
            >
              <div>
                Showing <strong style={{ color: "#fff" }}>{startRecord}</strong>–
                <strong style={{ color: "#fff" }}>{endRecord}</strong> of{" "}
                <strong style={{ color: "#00e676" }}>{totalItems}</strong> strategies (Page{" "}
                {filter.page + 1} of {totalPages})
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <button
                  type="button"
                  disabled={filter.page === 0}
                  onClick={() => setFilter((prev) => ({ ...prev, page: 0 }))}
                  style={{
                    background: "#1a1a1a",
                    border: "1px solid #282828",
                    borderRadius: "4px",
                    color: filter.page === 0 ? "#444" : "#aaa",
                    padding: "4px 8px",
                    cursor: filter.page === 0 ? "not-allowed" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <ChevronsLeft size={13} /> First
                </button>
                <button
                  type="button"
                  disabled={filter.page === 0}
                  onClick={() => setFilter((prev) => ({ ...prev, page: prev.page - 1 }))}
                  style={{
                    background: "#1a1a1a",
                    border: "1px solid #282828",
                    borderRadius: "4px",
                    color: filter.page === 0 ? "#444" : "#aaa",
                    padding: "4px 8px",
                    cursor: filter.page === 0 ? "not-allowed" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <ChevronLeft size={13} /> Prev
                </button>
                <button
                  type="button"
                  disabled={filter.page + 1 >= totalPages}
                  onClick={() => setFilter((prev) => ({ ...prev, page: prev.page + 1 }))}
                  style={{
                    background: "#1a1a1a",
                    border: "1px solid #282828",
                    borderRadius: "4px",
                    color: filter.page + 1 >= totalPages ? "#444" : "#aaa",
                    padding: "4px 8px",
                    cursor: filter.page + 1 >= totalPages ? "not-allowed" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  Next <ChevronRight size={13} />
                </button>
                <button
                  type="button"
                  disabled={filter.page + 1 >= totalPages}
                  onClick={() => setFilter((prev) => ({ ...prev, page: totalPages - 1 }))}
                  style={{
                    background: "#1a1a1a",
                    border: "1px solid #282828",
                    borderRadius: "4px",
                    color: filter.page + 1 >= totalPages ? "#444" : "#aaa",
                    padding: "4px 8px",
                    cursor: filter.page + 1 >= totalPages ? "not-allowed" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  Last <ChevronsRight size={13} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Rules View */}
      {activeTab === "rules" && <RulesPage showHeader={false} />}

      {showDayShift && <DayShiftModal onClose={() => setShowDayShift(false)} />}
    </div>
  );
};
