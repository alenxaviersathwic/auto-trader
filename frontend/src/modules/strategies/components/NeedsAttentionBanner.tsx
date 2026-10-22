import React from "react";
import { AlertTriangle, ChevronRight, CheckCircle2 } from "lucide-react";

interface NeedsAttentionBannerProps {
  attentionCount: number;
  isFiltered: boolean;
  onFilterToggle: () => void;
}

export const NeedsAttentionBanner: React.FC<NeedsAttentionBannerProps> = ({
  attentionCount,
  isFiltered,
  onFilterToggle,
}) => {
  if (attentionCount === 0) {
    return null;
  }

  return (
    <div
      className={`needs-attention-banner ${isFiltered ? "active-filter" : ""}`}
      onClick={onFilterToggle}
      role="button"
      tabIndex={0}
      title="Click to toggle filter for strategies needing attention"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: isFiltered
          ? "linear-gradient(90deg, rgba(245, 158, 11, 0.16) 0%, rgba(245, 158, 11, 0.08) 100%)"
          : "linear-gradient(90deg, rgba(245, 158, 11, 0.1) 0%, rgba(245, 158, 11, 0.04) 100%)",
        border: `1px solid ${isFiltered ? "#f59e0b" : "rgba(245, 158, 11, 0.3)"}`,
        borderRadius: "8px",
        padding: "12px 18px",
        marginBottom: "16px",
        cursor: "pointer",
        transition: "all 0.18s ease",
        gap: "14px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <div
          style={{
            width: "32px",
            height: "32px",
            borderRadius: "6px",
            background: "rgba(245, 158, 11, 0.18)",
            display: "grid",
            placeItems: "center",
            flexShrink: 0,
            color: "#f59e0b",
          }}
        >
          <AlertTriangle size={18} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
          <span style={{ fontSize: "13px", fontWeight: 700, color: "#f8fafc" }}>
            <strong style={{ color: "#f59e0b" }}>{attentionCount}</strong>{" "}
            {attentionCount === 1 ? "strategy requires" : "strategies require"} review
          </span>
          <span style={{ fontSize: "12px", color: "#94a3b8" }}>
            Flagged performance stats, missing indicators, or non-executable definitions detected.
          </span>
        </div>
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          color: "#f59e0b",
          fontSize: "12px",
          fontWeight: 700,
          background: "rgba(245, 158, 11, 0.12)",
          border: "1px solid rgba(245, 158, 11, 0.28)",
          padding: "5px 12px",
          borderRadius: "6px",
          flexShrink: 0,
        }}
      >
        <span>
          {isFiltered ? "Showing flagged only (Click to clear)" : "Filter flagged strategies"}
        </span>
        {isFiltered ? (
          <CheckCircle2 size={15} style={{ color: "#00e676" }} />
        ) : (
          <ChevronRight size={15} />
        )}
      </div>
    </div>
  );
};
