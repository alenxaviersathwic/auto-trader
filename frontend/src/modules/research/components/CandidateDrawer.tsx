import React, { useState } from "react";
import { useCandidate } from "../hooks/useResearch";
import {
  X,
  CheckCircle,
  ShieldCheck,
  TrendingDown,
  AlertTriangle,
  Cpu,
  BookOpen,
  ExternalLink,
  Zap,
  Clock,
  FileText,
} from "lucide-react";

interface CandidateDrawerProps {
  candidateId: number | null;
  onClose: () => void;
}

export const CandidateDrawer: React.FC<CandidateDrawerProps> = ({ candidateId, onClose }) => {
  const { data: candidate, isLoading } = useCandidate(candidateId);
  const [activeNewsTab, setActiveNewsTab] = useState<"affect" | "latest" | "neutral">("affect");

  if (!candidateId) return null;

  const isCleared = candidate?.suggested || candidate?.newsStatus === "CLEAR_POSITIVE";
  const isBearish = candidate?.bearishWatch || candidate?.newsStatus === "HAS_NEGATIVE";
  const claims = candidate?.verifiedClaims || candidate?.resolvedCitations || [];
  const affectNews = candidate?.affectNews || [];
  const latestNews = candidate?.latestNews || [];
  const neutralNews = candidate?.neutralNews || [];

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        display: "flex",
        justifyContent: "flex-end",
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(4px)",
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "760px",
          height: "100%",
          background: "#121620",
          borderLeft: "1px solid #232d3f",
          display: "flex",
          flexDirection: "column",
          boxShadow: "-8px 0 32px rgba(0, 0, 0, 0.6)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: "18px 24px",
            background: "#161b26",
            borderBottom: "1px solid #232d3f",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
              <span
                style={{
                  fontSize: "12px",
                  color: candidate?.underlyingType === "INDEX" ? "#ffb74d" : "#38bdf8",
                  fontFamily: "var(--font-mono)",
                  fontWeight: 800,
                  background: candidate?.underlyingType === "INDEX" ? "rgba(255, 183, 77, 0.12)" : "rgba(56, 189, 248, 0.12)",
                  border: candidate?.underlyingType === "INDEX" ? "1px solid rgba(255, 183, 77, 0.3)" : "1px solid rgba(56, 189, 248, 0.3)",
                  padding: "2px 8px",
                  borderRadius: "4px",
                  letterSpacing: "0.5px",
                }}
              >
                {candidate?.underlyingCode}
              </span>

              <h2
                style={{
                  fontSize: "18px",
                  fontWeight: 800,
                  color: "#ffffff",
                  margin: 0,
                  letterSpacing: "-0.2px",
                }}
              >
                {candidate?.underlyingCode} Intelligence
              </h2>

              {isCleared && (
                <span
                  style={{
                    background: "rgba(0, 230, 118, 0.12)",
                    border: "1px solid rgba(0, 230, 118, 0.3)",
                    color: "#00e676",
                    fontSize: "11px",
                    fontWeight: 700,
                    padding: "2px 8px",
                    borderRadius: "6px",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <ShieldCheck size={12} /> CLEARED
                </span>
              )}

              {isBearish && (
                <span
                  style={{
                    background: "rgba(255, 82, 82, 0.12)",
                    border: "1px solid rgba(255, 82, 82, 0.3)",
                    color: "#ff5252",
                    fontSize: "11px",
                    fontWeight: 700,
                    padding: "2px 8px",
                    borderRadius: "6px",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <TrendingDown size={12} /> BEARISH
                </span>
              )}

              {candidate?.hasVectorEmbedding && (
                <span
                  style={{
                    background: "rgba(168, 85, 247, 0.15)",
                    border: "1px solid rgba(168, 85, 247, 0.4)",
                    color: "#c084fc",
                    fontSize: "11px",
                    fontWeight: 700,
                    padding: "2px 8px",
                    borderRadius: "6px",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                    fontFamily: "var(--font-mono)",
                  }}
                  title="Ranked in Top 5 Index / Top 3 Commodity, embedded in PostgreSQL vector(768)"
                >
                  <Cpu size={12} /> VECTOR MEMORY
                </span>
              )}
            </div>

            <p style={{ fontSize: "12px", color: "#888", marginTop: "4px", marginBottom: 0 }}>
              {candidate?.underlyingType} · News Status:{" "}
              <strong style={{ color: isCleared ? "#00e676" : isBearish ? "#ff5252" : "#cbd5e1" }}>
                {candidate?.newsStatus}
              </strong>
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            style={{
              background: "#18202e",
              border: "1px solid #283449",
              borderRadius: "6px",
              color: "#94a3b8",
              cursor: "pointer",
              padding: "6px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Content Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "24px", display: "flex", flexDirection: "column", gap: "20px" }}>
          {isLoading || !candidate ? (
            <div style={{ textAlign: "center", padding: "60px 20px", color: "#94a3b8" }}>
              Loading candidate details...
            </div>
          ) : (
            <>
              {/* Executive Metrics Strip */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(4, 1fr)",
                  gap: "10px",
                  background: "#161b26",
                  border: "1px solid #232d3f",
                  borderRadius: "8px",
                  padding: "14px",
                  textAlign: "center",
                }}
              >
                <div>
                  <div style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>
                    Final Score
                  </div>
                  <div
                    style={{
                      fontSize: "18px",
                      fontWeight: 800,
                      fontFamily: "var(--font-mono)",
                      color:
                        candidate.score !== null && candidate.score !== undefined
                          ? candidate.score >= 70
                            ? "#00e676"
                            : candidate.score <= 40
                            ? "#ff5252"
                            : "#ff9800"
                          : "#64748b",
                      marginTop: "2px",
                    }}
                  >
                    {candidate.score !== null && candidate.score !== undefined ? candidate.score.toFixed(1) : "—"}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>
                    Bullish Weight
                  </div>
                  <div
                    style={{
                      fontSize: "18px",
                      fontWeight: 800,
                      fontFamily: "var(--font-mono)",
                      color: "#38bdf8",
                      marginTop: "2px",
                    }}
                  >
                    {candidate.positiveWeight.toFixed(2)}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>
                    Bearish Weight
                  </div>
                  <div
                    style={{
                      fontSize: "18px",
                      fontWeight: 800,
                      fontFamily: "var(--font-mono)",
                      color: "#ff5252",
                      marginTop: "2px",
                    }}
                  >
                    {candidate.negativeWeight.toFixed(2)}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>
                    Negative Share
                  </div>
                  <div
                    style={{
                      fontSize: "18px",
                      fontWeight: 800,
                      fontFamily: "var(--font-mono)",
                      color: candidate.negativeShare > 0.25 ? "#ff5252" : "#cbd5e1",
                      marginTop: "2px",
                    }}
                  >
                    {(candidate.negativeShare * 100).toFixed(1)}%
                  </div>
                </div>
              </div>

              {/* Synthesized Blog Summary */}
              {candidate.blogSummary && (
                <div
                  style={{
                    background: "#151b27",
                    border: "1px solid #233147",
                    borderRadius: "8px",
                    padding: "16px",
                  }}
                >
                  <div
                    style={{
                      fontSize: "11px",
                      fontWeight: 700,
                      color: "#38bdf8",
                      textTransform: "uppercase",
                      letterSpacing: "0.5px",
                      marginBottom: "10px",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <BookOpen size={14} color="#38bdf8" />
                    <span>Daily Intelligence Blog Summary</span>
                  </div>
                  <div
                    style={{
                      fontSize: "13px",
                      color: "#e2e8f0",
                      lineHeight: "1.65",
                      whiteSpace: "pre-line",
                    }}
                  >
                    {candidate.blogSummary}
                  </div>
                </div>
              )}

              {/* Clearance Thesis */}
              {candidate.thesis && (
                <div
                  style={{
                    background: "#161b26",
                    border: "1px solid #232d3f",
                    borderRadius: "8px",
                    padding: "16px",
                  }}
                >
                  <div style={{ fontSize: "11px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>
                    Clearance Rationale &amp; Synthesis
                  </div>
                  <div style={{ fontSize: "13px", color: "#e2e8f0", lineHeight: "1.6" }}>
                    {candidate.thesis}
                  </div>
                </div>
              )}

              {/* Categorized News Tabs */}
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", borderBottom: "1px solid #232d3f", paddingBottom: "8px", marginBottom: "14px" }}>
                  <button
                    type="button"
                    onClick={() => setActiveNewsTab("affect")}
                    style={{
                      background: activeNewsTab === "affect" ? "#1e293b" : "transparent",
                      border: activeNewsTab === "affect" ? "1px solid #38bdf8" : "1px solid transparent",
                      color: activeNewsTab === "affect" ? "#38bdf8" : "#94a3b8",
                      borderRadius: "6px",
                      padding: "6px 12px",
                      fontSize: "12px",
                      fontWeight: 700,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <Zap size={13} />
                    <span>Market Affecting ({affectNews.length})</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setActiveNewsTab("latest")}
                    style={{
                      background: activeNewsTab === "latest" ? "#1e293b" : "transparent",
                      border: activeNewsTab === "latest" ? "1px solid #38bdf8" : "1px solid transparent",
                      color: activeNewsTab === "latest" ? "#38bdf8" : "#94a3b8",
                      borderRadius: "6px",
                      padding: "6px 12px",
                      fontSize: "12px",
                      fontWeight: 700,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <Clock size={13} />
                    <span>Today's Latest ({latestNews.length})</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setActiveNewsTab("neutral")}
                    style={{
                      background: activeNewsTab === "neutral" ? "#1e293b" : "transparent",
                      border: activeNewsTab === "neutral" ? "1px solid #38bdf8" : "1px solid transparent",
                      color: activeNewsTab === "neutral" ? "#38bdf8" : "#94a3b8",
                      borderRadius: "6px",
                      padding: "6px 12px",
                      fontSize: "12px",
                      fontWeight: 700,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <FileText size={13} />
                    <span>Neutral Commentary ({neutralNews.length})</span>
                  </button>
                </div>

                {/* News Items List */}
                {activeNewsTab === "affect" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {affectNews.length === 0 ? (
                      <div style={{ fontSize: "12px", color: "#64748b", padding: "16px", textAlign: "center", background: "#161b26", borderRadius: "6px", border: "1px dashed #232d3f" }}>
                        No high-impact catalyst news detected for this instrument today.
                      </div>
                    ) : (
                      affectNews.map((n, i) => (
                        <div
                          key={i}
                          style={{
                            background: "#161b26",
                            border: "1px solid #232d3f",
                            borderRadius: "8px",
                            padding: "12px 14px",
                            display: "flex",
                            flexDirection: "column",
                            gap: "6px",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                              <span
                                style={{
                                  fontSize: "10px",
                                  fontWeight: 800,
                                  padding: "2px 6px",
                                  borderRadius: "4px",
                                  fontFamily: "var(--font-mono)",
                                  background: n.direction === "BULLISH" ? "rgba(0, 230, 118, 0.15)" : "rgba(255, 82, 82, 0.15)",
                                  color: n.direction === "BULLISH" ? "#00e676" : "#ff5252",
                                  border: n.direction === "BULLISH" ? "1px solid rgba(0, 230, 118, 0.3)" : "1px solid rgba(255, 82, 82, 0.3)",
                                }}
                              >
                                {n.direction || "CATALYST"}
                              </span>
                              {n.catalystType && (
                                <span
                                  style={{
                                    fontSize: "10px",
                                    fontWeight: 700,
                                    padding: "2px 6px",
                                    borderRadius: "4px",
                                    background: "#1e293b",
                                    color: "#cbd5e1",
                                  }}
                                >
                                  {n.catalystType}
                                </span>
                              )}
                            </div>
                            <span style={{ fontSize: "11px", color: "#64748b", fontFamily: "var(--font-mono)" }}>
                              {n.source || "Market Source"}
                            </span>
                          </div>

                          <div style={{ fontSize: "13px", fontWeight: 700, color: "#f1f5f9" }}>
                            {n.url ? (
                              <a
                                href={n.url}
                                target="_blank"
                                rel="noreferrer"
                                style={{ color: "#f1f5f9", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: "4px" }}
                                onMouseEnter={(e) => (e.currentTarget.style.color = "#38bdf8")}
                                onMouseLeave={(e) => (e.currentTarget.style.color = "#f1f5f9")}
                              >
                                {n.title}
                                <ExternalLink size={12} />
                              </a>
                            ) : (
                              n.title
                            )}
                          </div>

                          {n.snippet && (
                            <div style={{ fontSize: "12px", color: "#94a3b8", lineHeight: "1.4" }}>
                              {n.snippet}
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                )}

                {activeNewsTab === "latest" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {latestNews.length === 0 ? (
                      <div style={{ fontSize: "12px", color: "#64748b", padding: "16px", textAlign: "center", background: "#161b26", borderRadius: "6px", border: "1px dashed #232d3f" }}>
                        No fresh today's news recorded for this instrument.
                      </div>
                    ) : (
                      latestNews.map((n, i) => (
                        <div
                          key={i}
                          style={{
                            background: "#161b26",
                            border: "1px solid #232d3f",
                            borderRadius: "8px",
                            padding: "12px 14px",
                            display: "flex",
                            flexDirection: "column",
                            gap: "6px",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                            <span style={{ fontSize: "11px", color: "#38bdf8", fontWeight: 600 }}>
                              {n.source || "Newswire"}
                            </span>
                            {n.publishedAt && (
                              <span style={{ fontSize: "11px", color: "#64748b", fontFamily: "var(--font-mono)" }}>
                                {new Date(n.publishedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: "13px", fontWeight: 700, color: "#f1f5f9" }}>
                            {n.url ? (
                              <a
                                href={n.url}
                                target="_blank"
                                rel="noreferrer"
                                style={{ color: "#f1f5f9", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: "4px" }}
                                onMouseEnter={(e) => (e.currentTarget.style.color = "#38bdf8")}
                                onMouseLeave={(e) => (e.currentTarget.style.color = "#f1f5f9")}
                              >
                                {n.title}
                                <ExternalLink size={12} />
                              </a>
                            ) : (
                              n.title
                            )}
                          </div>
                          {n.snippet && (
                            <div style={{ fontSize: "12px", color: "#94a3b8", lineHeight: "1.4" }}>
                              {n.snippet}
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                )}

                {activeNewsTab === "neutral" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {neutralNews.length === 0 ? (
                      <div style={{ fontSize: "12px", color: "#64748b", padding: "16px", textAlign: "center", background: "#161b26", borderRadius: "6px", border: "1px dashed #232d3f" }}>
                        No neutral commentary items for this instrument.
                      </div>
                    ) : (
                      neutralNews.map((n, i) => (
                        <div
                          key={i}
                          style={{
                            background: "#161b26",
                            border: "1px solid #232d3f",
                            borderRadius: "8px",
                            padding: "12px 14px",
                            display: "flex",
                            flexDirection: "column",
                            gap: "6px",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                            <span style={{ fontSize: "11px", color: "#94a3b8", fontWeight: 600 }}>
                              {n.source || "Market Digest"}
                            </span>
                            {n.publishedAt && (
                              <span style={{ fontSize: "11px", color: "#64748b", fontFamily: "var(--font-mono)" }}>
                                {new Date(n.publishedAt).toLocaleDateString()}
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: "13px", fontWeight: 600, color: "#cbd5e1" }}>
                            {n.url ? (
                              <a
                                href={n.url}
                                target="_blank"
                                rel="noreferrer"
                                style={{ color: "#cbd5e1", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: "4px" }}
                                onMouseEnter={(e) => (e.currentTarget.style.color = "#38bdf8")}
                                onMouseLeave={(e) => (e.currentTarget.style.color = "#cbd5e1")}
                              >
                                {n.title}
                                <ExternalLink size={12} />
                              </a>
                            ) : (
                              n.title
                            )}
                          </div>
                          {n.snippet && (
                            <div style={{ fontSize: "12px", color: "#8892b0", lineHeight: "1.4" }}>
                              {n.snippet}
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>

              {/* Supporting Points */}
              {candidate.supportingPoints && candidate.supportingPoints.length > 0 && (
                <div>
                  <div style={{ fontSize: "11px", fontWeight: 700, color: "#00e676", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
                    <CheckCircle size={13} color="#00e676" />
                    <span>Verified Bullish Supporting Drivers ({candidate.supportingPoints.length})</span>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {candidate.supportingPoints.map((pt, i) => (
                      <div
                        key={i}
                        style={{
                          background: "#161b26",
                          border: "1px solid #232d3f",
                          borderRadius: "8px",
                          padding: "12px 14px",
                          fontSize: "12px",
                          color: "#cbd5e1",
                          lineHeight: "1.5",
                        }}
                      >
                        {pt.text}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Watch Items & Risks */}
              {candidate.watchItems && candidate.watchItems.length > 0 && (
                <div>
                  <div style={{ fontSize: "11px", fontWeight: 700, color: "#ff5252", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
                    <AlertTriangle size={13} color="#ff5252" />
                    <span>Risk Watch &amp; Negative Signals ({candidate.watchItems.length})</span>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {candidate.watchItems.map((item, i) => (
                      <div
                        key={i}
                        style={{
                          background: "rgba(255, 82, 82, 0.08)",
                          border: "1px solid rgba(255, 82, 82, 0.25)",
                          borderRadius: "8px",
                          padding: "12px 14px",
                          fontSize: "12px",
                          color: "#ffcdd2",
                          lineHeight: "1.5",
                        }}
                      >
                        {item.text}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Verified Claims Evidence */}
              {claims.length > 0 && (
                <div>
                  <div style={{ fontSize: "11px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>
                    Verified Source Quotes ({claims.length})
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {claims.map((cl: any, i: number) => (
                      <div
                        key={i}
                        style={{
                          background: "#10141d",
                          border: "1px solid #1e2638",
                          borderRadius: "8px",
                          padding: "12px",
                          display: "flex",
                          flexDirection: "column",
                          gap: "8px",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <span style={{ fontSize: "11px", fontWeight: 700, color: cl.stance === "BULLISH" ? "#00e676" : "#ff5252" }}>
                            {cl.stance}
                          </span>
                          <span style={{ fontSize: "10px", color: "#64748b", fontFamily: "var(--font-mono)" }}>
                            {cl.domain || "Market Publisher"}
                          </span>
                        </div>
                        <div
                          style={{
                            background: "#0a0d14",
                            borderLeft: "2px solid #38bdf8",
                            padding: "8px 10px",
                            fontSize: "11px",
                            fontStyle: "italic",
                            color: "#94a3b8",
                            lineHeight: "1.4",
                          }}
                        >
                          &quot;{cl.quote || cl.statement}&quot;
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
