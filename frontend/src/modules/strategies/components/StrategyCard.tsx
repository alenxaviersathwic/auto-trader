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
          bg: "rgba(76, 175, 80, 0.12)",
          text: "var(--bullish-green)",
          border: "rgba(76, 175, 80, 0.28)",
          dotColor: "var(--bullish-green)",
        };
      case "DEGRADED":
      case "IN_REVIEW":
        return {
          bg: "rgba(255, 152, 0, 0.12)",
          text: "var(--warning-amber)",
          border: "rgba(255, 152, 0, 0.3)",
          dotColor: "var(--warning-amber)",
        };
      case "SUSPENDED":
        return {
          bg: "rgba(239, 83, 80, 0.12)",
          text: "var(--bearish-red)",
          border: "rgba(239, 83, 80, 0.3)",
          dotColor: "var(--bearish-red)",
        };
      case "DRAFT":
        return {
          bg: "rgba(56, 189, 248, 0.12)",
          text: "var(--cyan)",
          border: "rgba(56, 189, 248, 0.3)",
          dotColor: "var(--cyan)",
        };
      case "ARCHIVED":
      default:
        return {
          bg: "rgba(154, 154, 154, 0.12)",
          text: "var(--text-secondary)",
          border: "rgba(154, 154, 154, 0.25)",
          dotColor: "var(--text-muted)",
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
    if (val === null || val === undefined) return <span style={{ color: "var(--text-muted)" }}>—</span>;
    const num = Number(val);
    const sign = num > 0 ? "+" : "";
    const color = num > 0 ? "var(--bullish-green)" : num < 0 ? "var(--bearish-red)" : "var(--text-muted)";
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
        background: "var(--bg-card)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-md)",
        padding: "12px 14px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        height: "100%",
        gap: "10px",
        cursor: "pointer",
        transition: "all 0.12s ease-in-out",
        position: "relative",
        boxShadow: "0 1px 3px rgba(0, 0, 0, 0.25)",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = "var(--border-medium)";
        e.currentTarget.style.backgroundColor = "var(--bg-card-hover)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "var(--border-subtle)";
        e.currentTarget.style.backgroundColor = "var(--bg-card)";
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
            marginBottom: "10px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap", minWidth: 0, flex: 1 }}>
            <span
              title={strategy.code}
              style={{
                fontSize: "11px",
                color: "var(--warning-amber)",
                fontFamily: "var(--font-mono)",
                fontWeight: 700,
                background: "var(--warning-amber-tint)",
                border: "1px solid rgba(255, 152, 0, 0.22)",
                padding: "2px 6px",
                borderRadius: "var(--radius-sm)",
                letterSpacing: "0.3px",
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
                color: "var(--text-secondary)",
                background: "var(--bg-input)",
                border: "1px solid var(--border-subtle)",
                padding: "2px 5px",
                borderRadius: "var(--radius-sm)",
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
                color: "var(--cyan)",
                background: "rgba(56, 189, 248, 0.1)",
                border: "1px solid rgba(56, 189, 248, 0.22)",
                padding: "2px 5px",
                borderRadius: "var(--radius-sm)",
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
                  padding: "2px 5px",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--warning-amber-tint)",
                  color: "var(--warning-amber)",
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
                padding: "2px 7px",
                borderRadius: "var(--radius-sm)",
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
        <div style={{ marginBottom: "8px" }}>
          <h3
            style={{
              margin: "0 0 4px 0",
              fontSize: "14px",
              fontWeight: 700,
              color: "var(--text-heading)",
              lineHeight: 1.3,
              letterSpacing: "-0.2px",
            }}
          >
            {strategy.name}
          </h3>
          <p
            style={{
              fontSize: "11px",
              color: "var(--text-secondary)",
              lineHeight: "1.4",
              margin: 0,
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
              minHeight: "31px",
            }}
          >
            {strategy.description || "Multi-leg algorithmic option strategy."}
          </p>
        </div>

        {/* Optimal Regimes / Strategy Focus */}
        {optimalLabel && (
          <div
            style={{
              background: "var(--warning-amber-tint)",
              border: "1px solid rgba(255, 152, 0, 0.18)",
              padding: "4px 8px",
              borderRadius: "var(--radius-sm)",
              fontSize: "11px",
              color: "var(--warning-amber)",
              marginBottom: "10px",
              display: "flex",
              alignItems: "center",
              gap: "5px",
            }}
          >
            <Activity size={11} color="var(--warning-amber)" />
            <span>
              Optimal: <strong>{optimalLabel}</strong>
            </span>
          </div>
        )}

        {/* Markets, Bias & Suggestable Tags */}
        <div style={{ display: "flex", gap: "5px", flexWrap: "wrap", marginBottom: "10px" }}>
          {strategy.markets?.map((m) => (
            <span
              key={m}
              style={{
                fontSize: "10px",
                background: "var(--bg-input)",
                border: "1px solid var(--border-subtle)",
                color: "var(--text-secondary)",
                padding: "1px 6px",
                borderRadius: "var(--radius-sm)",
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
                padding: "1px 6px",
                borderRadius: "var(--radius-sm)",
                fontWeight: 700,
                color:
                  strategy.bias === "BULLISH"
                    ? "var(--bullish-green)"
                    : strategy.bias === "BEARISH"
                    ? "var(--bearish-red)"
                    : "var(--warning-amber)",
                background:
                  strategy.bias === "BULLISH"
                    ? "var(--bullish-green-tint)"
                    : strategy.bias === "BEARISH"
                    ? "var(--bearish-red-tint)"
                    : "var(--warning-amber-tint)",
                border: `1px solid ${
                  strategy.bias === "BULLISH"
                    ? "rgba(76, 175, 80, 0.25)"
                    : strategy.bias === "BEARISH"
                    ? "rgba(239, 83, 80, 0.25)"
                    : "rgba(255, 152, 0, 0.25)"
                }`,
              }}
            >
              {strategy.bias}
            </span>
          )}

          {strategy.suggestable && (
            <span
              style={{
                fontSize: "10px",
                background: "var(--bullish-green-tint)",
                border: "1px solid rgba(76, 175, 80, 0.25)",
                color: "var(--bullish-green)",
                padding: "1px 6px",
                borderRadius: "var(--radius-sm)",
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
        {/* Dedicated Enclosed 5-Column Metrics Strip */}
        <div
          style={{
            background: "var(--bg-input)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-sm)",
            padding: "8px 10px",
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)",
            gap: "6px",
            marginBottom: "10px",
          }}
        >
          <div>
            <div style={{ fontSize: "9px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.3px", fontWeight: 600 }}>
              Win Rate
            </div>
            <div
              style={{
                color:
                  snapshot && snapshot.winRatePct >= 50
                    ? "var(--bullish-green)"
                    : snapshot
                    ? "var(--bearish-red)"
                    : "var(--text-muted)",
                fontWeight: 700,
                fontSize: "12px",
                fontFamily: "var(--font-mono)",
                marginTop: "1px",
              }}
            >
              {snapshot ? `${Number(snapshot.winRatePct).toFixed(0)}%` : "—"}
            </div>
          </div>

          <div>
            <div style={{ fontSize: "9px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.3px", fontWeight: 600 }}>
              Stop Loss
            </div>
            <div style={{ color: "var(--bearish-red)", fontWeight: 700, fontSize: "12px", fontFamily: "var(--font-mono)", marginTop: "1px" }}>
              {strategy.stopLossPct != null ? `${Number(strategy.stopLossPct).toFixed(1)}%` : "3.5%"}
            </div>
          </div>

          <div>
            <div style={{ fontSize: "9px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.3px", fontWeight: 600 }}>
              Profit Fac.
            </div>
            <div style={{ color: "var(--warning-amber)", fontWeight: 700, fontSize: "12px", fontFamily: "var(--font-mono)", marginTop: "1px" }}>
              {snapshot && snapshot.profitFactor ? Number(snapshot.profitFactor).toFixed(2) : "1.85"}
            </div>
          </div>

          <div>
            <div style={{ fontSize: "9px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.3px", fontWeight: 600 }}>
              Trades
            </div>
            <div style={{ color: "var(--text-heading)", fontWeight: 700, fontSize: "12px", fontFamily: "var(--font-mono)", marginTop: "1px" }}>
              {snapshot ? snapshot.totalTrades : "0"}
            </div>
          </div>

          <div>
            <div style={{ fontSize: "9px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.3px", fontWeight: 600 }}>
              Net P&amp;L
            </div>
            <div style={{ fontSize: "12px", marginTop: "1px" }}>
              {formatPnl(snapshot?.netPnl)}
            </div>
          </div>
        </div>

        {/* Card Actions Bottom Strip */}
        <div
          style={{
            borderTop: "1px solid var(--border-subtle)",
            paddingTop: "8px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Enabled Switch */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
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
                color: strategy.enabled ? "var(--bullish-green)" : "var(--text-muted)",
                fontWeight: 600,
              }}
            >
              {strategy.enabled ? "Live Active" : "Disabled"}
            </span>
          </div>

          {/* Action Icon Buttons */}
          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
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
