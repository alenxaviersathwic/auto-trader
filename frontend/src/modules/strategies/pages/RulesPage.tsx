import React, { useState } from "react";
import {
  ShieldCheck,
  Play,
  Terminal,
  AlertTriangle,
  Clock,
  Trash2,
  HelpCircle,
  Eye,
  Check,
  Search,
  X,
} from "lucide-react";
import {
  useCheckGuardrails,
  useDeleteRule,
  useRuleDetail,
  useRulesSearch,
} from "../hooks/useStrategies";
import { GuardrailCheckResponse, Rule, RuleFilter } from "../types/strategies.types";

interface RulesPageProps {
  showHeader?: boolean;
}

export const RulesPage: React.FC<RulesPageProps> = ({ showHeader = false }) => {
  const [filter, setFilter] = useState<RuleFilter>({
    page: 0,
    limit: 25,
    sortBy: "createdAt",
    sortDir: "desc",
    status: "ACTIVE",
    query: "",
  });

  const [searchInput, setSearchInput] = useState<string>("");

  const { data, isLoading } = useRulesSearch(filter);
  const deleteRuleMutation = useDeleteRule();
  const checkGuardrailsMutation = useCheckGuardrails();

  const [selectedRuleId, setSelectedRuleId] = useState<number | null>(null);
  const { data: selectedRule } = useRuleDetail(selectedRuleId || 0);

  // Simulation Context Presets
  const PRESET_RANGING_CALL = {
    market: "NIFTY",
    optionSide: "CALL",
    executionDomain: "LIVE",
    indicators: {
      MARKET_REGIME: "RANGING",
      ADX: 18,
    },
    PRICE: {
      close: 24600,
    },
  };

  const PRESET_VOLATILITY_BLOCK = {
    market: "SENSEX",
    optionSide: "PUT",
    executionDomain: "LIVE",
    indicators: {
      MARKET_REGIME: "HIGH_VOLATILITY",
      GROSS_PREMIUM: 12.5,
    },
    PRICE: {
      close: 81200,
    },
  };

  const PRESET_TREND_PASS = {
    market: "NIFTY",
    optionSide: "CALL",
    executionDomain: "LIVE",
    indicators: {
      MARKET_REGIME: "BULLISH_TREND",
      ADX: 32,
    },
    PRICE: {
      close: 24850,
    },
  };

  const [testContextJson, setTestContextJson] = useState<string>(
    JSON.stringify(PRESET_RANGING_CALL, null, 2)
  );
  const [guardrailResults, setGuardrailResults] = useState<GuardrailCheckResponse | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  const rules: Rule[] = data?.list || [];
  const totalItems = data?.totalItems || 0;

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFilter((prev) => ({ ...prev, query: searchInput.trim(), page: 0 }));
  };

  const handleClearSearch = () => {
    setSearchInput("");
    setFilter((prev) => ({ ...prev, query: "", page: 0 }));
  };

  const handleRunCheck = () => {
    try {
      const parsed = JSON.parse(testContextJson);
      setTestError(null);
      checkGuardrailsMutation.mutate(
        { context: parsed, includeStale: true },
        {
          onSuccess: (res) => setGuardrailResults(res),
          onError: (err: any) => setTestError(err.message || "Guardrail check failed"),
        }
      );
    } catch (err: any) {
      setTestError("Invalid JSON syntax: " + err.message);
    }
  };

  const handleDelete = (id: number, name: string) => {
    if (window.confirm(`Delete rule "${name}"?`)) {
      deleteRuleMutation.mutate(id);
    }
  };

  const getActionBadgeStyle = (action?: string | null) => {
    switch (action?.toUpperCase()) {
      case "BLOCK":
        return {
          bg: "rgba(255, 82, 82, 0.15)",
          text: "#ff5252",
          border: "rgba(255, 82, 82, 0.35)",
        };
      case "AVOID":
        return {
          bg: "rgba(255, 152, 0, 0.15)",
          text: "#ff9800",
          border: "rgba(255, 152, 0, 0.35)",
        };
      case "PREFER":
        return {
          bg: "rgba(0, 230, 118, 0.15)",
          text: "#00e676",
          border: "rgba(0, 230, 118, 0.35)",
        };
      case "WATCH":
      default:
        return {
          bg: "rgba(56, 189, 248, 0.15)",
          text: "#38bdf8",
          border: "rgba(56, 189, 248, 0.35)",
        };
    }
  };

  const getPriorityBadgeStyle = (priority?: string | null) => {
    switch (priority?.toUpperCase()) {
      case "CRITICAL":
        return { color: "#ff5252", bg: "rgba(255, 82, 82, 0.12)", border: "rgba(255, 82, 82, 0.3)" };
      case "HIGH":
        return { color: "#ff9800", bg: "rgba(255, 152, 0, 0.12)", border: "rgba(255, 152, 0, 0.3)" };
      case "MEDIUM":
        return { color: "#38bdf8", bg: "rgba(56, 189, 248, 0.12)", border: "rgba(56, 189, 248, 0.3)" };
      default:
        return { color: "#94a3b8", bg: "#19202e", border: "#283449" };
    }
  };

  return (
    <div className="rules-page module-page">
      {showHeader && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "18px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#ffffff", margin: 0 }}>
                Trading Rules &amp; Guardrails
              </h1>
              {totalItems > 0 && (
                <span
                  style={{
                    background: "rgba(0, 230, 118, 0.12)",
                    border: "1px solid rgba(0, 230, 118, 0.3)",
                    color: "#00e676",
                    fontSize: "12px",
                    fontWeight: 700,
                    padding: "2px 8px",
                    borderRadius: "12px",
                  }}
                >
                  {totalItems} Guardrails
                </span>
              )}
            </div>
            <p style={{ fontSize: "13px", color: "#888", marginTop: "6px", marginBottom: 0 }}>
              Global risk guardrails, empirical regime filters, and reusable condition blocks.
            </p>
          </div>
        </div>
      )}

      {/* Filter and Search Bar matching Strategies Page */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "14px",
          marginBottom: "18px",
          flexWrap: "wrap",
          background: "linear-gradient(180deg, #161c28 0%, #121620 100%)",
          padding: "12px 18px",
          borderRadius: "10px",
          border: "1px solid #232d3f",
          boxShadow: "0 2px 8px rgba(0, 0, 0, 0.2)",
        }}
      >
        {/* Search Form */}
        <form
          onSubmit={handleSearchSubmit}
          style={{ position: "relative", flex: "1", minWidth: "220px", maxWidth: "320px" }}
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
            placeholder="Search rule code, name, scope..."
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

        {/* Kind Filter Chips */}
        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>
            Kind:
          </span>
          {["ALL", "GUARDRAIL", "CONDITION_BLOCK"].map((k) => {
            const isActive = (filter.ruleKind || "ALL") === k || (k === "ALL" && !filter.ruleKind);
            return (
              <button
                key={k}
                type="button"
                onClick={() => setFilter((prev) => ({ ...prev, ruleKind: k === "ALL" ? undefined : k, page: 0 }))}
                style={{
                  background: isActive ? "#1c2638" : "#10141d",
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
                {k === "ALL" ? "All Kinds" : k}
              </button>
            );
          })}
        </div>

        {/* Action Filter Chips */}
        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>
            Action:
          </span>
          {["ALL", "AVOID", "BLOCK", "PREFER"].map((act) => {
            const isActive = (filter.action || "ALL") === act || (act === "ALL" && !filter.action);
            const activeColor = act === "BLOCK" ? "#ff5252" : act === "AVOID" ? "#ff9800" : act === "PREFER" ? "#00e676" : "#38bdf8";
            return (
              <button
                key={act}
                type="button"
                onClick={() => setFilter((prev) => ({ ...prev, action: act === "ALL" ? undefined : act, page: 0 }))}
                style={{
                  background: isActive ? "#1c2638" : "#10141d",
                  border: `1px solid ${isActive ? activeColor : "#232b3b"}`,
                  borderRadius: "5px",
                  color: isActive ? activeColor : "#94a3b8",
                  padding: "4px 9px",
                  fontSize: "11px",
                  fontWeight: isActive ? 700 : 500,
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                {act}
              </button>
            );
          })}
        </div>

        {/* Priority Filter Chips */}
        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>
            Priority:
          </span>
          {["ALL", "CRITICAL", "HIGH", "MEDIUM"].map((p) => {
            const isActive = (filter.priority || "ALL") === p || (p === "ALL" && !filter.priority);
            return (
              <button
                key={p}
                type="button"
                onClick={() => setFilter((prev) => ({ ...prev, priority: p === "ALL" ? undefined : p, page: 0 }))}
                style={{
                  background: isActive ? "#1c2638" : "#10141d",
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
                {p}
              </button>
            );
          })}
        </div>
      </div>

      {/* Rules Table in Standard Card Container */}
      {isLoading ? (
        <div
          style={{
            background: "#161c28",
            border: "1px solid #232d3f",
            borderRadius: "10px",
            padding: "40px",
            textAlign: "center",
            color: "#94a3b8",
          }}
        >
          Loading trading rules...
        </div>
      ) : rules.length === 0 ? (
        <div
          style={{
            background: "#161c28",
            border: "1px solid #232d3f",
            borderRadius: "10px",
            padding: "50px 20px",
            textAlign: "center",
            marginBottom: "20px",
          }}
        >
          <ShieldCheck size={36} color="#38bdf8" style={{ margin: "0 auto 12px", opacity: 0.7 }} />
          <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", marginBottom: "6px" }}>
            No Trading Rules Found
          </h3>
          <p style={{ fontSize: "12px", color: "#888", marginBottom: "14px" }}>
            No active guardrails match the current search filters.
          </p>
          <button
            type="button"
            onClick={() => setFilter({ page: 0, limit: 25, sortBy: "createdAt", sortDir: "desc", status: "ACTIVE" })}
            style={{
              background: "#19202e",
              border: "1px solid #283449",
              color: "#38bdf8",
              fontSize: "12px",
              padding: "6px 14px",
              borderRadius: "6px",
              cursor: "pointer",
            }}
          >
            Clear Filters
          </button>
        </div>
      ) : (
        <div
          style={{
            background: "linear-gradient(150deg, #161c28 0%, #121620 100%)",
            border: "1px solid #232d3f",
            borderRadius: "10px",
            boxShadow: "0 4px 16px rgba(0, 0, 0, 0.3)",
            overflow: "hidden",
            marginBottom: "24px",
          }}
        >
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "12px" }}>
              <thead>
                <tr style={{ background: "#0e121a", borderBottom: "1px solid #1f283a" }}>
                  <th style={{ padding: "12px 16px", color: "#64748b", fontWeight: 700, fontSize: "11px", letterSpacing: "0.05em", textTransform: "uppercase" }}>
                    Rule Code &amp; Name
                  </th>
                  <th style={{ padding: "12px 14px", color: "#64748b", fontWeight: 700, fontSize: "11px", letterSpacing: "0.05em", textTransform: "uppercase" }}>
                    Kind &amp; Type
                  </th>
                  <th style={{ padding: "12px 14px", color: "#64748b", fontWeight: 700, fontSize: "11px", letterSpacing: "0.05em", textTransform: "uppercase" }}>
                    Intervention
                  </th>
                  <th style={{ padding: "12px 14px", color: "#64748b", fontWeight: 700, fontSize: "11px", letterSpacing: "0.05em", textTransform: "uppercase" }}>
                    Priority
                  </th>
                  <th style={{ padding: "12px 14px", color: "#64748b", fontWeight: 700, fontSize: "11px", letterSpacing: "0.05em", textTransform: "uppercase" }}>
                    Scope
                  </th>
                  <th style={{ padding: "12px 14px", color: "#64748b", fontWeight: 700, fontSize: "11px", letterSpacing: "0.05em", textTransform: "uppercase" }}>
                    Empirical Evidence
                  </th>
                  <th style={{ padding: "12px 14px", color: "#64748b", fontWeight: 700, fontSize: "11px", letterSpacing: "0.05em", textTransform: "uppercase" }}>
                    Review Due
                  </th>
                  <th style={{ padding: "12px 14px", color: "#64748b", fontWeight: 700, fontSize: "11px", letterSpacing: "0.05em", textTransform: "uppercase" }}>
                    Executable
                  </th>
                  <th style={{ padding: "12px 16px", color: "#64748b", fontWeight: 700, fontSize: "11px", letterSpacing: "0.05em", textTransform: "uppercase", textAlign: "right" }}>
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {rules.map((rule) => {
                  const isStale = rule.reviewBy && new Date(rule.reviewBy).getTime() < Date.now();
                  const actStyle = getActionBadgeStyle(rule.action);
                  const priStyle = getPriorityBadgeStyle(rule.priority);

                  return (
                    <tr
                      key={rule.id}
                      style={{ borderBottom: "1px solid #1c2436", transition: "background 0.15s ease" }}
                      onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.02)")}
                      onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
                    >
                      {/* Name & Code */}
                      <td style={{ padding: "14px 16px" }}>
                        <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
                          <span
                            onClick={() => setSelectedRuleId(rule.id)}
                            style={{
                              fontWeight: 700,
                              color: "#f8fafc",
                              cursor: "pointer",
                              fontSize: "13px",
                            }}
                            onMouseEnter={(e) => (e.currentTarget.style.color = "#38bdf8")}
                            onMouseLeave={(e) => (e.currentTarget.style.color = "#f8fafc")}
                          >
                            {rule.name}
                          </span>
                          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                            <span
                              style={{
                                fontFamily: "var(--font-mono)",
                                fontSize: "10px",
                                fontWeight: 700,
                                color: "#ffb74d",
                                background: "rgba(255, 183, 77, 0.08)",
                                border: "1px solid rgba(255, 183, 77, 0.25)",
                                padding: "1px 6px",
                                borderRadius: "3px",
                              }}
                            >
                              {rule.code}
                            </span>
                            {rule.conditionText && (
                              <span style={{ fontSize: "11px", color: "#64748b", maxWidth: "260px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                {rule.conditionText}
                              </span>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Kind & Type */}
                      <td style={{ padding: "14px 14px" }}>
                        <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                          <span
                            style={{
                              fontSize: "10px",
                              fontWeight: 700,
                              color: "#cbd5e1",
                              background: "#19202e",
                              border: "1px solid #283449",
                              padding: "2px 6px",
                              borderRadius: "4px",
                              display: "inline-block",
                              width: "fit-content",
                            }}
                          >
                            {rule.ruleKind}
                          </span>
                          <span style={{ fontSize: "11px", color: "#38bdf8", fontWeight: 600 }}>
                            {rule.ruleType}
                          </span>
                        </div>
                      </td>

                      {/* Intervention Action */}
                      <td style={{ padding: "14px 14px" }}>
                        <span
                          style={{
                            fontSize: "11px",
                            fontWeight: 800,
                            padding: "3px 8px",
                            borderRadius: "4px",
                            background: actStyle.bg,
                            color: actStyle.text,
                            border: `1px solid ${actStyle.border}`,
                            letterSpacing: "0.3px",
                          }}
                        >
                          {rule.action || "—"}
                        </span>
                      </td>

                      {/* Priority */}
                      <td style={{ padding: "14px 14px" }}>
                        <span
                          style={{
                            fontSize: "10px",
                            fontWeight: 700,
                            padding: "2px 6px",
                            borderRadius: "3px",
                            color: priStyle.color,
                            background: priStyle.bg,
                            border: `1px solid ${priStyle.border}`,
                          }}
                        >
                          {rule.priority}
                        </span>
                      </td>

                      {/* Scope & Markets */}
                      <td style={{ padding: "14px 14px" }}>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", maxWidth: "160px" }}>
                          {rule.appliesTo?.markets?.map((m) => (
                            <span
                              key={m}
                              style={{
                                fontSize: "10px",
                                background: "#19202e",
                                border: "1px solid #283449",
                                color: "#cbd5e1",
                                padding: "1px 5px",
                                borderRadius: "3px",
                              }}
                            >
                              {m}
                            </span>
                          ))}
                          {rule.appliesTo?.optionSides?.map((s) => (
                            <span
                              key={s}
                              style={{
                                fontSize: "10px",
                                background: s === "CALL" ? "rgba(0, 230, 118, 0.1)" : "rgba(255, 82, 82, 0.1)",
                                border: `1px solid ${s === "CALL" ? "rgba(0, 230, 118, 0.25)" : "rgba(255, 82, 82, 0.25)"}`,
                                color: s === "CALL" ? "#00e676" : "#ff5252",
                                padding: "1px 5px",
                                borderRadius: "3px",
                                fontWeight: 700,
                              }}
                            >
                              {s}
                            </span>
                          ))}
                        </div>
                      </td>

                      {/* Empirical Evidence */}
                      <td style={{ padding: "14px 14px" }}>
                        {rule.evidence ? (
                          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontFamily: "var(--font-mono)" }}>
                            <span style={{ color: "#f8fafc", fontWeight: 600 }}>
                              {rule.evidence.count} trd
                            </span>
                            {rule.evidence.successRatePct !== undefined && (
                              <span style={{ color: "#00e676", fontWeight: 700 }}>
                                ({rule.evidence.successRatePct}%)
                              </span>
                            )}
                            {Number(rule.evidence.count || 0) < 30 && (
                              <span
                                style={{
                                  fontSize: "9px",
                                  color: "#ff9800",
                                  background: "rgba(255, 152, 0, 0.12)",
                                  padding: "1px 4px",
                                  borderRadius: "2px",
                                  border: "1px solid rgba(255, 152, 0, 0.3)",
                                }}
                              >
                                Small
                              </span>
                            )}
                          </div>
                        ) : (
                          <span style={{ color: "#64748b" }}>—</span>
                        )}
                      </td>

                      {/* Review Due */}
                      <td style={{ padding: "14px 14px" }}>
                        <span
                          style={{
                            fontSize: "11px",
                            color: isStale ? "#ff5252" : "#94a3b8",
                            fontWeight: isStale ? 700 : 500,
                            display: "flex",
                            alignItems: "center",
                            gap: "4px",
                          }}
                        >
                          {isStale && <Clock size={12} />}
                          {rule.reviewBy || "Indefinite"}
                        </span>
                      </td>

                      {/* Executable */}
                      <td style={{ padding: "14px 14px" }}>
                        {rule.executable ? (
                          <span
                            style={{
                              fontSize: "10px",
                              fontWeight: 700,
                              color: "#00e676",
                              background: "rgba(0, 230, 118, 0.1)",
                              border: "1px solid rgba(0, 230, 118, 0.25)",
                              padding: "2px 6px",
                              borderRadius: "4px",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "3px",
                            }}
                          >
                            <Check size={11} strokeWidth={2.5} /> Active
                          </span>
                        ) : (
                          <span
                            style={{
                              fontSize: "10px",
                              fontWeight: 700,
                              color: "#ff9800",
                              background: "rgba(255, 152, 0, 0.1)",
                              border: "1px solid rgba(255, 152, 0, 0.25)",
                              padding: "2px 6px",
                              borderRadius: "4px",
                            }}
                            title="Missing code handler"
                          >
                            Review
                          </span>
                        )}
                      </td>

                      {/* Action buttons */}
                      <td style={{ padding: "14px 16px", textAlign: "right" }}>
                        <div style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                          <button
                            type="button"
                            className="btn-icon"
                            title="View Rule Details"
                            onClick={() => setSelectedRuleId(rule.id)}
                          >
                            <Eye size={13} />
                          </button>
                          <button
                            type="button"
                            className="btn-icon danger"
                            title="Delete Rule"
                            onClick={() => handleDelete(rule.id, rule.name)}
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div
            style={{
              padding: "10px 16px",
              background: "#0e121a",
              borderTop: "1px solid #1f283a",
              fontSize: "11px",
              color: "#64748b",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span>
              Showing <strong style={{ color: "#f8fafc" }}>{rules.length}</strong> of{" "}
              <strong style={{ color: "#00e676" }}>{totalItems}</strong> active rules
            </span>
            <span style={{ fontFamily: "var(--font-mono)" }}>APScheduler Active · Engine Sync</span>
          </div>
        </div>
      )}

      {/* Live Guardrail Evaluator Panel (Terminal Style) */}
      <div
        style={{
          background: "linear-gradient(150deg, #161c28 0%, #121620 100%)",
          border: "1px solid #232d3f",
          borderRadius: "10px",
          padding: "20px 22px",
          boxShadow: "0 4px 16px rgba(0, 0, 0, 0.25)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px", flexWrap: "wrap", gap: "10px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "6px",
                background: "rgba(56, 189, 248, 0.12)",
                border: "1px solid rgba(56, 189, 248, 0.25)",
                display: "grid",
                placeItems: "center",
                color: "#38bdf8",
              }}
            >
              <Terminal size={17} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700, color: "#f8fafc" }}>
                Live Guardrail Simulation Engine (/rules/check)
              </h3>
              <p style={{ margin: 0, fontSize: "12px", color: "#94a3b8" }}>
                Test order contexts against active guardrails to detect AVOID or BLOCK interventions before execution.
              </p>
            </div>
          </div>

          {/* Quick Presets */}
          <div style={{ display: "flex", gap: "6px", alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ fontSize: "11px", color: "#64748b", fontWeight: 600 }}>Presets:</span>
            <button
              type="button"
              onClick={() => setTestContextJson(JSON.stringify(PRESET_RANGING_CALL, null, 2))}
              style={{
                background: "#19202e",
                border: "1px solid #283449",
                borderRadius: "4px",
                color: "#ff9800",
                fontSize: "11px",
                padding: "3px 8px",
                cursor: "pointer",
              }}
            >
              Ranging Nifty Call
            </button>
            <button
              type="button"
              onClick={() => setTestContextJson(JSON.stringify(PRESET_VOLATILITY_BLOCK, null, 2))}
              style={{
                background: "#19202e",
                border: "1px solid #283449",
                borderRadius: "4px",
                color: "#ff5252",
                fontSize: "11px",
                padding: "3px 8px",
                cursor: "pointer",
              }}
            >
              Sensex Vol Spike
            </button>
            <button
              type="button"
              onClick={() => setTestContextJson(JSON.stringify(PRESET_TREND_PASS, null, 2))}
              style={{
                background: "#19202e",
                border: "1px solid #283449",
                borderRadius: "4px",
                color: "#00e676",
                fontSize: "11px",
                padding: "3px 8px",
                cursor: "pointer",
              }}
            >
              Clean Bull Trend
            </button>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "18px", marginTop: "16px" }}>
          {/* Left: JSON Input */}
          <div>
            <label style={{ fontSize: "12px", color: "#94a3b8", fontWeight: 700, display: "block", marginBottom: "6px" }}>
              Simulation Context (JSON Payload):
            </label>
            <textarea
              style={{
                width: "100%",
                background: "#0a0d14",
                border: "1px solid #232d3f",
                borderRadius: "8px",
                padding: "12px 14px",
                fontFamily: "var(--font-mono)",
                fontSize: "12px",
                color: "#e2e8f0",
                outline: "none",
                minHeight: "180px",
                lineHeight: "1.5",
                boxSizing: "border-box",
                resize: "vertical",
              }}
              value={testContextJson}
              onChange={(e) => setTestContextJson(e.target.value)}
              spellCheck={false}
            />
            {testError && (
              <div style={{ color: "#ff5252", fontSize: "12px", marginTop: "6px", display: "flex", alignItems: "center", gap: "6px" }}>
                <AlertTriangle size={13} />
                <span>{testError}</span>
              </div>
            )}
            <div style={{ marginTop: "10px" }}>
              <button
                type="button"
                onClick={handleRunCheck}
                disabled={checkGuardrailsMutation.isPending}
                style={{
                  background: "#00e676",
                  color: "#000",
                  fontWeight: 800,
                  fontSize: "12px",
                  padding: "8px 18px",
                  borderRadius: "6px",
                  border: "none",
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  boxShadow: "0 2px 10px rgba(0, 230, 118, 0.25)",
                }}
              >
                <Play size={13} fill="currentColor" />
                <span>{checkGuardrailsMutation.isPending ? "Evaluating Guardrails..." : "Evaluate Active Guardrails"}</span>
              </button>
            </div>
          </div>

          {/* Right: Results Display */}
          <div>
            <label style={{ fontSize: "12px", color: "#94a3b8", fontWeight: 700, display: "block", marginBottom: "6px" }}>
              Evaluation Verdict:
            </label>
            {!guardrailResults ? (
              <div
                style={{
                  height: "180px",
                  border: "1px dashed #232d3f",
                  borderRadius: "8px",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#64748b",
                  fontSize: "12px",
                  background: "#0d1017",
                  padding: "20px",
                  textAlign: "center",
                }}
              >
                <HelpCircle size={28} style={{ marginBottom: "8px", opacity: 0.5 }} />
                <span>Run guardrail evaluation to test real-time risk interventions.</span>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "250px", overflowY: "auto" }}>
                {/* Overall Verdict Banner */}
                <div
                  style={{
                    padding: "10px 14px",
                    borderRadius: "6px",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    fontWeight: 700,
                    fontSize: "13px",
                    background: guardrailResults.hasBlock
                      ? "rgba(255, 82, 82, 0.15)"
                      : guardrailResults.hasAvoid
                      ? "rgba(255, 152, 0, 0.15)"
                      : "rgba(0, 230, 118, 0.15)",
                    border: `1px solid ${
                      guardrailResults.hasBlock
                        ? "rgba(255, 82, 82, 0.4)"
                        : guardrailResults.hasAvoid
                        ? "rgba(255, 152, 0, 0.4)"
                        : "rgba(0, 230, 118, 0.4)"
                    }`,
                    color: guardrailResults.hasBlock
                      ? "#ff5252"
                      : guardrailResults.hasAvoid
                      ? "#ff9800"
                      : "#00e676",
                  }}
                >
                  {guardrailResults.hasBlock ? (
                    <>
                      <AlertTriangle size={16} />
                      <span>ORDER BLOCKED — Critical risk guardrail intervened</span>
                    </>
                  ) : guardrailResults.hasAvoid ? (
                    <>
                      <AlertTriangle size={16} />
                      <span>ORDER AVOIDED — Non-optimal regime filter active</span>
                    </>
                  ) : (
                    <>
                      <Check size={16} strokeWidth={2.5} />
                      <span>ALL GUARDRAILS PASSED — Order execution permitted</span>
                    </>
                  )}
                </div>

                {/* Individual Triggered Guardrails */}
                {guardrailResults.results.map((res, i) => {
                  const act = getActionBadgeStyle(res.action);
                  return (
                    <div
                      key={i}
                      style={{
                        padding: "10px 14px",
                        borderRadius: "6px",
                        background: "#0e121a",
                        border: `1px solid ${act.border}`,
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                        <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: "#f8fafc", fontSize: "12px" }}>
                          {res.ruleCode}
                        </span>
                        <span
                          style={{
                            fontSize: "10px",
                            fontWeight: 800,
                            padding: "2px 6px",
                            borderRadius: "3px",
                            background: act.bg,
                            color: act.text,
                            border: `1px solid ${act.border}`,
                          }}
                        >
                          {res.action}
                        </span>
                      </div>
                      <p style={{ margin: 0, fontSize: "12px", color: "#94a3b8", lineHeight: "1.4" }}>
                        {res.message}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Rule Detail Modal */}
      {selectedRule && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0, 0, 0, 0.75)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "20px",
          }}
          onClick={() => setSelectedRuleId(null)}
        >
          <div
            style={{
              background: "#161c28",
              border: "1px solid #2e3a52",
              borderRadius: "10px",
              maxWidth: "600px",
              width: "100%",
              boxShadow: "0 20px 40px rgba(0, 0, 0, 0.6)",
              overflow: "hidden",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                padding: "16px 20px",
                borderBottom: "1px solid #232d3f",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700, color: "#fff" }}>
                  {selectedRule.name}
                </h3>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "10px",
                    color: "#ffb74d",
                    background: "rgba(255, 183, 77, 0.1)",
                    padding: "1px 6px",
                    borderRadius: "3px",
                  }}
                >
                  {selectedRule.code}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedRuleId(null)}
                style={{
                  background: "#1e2638",
                  border: "none",
                  borderRadius: "4px",
                  color: "#94a3b8",
                  cursor: "pointer",
                  padding: "4px 8px",
                  fontSize: "12px",
                }}
              >
                ✕
              </button>
            </div>

            <div style={{ padding: "20px", fontSize: "12px", display: "flex", flexDirection: "column", gap: "14px" }}>
              <div>
                <span style={{ color: "#64748b", display: "block", marginBottom: "4px", fontWeight: 600 }}>
                  Condition Expression:
                </span>
                <p
                  style={{
                    margin: 0,
                    padding: "10px 12px",
                    background: "#0e121a",
                    border: "1px solid #232d3f",
                    borderRadius: "6px",
                    color: "#f8fafc",
                    lineHeight: "1.5",
                  }}
                >
                  {selectedRule.conditionText}
                </p>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                <div>
                  <span style={{ color: "#64748b", display: "block", fontSize: "11px" }}>Kind &amp; Type:</span>
                  <span style={{ color: "#38bdf8", fontWeight: 600 }}>
                    {selectedRule.ruleKind} / {selectedRule.ruleType}
                  </span>
                </div>
                <div>
                  <span style={{ color: "#64748b", display: "block", fontSize: "11px" }}>Action:</span>
                  <span
                    style={{
                      fontWeight: 800,
                      color:
                        selectedRule.action === "BLOCK"
                          ? "#ff5252"
                          : selectedRule.action === "AVOID"
                          ? "#ff9800"
                          : "#00e676",
                    }}
                  >
                    {selectedRule.action}
                  </span>
                </div>
                <div>
                  <span style={{ color: "#64748b", display: "block", fontSize: "11px" }}>Empirical Evidence:</span>
                  <span style={{ color: "#cbd5e1" }}>
                    {selectedRule.evidence
                      ? `${selectedRule.evidence.count} trades, ${selectedRule.evidence.successRatePct}% win rate`
                      : "None"}
                  </span>
                </div>
                <div>
                  <span style={{ color: "#64748b", display: "block", fontSize: "11px" }}>Review Due:</span>
                  <span style={{ color: "#cbd5e1" }}>{selectedRule.reviewBy || "Indefinite"}</span>
                </div>
              </div>

              {selectedRule.currentVersion?.content && (
                <div>
                  <span style={{ color: "#64748b", display: "block", marginBottom: "4px", fontWeight: 600 }}>
                    Condition Definition Tree:
                  </span>
                  <pre
                    style={{
                      margin: 0,
                      padding: "10px 12px",
                      background: "#090d14",
                      border: "1px solid #232d3f",
                      borderRadius: "6px",
                      color: "#38bdf8",
                      fontFamily: "var(--font-mono)",
                      fontSize: "11px",
                      maxHeight: "150px",
                      overflowY: "auto",
                    }}
                  >
                    {JSON.stringify(selectedRule.currentVersion.content, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
