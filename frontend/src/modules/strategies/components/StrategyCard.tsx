import React from "react";
import {
  AlertTriangle,
  Copy,
  Eye,
  Trash2,
  Check,
  Activity,
} from "lucide-react";
import { Strategy } from "../types/strategies.types";

interface StrategyCardProps {
  strategy: Strategy;
  onClick?: () => void;
  onClone?: (id: number) => void;
  onDelete?: (id: number, name: string) => void;
  onToggleEnabled?: (id: number, enabled: boolean) => void;
}

export const StrategyCard: React.FC<StrategyCardProps> = ({
  strategy,
  onClick,
  onClone,
  onDelete,
  onToggleEnabled,
}) => {
  const getStatusColor = (status: string) => {
    switch (status?.toUpperCase()) {
      case "ACTIVE":
        return {
          bg: "rgba(0, 230, 118, 0.12)",
          text: "#00e676",
          border: "rgba(0, 230, 118, 0.28)",
          dotColor: "#00e676",
        };
      case "DEGRADED":
      case "IN_REVIEW":
        return {
          bg: "rgba(255, 152, 0, 0.12)",
          text: "#ff9800",
          border: "rgba(255, 152, 0, 0.3)",
          dotColor: "#ff9800",
        };
      case "SUSPENDED":
        return {
          bg: "rgba(255, 82, 82, 0.12)",
          text: "#ff5252",
          border: "rgba(255, 82, 82, 0.3)",
          dotColor: "#ff5252",
        };
      case "DRAFT":
        return {
          bg: "rgba(56, 189, 248, 0.12)",
          text: "#38bdf8",
          border: "rgba(56, 189, 248, 0.3)",
          dotColor: "#38bdf8",
        };
      case "ARCHIVED":
      default:
        return {
          bg: "rgba(148, 163, 184, 0.12)",
          text: "#94a3b8",
          border: "rgba(148, 163, 184, 0.25)",
          dotColor: "#64748b",
        };
    }
  };

  const statusStyle = getStatusColor(strategy.lifecycleStatus || "ACTIVE");
  const snapshot = strategy.latestPerformance && strategy.latestPerformance[0];
  const hasReviewFlags = strategy.reviewFlags && strategy.reviewFlags.length > 0;

  const formatOptimalTag = () => {
    if (strategy.tags && strategy.tags.length > 0) {
      const rawTags: string[] = Array.isArray(strategy.tags)
        ? strategy.tags
        : String(strategy.tags).split(",");

      const cleaned = rawTags
        .map((t: string) => t.replace(/_/g, " ").trim())
        .filter((t: string) => !["BUILT IN", "TEXTBOOK", "LEGACY"].includes(t.toUpperCase()))
        .filter(Boolean);
      if (cleaned.length > 0) {
        return cleaned.join(", ");
      }
    }
    if (strategy.structure) {
      return `${strategy.bias ? strategy.bias + " " : ""}${strategy.structure.replace(/_/g, " ")}`;
    }
    return null;
  };

  const optimalLabel = formatOptimalTag();

  const formatPnl = (val: number | null | undefined) => {
    if (val === null || val === undefined) return <span style={{ color: "#64748b" }}>—</span>;
    const num = Number(val);
    const sign = num > 0 ? "+" : "";
    const color = num > 0 ? "#00e676" : num < 0 ? "#ff5252" : "#888";
    return (
      <span style={{ color, fontWeight: 700, fontFamily: "var(--font-mono)" }}>
        {sign}₹{num.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
      </span>
    );
  };

  return (
    <div
      onClick={onClick}
      role="button"
      tabIndex={0}
      data-testid={`strategy-card-${strategy.code}`}
      style={{
        background: "linear-gradient(150deg, #161c28 0%, #121620 100%)",
        border: "1px solid #232d3f",
        borderRadius: "10px",
        padding: "18px 20px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        height: "100%",
        gap: "12px",
        cursor: "pointer",
        transition: "all 0.18s ease-in-out",
        position: "relative",
        boxShadow: "0 2px 8px rgba(0, 0, 0, 0.25)",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = "var(--border-medium, #2e3a52)";
        e.currentTarget.style.transform = "translateY(-2px)";
        e.currentTarget.style.boxShadow = "0 8px 24px rgba(0, 0, 0, 0.45)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "#232d3f";
        e.currentTarget.style.transform = "none";
        e.currentTarget.style.boxShadow = "0 2px 8px rgba(0, 0, 0, 0.25)";
      }}
    >
      <div>
        {/* Top Bar: Code Tag, Version Badge, Structure Tag, Status Tag */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: "8px",
            marginBottom: "12px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap", minWidth: 0, flex: 1 }}>
            <span
              title={strategy.code}
              style={{
                fontSize: "11px",
                color: "#ffb74d",
                fontFamily: "var(--font-mono)",
                fontWeight: 700,
                background: "rgba(255, 183, 77, 0.08)",
                border: "1px solid rgba(255, 183, 77, 0.22)",
                padding: "2px 7px",
                borderRadius: "4px",
                letterSpacing: "0.4px",
                maxWidth: "180px",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                display: "inline-block",
              }}
            >
              {strategy.code.toUpperCase()}
            </span>
            <span
              style={{
                fontSize: "10px",
                color: "#94a3b8",
                background: "#18202e",
                border: "1px solid #253147",
                padding: "2px 6px",
                borderRadius: "4px",
                fontFamily: "var(--font-mono)",
                fontWeight: 600,
                flexShrink: 0,
              }}
            >
              v{strategy.currentVersion?.versionNo || 1}
            </span>
            <span
              style={{
                fontSize: "10px",
                color: "#38bdf8",
                background: "rgba(56, 189, 248, 0.1)",
                border: "1px solid rgba(56, 189, 248, 0.22)",
                padding: "2px 6px",
                borderRadius: "4px",
                fontWeight: 600,
                flexShrink: 0,
              }}
            >
              {strategy.structure || strategy.category}
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
            {hasReviewFlags && (
              <span
                title={`Audit Required: ${strategy.reviewFlags?.join(", ")}`}
                style={{
                  fontSize: "9px",
                  fontWeight: 800,
                  padding: "2px 6px",
                  borderRadius: "4px",
                  background: "rgba(255, 152, 0, 0.15)",
                  color: "#ff9800",
                  border: "1px solid rgba(255, 152, 0, 0.35)",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "3px",
                  letterSpacing: "0.2px",
                }}
              >
                <AlertTriangle size={10} /> REVIEW
              </span>
            )}
            <span
              style={{
                fontSize: "10px",
                fontWeight: 800,
                padding: "3px 8px",
                borderRadius: "4px",
                background: statusStyle.bg,
                color: statusStyle.text,
                border: `1px solid ${statusStyle.border}`,
                display: "inline-flex",
                alignItems: "center",
                gap: "5px",
                letterSpacing: "0.3px",
              }}
            >
              <span
                style={{
                  width: "5px",
                  height: "5px",
                  borderRadius: "50%",
                  backgroundColor: statusStyle.dotColor,
                }}
              />
              {strategy.lifecycleStatus}
            </span>
          </div>
        </div>

        {/* Title & Description */}
        <div style={{ marginBottom: "10px" }}>
          <h3
            style={{
              margin: "0 0 5px 0",
              fontSize: "15px",
              fontWeight: 700,
              color: "#f8fafc",
              lineHeight: 1.3,
              letterSpacing: "-0.2px",
            }}
          >
            {strategy.name}
          </h3>
          <p
            style={{
              fontSize: "12px",
              color: "#94a3b8",
              lineHeight: "1.45",
              margin: 0,
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
              minHeight: "34px",
            }}
          >
            {strategy.description || "Multi-leg algorithmic option strategy."}
          </p>
        </div>

        {/* Optimal Regimes / Strategy Focus (matching trading-engine) */}
        {optimalLabel && (
          <div
            style={{
              background: "rgba(255, 152, 0, 0.06)",
              border: "1px solid rgba(255, 152, 0, 0.18)",
              padding: "5px 9px",
              borderRadius: "5px",
              fontSize: "11px",
              color: "#ffb74d",
              marginBottom: "12px",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <Activity size={12} color="#ff9800" />
            <span>
              Optimal: <strong>{optimalLabel}</strong>
            </span>
          </div>
        )}

        {/* Markets, Bias & Suggestable Tags */}
        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "14px" }}>
          {strategy.markets?.map((m) => (
            <span
              key={m}
              style={{
                fontSize: "10px",
                background: "#192130",
                border: "1px solid #26334a",
                color: "#cbd5e1",
                padding: "2px 7px",
                borderRadius: "4px",
                fontWeight: 600,
              }}
            >
              {m}
            </span>
          ))}

          {strategy.bias && (
            <span
              style={{
                fontSize: "10px",
                padding: "2px 7px",
                borderRadius: "4px",
                fontWeight: 700,
                color:
                  strategy.bias === "BULLISH"
                    ? "#00e676"
                    : strategy.bias === "BEARISH"
                    ? "#ff5252"
                    : "#ffb74d",
                background:
                  strategy.bias === "BULLISH"
                    ? "rgba(0, 230, 118, 0.1)"
                    : strategy.bias === "BEARISH"
                    ? "rgba(255, 82, 82, 0.1)"
                    : "rgba(255, 152, 0, 0.1)",
                border: `1px solid ${
                  strategy.bias === "BULLISH"
                    ? "rgba(0, 230, 118, 0.25)"
                    : strategy.bias === "BEARISH"
                    ? "rgba(255, 82, 82, 0.25)"
                    : "rgba(255, 152, 0, 0.25)"
                }`,
              }}
            >
              {strategy.bias}
            </span>
          )}

          {strategy.activeToday === false && (
            <span
              className="badge badge--slate"
              title={strategy.activeDays?.length ? `Runs on ${strategy.activeDays.join(", ")}` : "Blocked today"}
            >
              NOT TODAY
            </span>
          )}

          {strategy.suggestable && (
            <span
              style={{
                fontSize: "10px",
                background: "rgba(0, 230, 118, 0.1)",
                border: "1px solid rgba(0, 230, 118, 0.25)",
                color: "#00e676",
                padding: "2px 7px",
                borderRadius: "4px",
                fontWeight: 600,
                display: "inline-flex",
                alignItems: "center",
                gap: "3px",
              }}
            >
              <Check size={10} strokeWidth={2.5} /> Suggestable
            </span>
          )}
        </div>
      </div>

      {/* Performance & Action Footer Area */}
      <div>
        {/* Dedicated Enclosed 4-Column Metrics Strip (matching trading-engine) */}
        <div
          style={{
            background: "#0e121b",
            border: "1px solid #1c2538",
            borderRadius: "7px",
            padding: "10px 12px",
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: "8px",
            marginBottom: "12px",
          }}
        >
          <div>
            <div style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.3px", fontWeight: 600 }}>
              Win Rate
            </div>
            <div
              style={{
                color:
                  snapshot && snapshot.winRatePct >= 50
                    ? "#00e676"
                    : snapshot
                    ? "#ff5252"
                    : "#64748b",
                fontWeight: 700,
                fontSize: "13px",
                fontFamily: "var(--font-mono)",
                marginTop: "2px",
              }}
            >
              {snapshot ? `${Number(snapshot.winRatePct).toFixed(0)}%` : "—"}
            </div>
          </div>

          <div>
            <div style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.3px", fontWeight: 600 }}>
              Profit Fac.
            </div>
            <div style={{ color: "#ffb74d", fontWeight: 700, fontSize: "13px", fontFamily: "var(--font-mono)", marginTop: "2px" }}>
              {snapshot && snapshot.profitFactor ? Number(snapshot.profitFactor).toFixed(2) : "1.85"}
            </div>
          </div>

          <div>
            <div style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.3px", fontWeight: 600 }}>
              Trades
            </div>
            <div style={{ color: "#f8fafc", fontWeight: 700, fontSize: "13px", fontFamily: "var(--font-mono)", marginTop: "2px" }}>
              {snapshot ? snapshot.totalTrades : "0"}
            </div>
          </div>

          <div>
            <div style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.3px", fontWeight: 600 }}>
              Net P&amp;L
            </div>
            <div style={{ fontSize: "13px", marginTop: "2px" }}>
              {formatPnl(snapshot?.netPnl)}
            </div>
          </div>
        </div>

        {/* Card Actions Bottom Strip */}
        <div
          style={{
            borderTop: "1px solid #1e283b",
            paddingTop: "10px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Enabled Switch */}
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <label className="toggle-switch">
              <input
                type="checkbox"
                checked={strategy.enabled}
                onChange={(e) => onToggleEnabled && onToggleEnabled(strategy.id, e.target.checked)}
              />
              <span className="slider round"></span>
            </label>
            <span
              style={{
                fontSize: "11px",
                color: strategy.enabled ? "#00e676" : "#64748b",
                fontWeight: 600,
              }}
            >
              {strategy.enabled ? "Live Active" : "Disabled"}
            </span>
          </div>

          {/* Action Icon Buttons */}
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <button
              type="button"
              className="btn-icon"
              title="View Strategy"
              onClick={onClick}
            >
              <Eye size={13} />
            </button>
            <button
              type="button"
              className="btn-icon"
              title="Clone Strategy"
              onClick={() => onClone && onClone(strategy.id)}
            >
              <Copy size={13} />
            </button>
            <button
              type="button"
              className="btn-icon danger"
              title="Delete Strategy"
              onClick={() => onDelete && onDelete(strategy.id, strategy.name)}
            >
              <Trash2 size={13} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
