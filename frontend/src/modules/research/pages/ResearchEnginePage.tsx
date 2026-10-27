import React, { useState } from "react";
import {
  useCandidates,
  useRunEngine,
  useRunStatus,
} from "../hooks/useResearch";
import { CandidateDrawer } from "../components/CandidateDrawer";
import { ResearchCandidate } from "../types/research.types";
import {
  Play,
  RefreshCw,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Layers,
  ChevronRight,
  Sparkles,
} from "lucide-react";

type ActiveTab = "INDEX" | "COMMODITY";

export const ResearchEnginePage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>("INDEX");
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(null);

  // Live status hook (polls GET /api/v1/research/run-status)
  const { data: runStatus, refetch: refetchStatus } = useRunStatus();

  // Run engine trigger mutation (POST /api/v1/research/run)
  const runEngineMutation = useRunEngine();

  // Single search endpoint: returns candidates sorted by opportunity score
  const {
    data: candidateSearchData,
    isLoading,
    refetch: refetchCandidates,
  } = useCandidates({ page: 0, limit: 50 });

  const isRunning = Boolean(
    runEngineMutation.isPending ||
    runStatus?.isRunning ||
    runStatus?.state === "RUNNING" ||
    runStatus?.state === "QUEUED"
  );

  const handleRunEngine = async () => {
    try {
      await runEngineMutation.mutateAsync();
      await refetchStatus();
      await refetchCandidates();
    } catch (err) {
      console.error("Failed to trigger research run:", err);
    }
  };

  const handleRefresh = () => {
    refetchStatus();
    refetchCandidates();
  };

  // Candidates list sorted by opportunity score
  const allCandidates: ResearchCandidate[] = candidateSearchData?.list || [];

  const indexCandidates = React.useMemo(() => {
    return allCandidates.filter(
      (c) => (c.scope || c.underlyingType || "").toUpperCase() === "INDEX"
    );
  }, [allCandidates]);

  const commodityCandidates = React.useMemo(() => {
    return allCandidates.filter(
      (c) => (c.scope || c.underlyingType || "").toUpperCase() === "COMMODITY"
    );
  }, [allCandidates]);

  const candidates = activeTab === "INDEX" ? indexCandidates : commodityCandidates;

  const indexOpportunityCount = React.useMemo(() => {
    return indexCandidates.filter(
      (c) => c.direction === "BULLISH" || c.direction === "BEARISH"
    ).length;
  }, [indexCandidates]);

  const commodityOpportunityCount = React.useMemo(() => {
    return commodityCandidates.filter(
      (c) => c.direction === "BULLISH" || c.direction === "BEARISH"
    ).length;
  }, [commodityCandidates]);

  const getStatusBadge = (c: ResearchCandidate) => {
    const status = c.newsStatus;
    if (c.direction === "BULLISH") {
      return (
        <span
          style={{
            background: "rgba(0, 230, 118, 0.12)",
            border: "1px solid rgba(0, 230, 118, 0.3)",
            color: "#00e676",
            fontSize: "11px",
            fontWeight: 700,
            padding: "3px 8px",
            borderRadius: "6px",
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
            letterSpacing: "0.2px",
          }}
        >
          <TrendingUp size={13} color="#00e676" />
          BULLISH
        </span>
      );
    }
    if (c.bearishWatch || status === "HAS_NEGATIVE") {
      return (
        <span
          style={{
            background: "rgba(255, 82, 82, 0.12)",
            border: "1px solid rgba(255, 82, 82, 0.3)",
            color: "#ff5252",
            fontSize: "11px",
            fontWeight: 700,
            padding: "3px 8px",
            borderRadius: "6px",
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
            letterSpacing: "0.2px",
          }}
        >
          <TrendingDown size={13} color="#ff5252" />
          BEARISH
        </span>
      );
    }
    if (status === "MIXED") {
      return (
        <span
          style={{
            background: "rgba(255, 152, 0, 0.12)",
            border: "1px solid rgba(255, 152, 0, 0.3)",
            color: "#ff9800",
            fontSize: "11px",
            fontWeight: 700,
            padding: "3px 8px",
            borderRadius: "6px",
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
            letterSpacing: "0.2px",
          }}
        >
          <AlertTriangle size={13} color="#ff9800" />
          MIXED
        </span>
      );
    }
    return (
      <span
        style={{
          background: "rgba(148, 163, 184, 0.12)",
          border: "1px solid rgba(148, 163, 184, 0.25)",
          color: "#94a3b8",
          fontSize: "11px",
          fontWeight: 600,
          padding: "3px 8px",
          borderRadius: "6px",
          display: "inline-flex",
          alignItems: "center",
          gap: "5px",
        }}
      >
        LOW COVERAGE
      </span>
    );
  };

  const getDisplayName = (code: string) => {
    const map: Record<string, string> = {
      NIFTY: "Nifty 50 Index",
      BANKNIFTY: "Nifty Bank Index",
      FINNIFTY: "Nifty Financial Services",
      MIDCPNIFTY: "Nifty Midcap Select",
      SENSEX: "BSE Sensex 30",
      BANKEX: "BSE Bankex Index",
      CRUDEOIL: "Crude Oil (MCX)",
      NATURALGAS: "Natural Gas (MCX)",
      GOLD: "Gold (MCX)",
      SILVER: "Silver (MCX)",
      COPPER: "Copper (MCX)",
      ZINC: "Zinc (MCX)",
    };
    return map[code.toUpperCase()] || code;
  };

  return (
    <div className="module-page research-page" style={{ padding: "24px 32px", maxWidth: "1600px", margin: "0 auto" }}>
      {/* ── Top Header Section matching StrategiesPage.tsx ──────────────────── */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "20px",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <h1
              style={{
                fontSize: "22px",
                fontWeight: 800,
                color: "#ffffff",
                margin: 0,
                letterSpacing: "-0.3px",
              }}
            >
              Research Engine
            </h1>

            {allCandidates.length > 0 && (
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
                {allCandidates.length} Monitored
              </span>
            )}

            {isRunning && (
              <span
                style={{
                  background: "rgba(56, 189, 248, 0.15)",
                  border: "1px solid rgba(56, 189, 248, 0.35)",
                  color: "#38bdf8",
                  fontSize: "11px",
                  fontWeight: 700,
                  padding: "2px 8px",
                  borderRadius: "12px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  fontFamily: "var(--font-mono)",
                }}
              >
                <RefreshCw size={12} className="animate-spin" />
                Pipeline {runStatus?.progressPct || 0}%
              </span>
            )}
          </div>

          <p style={{ fontSize: "13px", color: "#888", marginTop: "6px", marginBottom: 0 }}>
            Deterministic market sentiment clearance, thesis verification, and real-time risk screening across Indian trading underlyings.
          </p>
        </div>

        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <button
            type="button"
            onClick={handleRefresh}
            style={{
              background: "#18202e",
              border: "1px solid #283449",
              borderRadius: "8px",
              color: "#cbd5e1",
              padding: "8px 14px",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
            title="Refresh candidate list"
          >
            <RefreshCw size={13} className={isRunning ? "animate-spin" : ""} /> Refresh
          </button>

          <button
            type="button"
            onClick={handleRunEngine}
            disabled={isRunning}
            style={{
              background: isRunning ? "#253147" : "#00e676",
              border: "none",
              borderRadius: "8px",
              color: isRunning ? "#94a3b8" : "#000",
              padding: "8px 18px",
              fontSize: "12px",
              fontWeight: 800,
              cursor: isRunning ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              boxShadow: isRunning ? "none" : "0 4px 12px rgba(0, 230, 118, 0.25)",
              transition: "all 0.15s ease",
            }}
          >
            {isRunning ? (
              <>
                <RefreshCw size={14} className="animate-spin" />
                <span>Running Engine ({runStatus?.progressPct || 0}%)</span>
              </>
            ) : (
              <>
                <Play size={14} fill="#000" />
                <span>Run Research Engine</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* ── Tab Bar matching Zerodha Kite Aesthetic ───────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid var(--border-subtle)",
          paddingBottom: "12px",
          marginBottom: "20px",
          gap: "12px",
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button
            type="button"
            onClick={() => setActiveTab("INDEX")}
            style={{
              background: activeTab === "INDEX" ? "var(--kite-blue, #387ed1)" : "#161b26",
              color: activeTab === "INDEX" ? "#ffffff" : "#94a3b8",
              border: activeTab === "INDEX" ? "1px solid var(--kite-blue, #387ed1)" : "1px solid #232d3f",
              borderRadius: "6px",
              padding: "7px 16px",
              fontSize: "12px",
              fontWeight: 700,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              transition: "all 0.15s ease",
            }}
          >
            <Layers size={14} />
            <span>Indices ({indexCandidates.length})</span>
            {indexOpportunityCount > 0 && (
              <span
                style={{
                  background: activeTab === "INDEX" ? "rgba(255, 255, 255, 0.2)" : "rgba(0, 230, 118, 0.2)",
                  color: activeTab === "INDEX" ? "#ffffff" : "#00e676",
                  padding: "1px 6px",
                  borderRadius: "10px",
                  fontSize: "10px",
                  fontWeight: 800,
                  fontFamily: "var(--font-mono)",
                }}
              >
                {indexOpportunityCount} Opportunities
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("COMMODITY")}
            style={{
              background: activeTab === "COMMODITY" ? "var(--kite-blue, #387ed1)" : "#161b26",
              color: activeTab === "COMMODITY" ? "#ffffff" : "#94a3b8",
              border: activeTab === "COMMODITY" ? "1px solid var(--kite-blue, #387ed1)" : "1px solid #232d3f",
              borderRadius: "6px",
              padding: "7px 16px",
              fontSize: "12px",
              fontWeight: 700,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              transition: "all 0.15s ease",
            }}
          >
            <TrendingUp size={14} />
            <span>Commodities ({commodityCandidates.length})</span>
            {commodityOpportunityCount > 0 && (
              <span
                style={{
                  background: activeTab === "COMMODITY" ? "rgba(255, 255, 255, 0.2)" : "rgba(0, 230, 118, 0.2)",
                  color: activeTab === "COMMODITY" ? "#ffffff" : "#00e676",
                  padding: "1px 6px",
                  borderRadius: "10px",
                  fontSize: "10px",
                  fontWeight: 800,
                  fontFamily: "var(--font-mono)",
                }}
              >
                {commodityOpportunityCount} Opportunities
              </span>
            )}
          </button>
        </div>

        <div style={{ color: "#64748b", fontSize: "12px", fontFamily: "var(--font-mono)" }}>
          Showing {candidates.length} underlyings sorted by opportunity score
        </div>
      </div>

      {/* ── Candidate Trading Cards Grid ─────────────────────────────────── */}
      {isLoading ? (
        <div style={{ textAlign: "center", padding: "80px 20px", color: "#94a3b8" }}>
          <RefreshCw size={24} className="animate-spin" style={{ margin: "0 auto 12px", color: "var(--kite-blue, #387ed1)" }} />
          <div style={{ fontSize: "14px", fontWeight: 600 }}>Loading evaluated underlyings...</div>
        </div>
      ) : candidates.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: "80px 20px",
            background: "#161b26",
            border: "1px solid #232d3f",
            borderRadius: "10px",
            color: "#94a3b8",
          }}
        >
          <Sparkles size={28} style={{ margin: "0 auto 12px", color: "#64748b" }} />
          <div style={{ fontSize: "15px", fontWeight: 700, color: "#ffffff" }}>No coverage evaluated yet</div>
          <p style={{ fontSize: "12px", color: "#64748b", marginTop: "6px" }}>
            Click &quot;Run Research Engine&quot; above to fetch live market news and evaluate underlyings.
          </p>
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))",
            gap: "16px",
          }}
        >
          {candidates.map((c) => {
            const itemCode = c.item || c.underlyingCode;
            const itemScope = c.scope || c.underlyingType;
            const itemScore = c.opportunityScore ?? c.latestScore ?? c.score;
            const status = c.newsStatus;
            const isCleared = c.direction === "BULLISH";
            const isBearish = c.direction === "BEARISH" || c.bearishWatch || status === "HAS_NEGATIVE";

            return (
              <div
                key={c.id || itemCode}
                onClick={() => setSelectedCandidateId(c.id)}
                style={{
                  background: "#161b26",
                  border: isCleared
                    ? "1px solid rgba(0, 230, 118, 0.35)"
                    : isBearish
                    ? "1px solid rgba(255, 82, 82, 0.35)"
                    : "1px solid #232d3f",
                  borderRadius: "10px",
                  padding: "18px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  height: "100%",
                  gap: "14px",
                  cursor: "pointer",
                  transition: "all 0.18s ease-in-out",
                  position: "relative",
                  boxShadow: isCleared
                    ? "0 4px 14px rgba(0, 230, 118, 0.08)"
                    : isBearish
                    ? "0 4px 14px rgba(255, 82, 82, 0.08)"
                    : "0 2px 8px rgba(0, 0, 0, 0.25)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = "var(--kite-blue, #387ed1)";
                  e.currentTarget.style.transform = "translateY(-2px)";
                  e.currentTarget.style.boxShadow = "0 8px 24px rgba(0, 0, 0, 0.45)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = isCleared
                    ? "rgba(0, 230, 118, 0.35)"
                    : isBearish
                    ? "rgba(255, 82, 82, 0.35)"
                    : "#232d3f";
                  e.currentTarget.style.transform = "none";
                  e.currentTarget.style.boxShadow = isCleared
                    ? "0 4px 14px rgba(0, 230, 118, 0.08)"
                    : isBearish
                    ? "0 4px 14px rgba(255, 82, 82, 0.08)"
                    : "0 2px 8px rgba(0, 0, 0, 0.25)";
                }}
              >
                <div>
                  {/* Top Bar: Symbol Badge, Name, Status Badge */}
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      gap: "10px",
                      marginBottom: "12px",
                    }}
                  >
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span
                          style={{
                            fontSize: "11px",
                            color: itemScope === "INDEX" ? "#ffb74d" : "#38bdf8",
                            fontFamily: "var(--font-mono)",
                            fontWeight: 800,
                            background: itemScope === "INDEX" ? "rgba(255, 183, 77, 0.1)" : "rgba(56, 189, 248, 0.1)",
                            border: itemScope === "INDEX" ? "1px solid rgba(255, 183, 77, 0.25)" : "1px solid rgba(56, 189, 248, 0.25)",
                            padding: "2px 7px",
                            borderRadius: "4px",
                            letterSpacing: "0.5px",
                          }}
                        >
                          {itemCode}
                        </span>
                        <h2
                          style={{
                            fontSize: "14px",
                            fontWeight: 700,
                            color: "#ffffff",
                            margin: 0,
                          }}
                        >
                          {getDisplayName(itemCode)}
                        </h2>
                      </div>
                      <div style={{ fontSize: "11px", color: "#64748b", marginTop: "3px" }}>
                        {itemScope} · {c.freshArticleCount || 0} fresh articles
                      </div>
                    </div>

                    <div>{getStatusBadge(c)}</div>
                  </div>

                  {/* Metric Strip (Score, Sources, Sentiment) */}
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(3, 1fr)",
                      gap: "8px",
                      background: "#10141d",
                      border: "1px solid #1e2638",
                      borderRadius: "8px",
                      padding: "10px",
                      marginBottom: "12px",
                      textAlign: "center",
                    }}
                  >
                    <div>
                      <div style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.5px" }}>
                        Score
                      </div>
                      <div
                        style={{
                          fontSize: "15px",
                          fontWeight: 800,
                          fontFamily: "var(--font-mono)",
                          marginTop: "2px",
                          color:
                            itemScore !== null && itemScore !== undefined
                              ? itemScore >= 70
                                ? "#00e676"
                                : itemScore <= 40
                                ? "#ff5252"
                                : "#ff9800"
                              : "#64748b",
                        }}
                      >
                        {itemScore !== null && itemScore !== undefined ? itemScore.toFixed(1) : "—"}
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.5px" }}>
                        Sources
                      </div>
                      <div
                        style={{
                          fontSize: "15px",
                          fontWeight: 800,
                          fontFamily: "var(--font-mono)",
                          color: "#e2e8f0",
                          marginTop: "2px",
                        }}
                      >
                        {c.independentSources || 0}
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.5px" }}>
                        Sentiment
                      </div>
                      <div
                        style={{
                          fontSize: "14px",
                          fontWeight: 800,
                          fontFamily: "var(--font-mono)",
                          marginTop: "2px",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: "4px",
                        }}
                      >
                        <span style={{ color: "#00e676" }}>+{c.positiveClaims || 0}</span>
                        <span style={{ color: "#475569" }}>/</span>
                        <span style={{ color: "#ff5252" }}>-{c.negativeClaims || 0}</span>
                      </div>
                    </div>
                  </div>

                  {/* Summary / Clearance Thesis */}
                  <div
                    style={{
                      fontSize: "12px",
                      color: "#cbd5e1",
                      lineHeight: "1.45",
                      minHeight: "36px",
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                    }}
                  >
                    {c.thesis ||
                      (c.reasons && c.reasons.length > 0 ? c.reasons[0] : null) ||
                      (c.supportingPoints && c.supportingPoints.length > 0
                        ? c.supportingPoints[0].text
                        : "No material news anomalies detected for this underlying.")}
                  </div>
                </div>

                {/* Bottom Footer Row */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    paddingTop: "12px",
                    borderTop: "1px solid #1e2638",
                    fontSize: "11px",
                    color: "var(--kite-blue, #387ed1)",
                    fontWeight: 700,
                  }}
                >
                  <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                    <span>Inspect Research &amp; Claims</span>
                    <ChevronRight size={14} />
                  </span>
                  <span style={{ color: "#64748b", fontFamily: "var(--font-mono)", fontSize: "10px", fontWeight: 500 }}>
                    {c.independentSources || 0} publishers
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Candidate Details Inspection Drawer ─────────────────────────── */}
      <CandidateDrawer
        candidateId={selectedCandidateId}
        onClose={() => setSelectedCandidateId(null)}
      />
    </div>
  );
};
