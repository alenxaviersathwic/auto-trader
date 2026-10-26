import React, { useState } from "react";
import { useLatestResults } from "../hooks/useResearch";
import { CandidateCard } from "../components/CandidateCard";
import { CandidateDrawer } from "../components/CandidateDrawer";
import { SemanticSearchBox } from "../components/SemanticSearchBox";
import { UnderlyingType } from "../types/research.types";
import {
  ShieldCheck,
  AlertTriangle,
  Clock,
  ChevronDown,
  ChevronUp,
  Info,
  Layers,
  ArrowLeft,
} from "lucide-react";
import { useNavigate } from "@tanstack/react-router";

export const ResultsPage: React.FC = () => {
  const navigate = useNavigate();
  const [activeType, setActiveType] = useState<UnderlyingType>("INDEX");
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(null);

  // Collapsible sections for non-suggested groups
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({
    hasNegative: true,
    mixed: false,
    clearNeutral: false,
    noCoverage: false,
  });

  const toggleGroup = (key: string) => {
    setOpenGroups((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const { data: results } = useLatestResults(activeType);

  const formatAge = (hours: number | null) => {
    if (hours === null || hours === undefined) return "Recent";
    if (hours < 1) return "< 1 hour old";
    return `${Math.round(hours)} hours old`;
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      {/* Back button & Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#232b3b]">
        <div>
          <button
            onClick={() => navigate({ to: "/research" as any })}
            className="flex items-center gap-1.5 text-xs text-sky-400 hover:text-sky-300 font-medium mb-1 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Research Engine
          </button>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <h1 className="text-xl font-bold text-slate-100">Research Clearance Results</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Verified news clearance analysis. Evaluates whether fresh articles contain negative or supportive news.
          </p>
        </div>

        {/* Underlying Type Tabs */}
        <div className="flex items-center bg-[#111520] p-1 rounded-2xl border border-[#232b3b]">
          {(["INDEX", "COMMODITY", "STOCK"] as const).map((type) => (
            <button
              key={type}
              onClick={() => setActiveType(type)}
              className={`px-4 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                activeType === type
                  ? "bg-emerald-500 text-black shadow-lg shadow-emerald-500/20"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {type === "INDEX" ? "Indices" : type === "COMMODITY" ? "Commodities" : "Stocks"}
            </button>
          ))}
        </div>
      </div>

      {/* Mandatory News Clearance Warning Alert */}
      <div className="p-3.5 rounded-2xl bg-amber-500/10 border border-amber-500/25 flex items-start gap-3">
        <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
        <div className="text-xs text-amber-200/90 leading-relaxed">
          <span className="font-semibold text-amber-300">News screen, not a forecast.</span> No negative news found
          does not mean safe. Market prices may move ahead of news publication. A suggested status means only that
          the reviewed fresh sources contain no material negative claims and have verified supportive coverage.
        </div>
      </div>

      {/* Run Metadata Banner */}
      {results?.run ? (
        <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-2xl bg-[#161b26] border border-[#232b3b] text-xs">
          <div className="flex items-center gap-4 text-slate-300">
            <span className="font-mono text-slate-400">Run #{results.run.id}</span>
            <span>•</span>
            <span className="flex items-center gap-1.5 text-slate-400">
              <Clock className="w-3.5 h-3.5" />
              Finished {results.run.finishedAt ? new Date(results.run.finishedAt).toLocaleTimeString() : "Recently"} (
              {formatAge(results.run.ageHours)})
            </span>
            <span>•</span>
            <span className="text-emerald-400 font-medium">
              Freshness Window: {results.run.windowHours}h
            </span>
          </div>

          <div className="text-slate-400 font-mono text-[11px]">
            {results.suggested.length} Suggested · {results.bearishWatch.length} Bearish Watch ·{" "}
            {results.hasNegative.length} Negatives
          </div>
        </div>
      ) : (
        <div className="text-center py-12 rounded-2xl bg-[#161b26] border border-[#232b3b] p-8">
          <Layers className="w-8 h-8 text-slate-500 mx-auto mb-2" />
          <h3 className="text-sm font-semibold text-slate-200">Research has not run yet for {activeType}</h3>
          <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
            Run the research engine from the Research Engine tab to extract fresh news clearance.
          </p>
          <button
            onClick={() => navigate({ to: "/research" as any })}
            className="mt-4 px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-500 hover:bg-emerald-400 text-black shadow-lg"
          >
            Go to Research Engine to Run
          </button>
        </div>
      )}

      {/* Vector Semantic Search lookup box */}
      <SemanticSearchBox />

      {/* SUGGESTED CANDIDATES SECTION */}
      {results && results.suggested.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              Suggested Underlyings (Clear of Negatives & Supported)
            </h2>
            <span className="text-xs text-emerald-400 font-medium">
              Top {results.suggested.length} Qualified
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {results.suggested.map((cand) => (
              <CandidateCard
                key={cand.id}
                candidate={cand}
                onClick={() => setSelectedCandidateId(cand.id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* BEARISH WATCH SECTION */}
      {results && results.bearishWatch.length > 0 && (
        <div className="space-y-3 pt-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-rose-400 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-400" />
                Bearish Watch (Strong Negative News Consensus)
              </h2>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
                Information Only
              </span>
            </div>
            <span className="text-xs text-slate-400">{results.bearishWatch.length} Underlyings</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {results.bearishWatch.map((cand) => (
              <CandidateCard
                key={cand.id}
                candidate={cand}
                onClick={() => setSelectedCandidateId(cand.id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* NOT SUGGESTED COLLAPSIBLE ACCORDIONS */}
      {results && (
        <div className="space-y-3 pt-4 border-t border-[#232b3b]">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Not Suggested (Detailed Clearance Reasons)
          </h2>

          {/* 1. Has Negative News */}
          {results.hasNegative.length > 0 && (
            <div className="rounded-2xl bg-[#161b26] border border-[#232b3b] overflow-hidden">
              <button
                onClick={() => toggleGroup("hasNegative")}
                className="w-full p-4 flex items-center justify-between text-left hover:bg-[#1c2230] transition-colors"
              >
                <div className="flex items-center gap-2.5">
                  <div className="w-2 h-2 rounded-full bg-rose-400" />
                  <span className="text-xs font-semibold text-slate-200">
                    Has Material Negative News ({results.hasNegative.length})
                  </span>
                </div>
                {openGroups.hasNegative ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
              </button>
              {openGroups.hasNegative && (
                <div className="p-4 pt-0 divide-y divide-[#232b3b]/60">
                  {results.hasNegative.map((cand) => (
                    <div
                      key={cand.id}
                      onClick={() => setSelectedCandidateId(cand.id)}
                      className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-[#1c2230]/40 cursor-pointer p-2 rounded-xl transition-colors"
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="text-xs font-bold text-slate-100">{cand.underlyingCode}</span>
                        <span className="text-[11px] text-slate-400">
                          {cand.reasons?.[0] || "Found material negative claims"}
                        </span>
                      </div>
                      <span className="text-[11px] text-sky-400 font-medium">View source citations →</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 2. Mixed Signals */}
          {results.mixed.length > 0 && (
            <div className="rounded-2xl bg-[#161b26] border border-[#232b3b] overflow-hidden">
              <button
                onClick={() => toggleGroup("mixed")}
                className="w-full p-4 flex items-center justify-between text-left hover:bg-[#1c2230] transition-colors"
              >
                <div className="flex items-center gap-2.5">
                  <div className="w-2 h-2 rounded-full bg-amber-400" />
                  <span className="text-xs font-semibold text-slate-200">
                    Mixed: Risk Words Found But Unconfirmed ({results.mixed.length})
                  </span>
                </div>
                {openGroups.mixed ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
              </button>
              {openGroups.mixed && (
                <div className="p-4 pt-0 divide-y divide-[#232b3b]/60">
                  {results.mixed.map((cand) => (
                    <div
                      key={cand.id}
                      onClick={() => setSelectedCandidateId(cand.id)}
                      className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-[#1c2230]/40 cursor-pointer p-2 rounded-xl transition-colors"
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="text-xs font-bold text-slate-100">{cand.underlyingCode}</span>
                        <span className="text-[11px] text-amber-300/90">
                          {cand.reasons?.[0] || "Risk terms detected in proximity"}
                        </span>
                      </div>
                      <span className="text-[11px] text-sky-400 font-medium">View details →</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 3. Clear Neutral */}
          {results.clearNeutral.length > 0 && (
            <div className="rounded-2xl bg-[#161b26] border border-[#232b3b] overflow-hidden">
              <button
                onClick={() => toggleGroup("clearNeutral")}
                className="w-full p-4 flex items-center justify-between text-left hover:bg-[#1c2230] transition-colors"
              >
                <div className="flex items-center gap-2.5">
                  <div className="w-2 h-2 rounded-full bg-slate-400" />
                  <span className="text-xs font-semibold text-slate-200">
                    Clear But No Catalyst ({results.clearNeutral.length})
                  </span>
                </div>
                {openGroups.clearNeutral ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
              </button>
              {openGroups.clearNeutral && (
                <div className="p-4 pt-0 divide-y divide-[#232b3b]/60">
                  {results.clearNeutral.map((cand) => (
                    <div
                      key={cand.id}
                      onClick={() => setSelectedCandidateId(cand.id)}
                      className="py-3 flex items-center justify-between gap-2 hover:bg-[#1c2230]/40 cursor-pointer p-2 rounded-xl transition-colors"
                    >
                      <span className="text-xs font-bold text-slate-100">{cand.underlyingCode}</span>
                      <span className="text-[11px] text-slate-400">
                        {cand.reasons?.[0] || "No negative news, but insufficient supportive catalyst"}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 4. No Coverage */}
          {results.noCoverage.length > 0 && (
            <div className="rounded-2xl bg-[#161b26] border border-[#232b3b] overflow-hidden">
              <button
                onClick={() => toggleGroup("noCoverage")}
                className="w-full p-4 flex items-center justify-between text-left hover:bg-[#1c2230] transition-colors"
              >
                <div className="flex items-center gap-2.5">
                  <div className="w-2 h-2 rounded-full bg-slate-600" />
                  <span className="text-xs font-semibold text-slate-200">
                    No Fresh Coverage ({results.noCoverage.length})
                  </span>
                </div>
                {openGroups.noCoverage ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
              </button>
              {openGroups.noCoverage && (
                <div className="p-4 pt-0 divide-y divide-[#232b3b]/60">
                  {results.noCoverage.map((cand) => (
                    <div
                      key={cand.id}
                      onClick={() => setSelectedCandidateId(cand.id)}
                      className="py-3 flex items-center justify-between gap-2 hover:bg-[#1c2230]/40 cursor-pointer p-2 rounded-xl transition-colors"
                    >
                      <span className="text-xs font-bold text-slate-100">{cand.underlyingCode}</span>
                      <span className="text-[11px] text-slate-400">
                        {cand.reasons?.[0] || "Fewer than minimum independent sources or stale articles"}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Candidate detail drawer */}
      <CandidateDrawer
        candidateId={selectedCandidateId}
        onClose={() => setSelectedCandidateId(null)}
      />
    </div>
  );
};
