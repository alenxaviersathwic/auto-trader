import React from "react";
import { ResearchCandidate } from "../types/research.types";
import { ShieldCheck, AlertTriangle, ArrowUpRight } from "lucide-react";

interface CandidateCardProps {
  candidate: ResearchCandidate;
  onClick: () => void;
}

export const CandidateCard: React.FC<CandidateCardProps> = ({ candidate, onClick }) => {
  const isSuggested = candidate.suggested;
  const isBearish = candidate.bearishWatch;

  const getScoreColor = (score: number | null | undefined) => {
    if (!score) return "text-slate-400";
    if (score >= 70) return "text-emerald-400";
    if (score >= 50) return "text-sky-400";
    return "text-amber-400";
  };

  const formatAge = (dateStr?: string | null) => {
    if (!dateStr) return "";
    const diffHours = Math.round((Date.now() - new Date(dateStr).getTime()) / (1000 * 3600));
    if (diffHours <= 1) return "newest < 1 h ago";
    return `newest ${diffHours} h ago`;
  };

  return (
    <div
      onClick={onClick}
      className="p-5 rounded-2xl bg-[#161b26] border border-[#232b3b] hover:border-[#2e384d] hover:bg-[#1c2230] cursor-pointer transition-all duration-200 flex flex-col justify-between shadow-lg hover:shadow-2xl group"
    >
      <div>
        {/* Top bar: Rank, Symbol, Status Chip */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2.5">
            {candidate.rank && (
              <span className="flex items-center justify-center w-6 h-6 rounded-lg bg-emerald-500/10 text-emerald-400 font-mono text-xs font-bold border border-emerald-500/20">
                #{candidate.rank}
              </span>
            )}
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-bold text-slate-100 group-hover:text-sky-400 transition-colors">
                  {candidate.underlyingCode}
                </span>
                <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#111520] text-slate-400 border border-[#232b3b]">
                  {candidate.underlyingType}
                </span>
              </div>
            </div>
          </div>

          <div>
            {isSuggested ? (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                <ShieldCheck className="w-3.5 h-3.5" /> No negative news
              </span>
            ) : isBearish ? (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/30">
                <AlertTriangle className="w-3.5 h-3.5" /> Negative news
              </span>
            ) : (
              <span className="text-xs px-2.5 py-1 rounded-full bg-[#111520] text-slate-400 border border-[#232b3b]">
                {candidate.newsStatus}
              </span>
            )}
          </div>
        </div>

        {/* Score & Sources metadata */}
        <div className="flex items-center justify-between py-2 border-y border-[#232b3b]/60 mb-3 text-xs">
          <div className="flex items-center gap-3">
            {candidate.score !== null && candidate.score !== undefined && (
              <div className="flex items-baseline gap-1.5">
                <span className="text-slate-400 text-[11px]">Score:</span>
                <span className={`font-mono font-bold text-sm ${getScoreColor(candidate.score)}`}>
                  {candidate.score.toFixed(1)}
                </span>
                {candidate.scoreLabel && (
                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#111520] text-slate-300 font-semibold border border-[#232b3b]">
                    {candidate.scoreLabel}
                  </span>
                )}
              </div>
            )}
          </div>

          <div className="text-[11px] text-slate-400 font-mono">
            <span>{candidate.independentSources} sources</span>
            <span className="mx-1.5">·</span>
            <span>{candidate.freshArticleCount} articles</span>
            {candidate.newestArticleAt && (
              <>
                <span className="mx-1.5">·</span>
                <span className="text-emerald-400">{formatAge(candidate.newestArticleAt)}</span>
              </>
            )}
          </div>
        </div>

        {/* Thesis preview */}
        {candidate.thesis && (
          <p className="text-xs text-slate-300 leading-relaxed mb-3 line-clamp-3">
            {candidate.thesis}
          </p>
        )}

        {/* Supporting points preview */}
        {candidate.supportingPoints && candidate.supportingPoints.length > 0 && (
          <div className="space-y-1.5 mb-3">
            {candidate.supportingPoints.slice(0, 2).map((pt, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-slate-300">
                <span className="text-emerald-400 font-bold">•</span>
                <span className="line-clamp-2">{pt.text}</span>
              </div>
            ))}
          </div>
        )}

        {/* Watch items preview */}
        {candidate.watchItems && candidate.watchItems.length > 0 && (
          <div className="space-y-1.5 mb-3">
            {candidate.watchItems.slice(0, 2).map((item, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-rose-300">
                <span className="text-rose-400 font-bold">•</span>
                <span className="line-clamp-2">{item.text}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Flags & footer */}
      <div className="pt-3 border-t border-[#232b3b]/60 flex items-center justify-between text-xs">
        <div className="flex flex-wrap gap-1.5">
          {candidate.flags?.map((flag) => (
            <span
              key={flag}
              className="text-[10px] px-2 py-0.5 rounded-full bg-[#111520] text-amber-400 border border-amber-500/20"
            >
              {flag}
            </span>
          ))}
        </div>

        <span className="text-sky-400 group-hover:translate-x-0.5 transition-transform flex items-center gap-1 font-medium text-xs">
          View details <ArrowUpRight className="w-3.5 h-3.5" />
        </span>
      </div>
    </div>
  );
};
