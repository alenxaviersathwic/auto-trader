import React, { useState } from "react";
import { useResearchRuns, useRunLogs } from "../hooks/useResearch";
import { RunSearchFilter, RunState } from "../types/research.types";
import {
  History,
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Eye,
  Terminal,
  CheckCircle,
  AlertCircle,
  StopCircle,
  Clock,
} from "lucide-react";
import { useNavigate } from "@tanstack/react-router";
import { LiveLogDrawer } from "../components/LiveLogDrawer";

export const RunHistoryPage: React.FC = () => {
  const navigate = useNavigate();

  const [filter, setFilter] = useState<RunSearchFilter>({
    page: 0,
    limit: 15,
    sortBy: "createdAt",
    sortDir: "desc",
    status: "ACTIVE",
  });

  const [selectedRunForLog, setSelectedRunForLog] = useState<number | null>(null);

  const { data: runsData } = useResearchRuns(filter);
  const { data: logsData } = useRunLogs(selectedRunForLog ?? 0, { limit: 100 });

  const getStatusChip = (state: string) => {
    switch (state) {
      case "COMPLETED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            <CheckCircle className="w-3 h-3" /> Completed
          </span>
        );
      case "PARTIAL":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">
            <AlertCircle className="w-3 h-3" /> Partial
          </span>
        );
      case "FAILED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/30">
            <AlertCircle className="w-3 h-3" /> Failed
          </span>
        );
      case "CANCELLED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-slate-500/10 text-slate-400 border border-slate-500/30">
            <StopCircle className="w-3 h-3" /> Cancelled
          </span>
        );
      case "RUNNING":
      case "QUEUED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/30 animate-pulse">
            <span className="w-1.5 h-1.5 rounded-full bg-sky-400" /> {state}
          </span>
        );
      default:
        return <span className="text-xs text-slate-400">{state}</span>;
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#232b3b]">
        <div>
          <button
            onClick={() => navigate({ to: "/research" as any })}
            className="flex items-center gap-1.5 text-xs text-sky-400 hover:text-sky-300 font-medium mb-1 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Research Engine
          </button>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-sky-500/10 text-sky-400 border border-sky-500/20">
              <History className="w-5 h-5" />
            </div>
            <h1 className="text-xl font-bold text-slate-100">Research Run History</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Archival log of prior news clearance executions, diagnostic events and candidate yields
          </p>
        </div>

        {/* State filters */}
        <div className="flex items-center gap-2">
          <select
            value={filter.state || ""}
            onChange={(e) =>
              setFilter((prev) => ({
                ...prev,
                page: 0,
                state: (e.target.value as RunState) || undefined,
              }))
            }
            className="px-3 py-1.5 rounded-xl bg-[#161b26] border border-[#232b3b] text-xs text-slate-300 focus:outline-none"
          >
            <option value="">All States</option>
            <option value="COMPLETED">Completed</option>
            <option value="PARTIAL">Partial</option>
            <option value="FAILED">Failed</option>
            <option value="CANCELLED">Cancelled</option>
            <option value="RUNNING">Running</option>
          </select>
        </div>
      </div>

      {/* Runs Table */}
      <div className="bg-[#161b26] border border-[#232b3b] rounded-2xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-[#111520] border-b border-[#232b3b] text-slate-400 uppercase tracking-wider text-[11px]">
                <th className="py-3 px-4 font-semibold">Run ID</th>
                <th className="py-3 px-4 font-semibold">Status</th>
                <th className="py-3 px-4 font-semibold">Scope</th>
                <th className="py-3 px-4 font-semibold">Trigger</th>
                <th className="py-3 px-4 font-semibold">Result Kind</th>
                <th className="py-3 px-4 font-semibold">Duration / Started</th>
                <th className="py-3 px-4 font-semibold">Stats</th>
                <th className="py-3 px-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#232b3b]">
              {runsData?.list.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500">
                    No research runs recorded yet
                  </td>
                </tr>
              ) : (
                runsData?.list.map((run) => (
                  <tr key={run.id} className="hover:bg-[#1c2230]/50 transition-colors">
                    <td className="py-3.5 px-4 font-mono font-bold text-slate-100">
                      #{run.id}
                    </td>
                    <td className="py-3.5 px-4">{getStatusChip(run.state)}</td>
                    <td className="py-3.5 px-4">
                      <div className="flex gap-1">
                        {run.scope?.map((s) => (
                          <span
                            key={s}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-[#111520] text-slate-300 border border-[#232b3b]"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-slate-300">
                      <span className="font-medium text-slate-200">{run.triggerSource}</span>
                      {run.triggeredBy && (
                        <div className="text-[10px] text-slate-500">{run.triggeredBy}</div>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      {run.resultKind ? (
                        <span
                          className={`text-xs font-semibold ${
                            run.resultKind === "SUGGESTED" ? "text-emerald-400" : "text-slate-400"
                          }`}
                        >
                          {run.resultKind}
                        </span>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-400">
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3 text-slate-500" />
                        <span>{new Date(run.createdAt).toLocaleString()}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-[11px] text-slate-400">
                      {run.stats?.docsKept !== undefined ? (
                        <span>
                          {run.stats.docsKept} docs · {run.stats.claimsExtracted} claims
                        </span>
                      ) : (
                        <span>—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => setSelectedRunForLog(run.id)}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#111520] text-slate-300 hover:text-slate-100 border border-[#232b3b] hover:border-[#2e384d] transition-colors"
                          title="View Execution Log"
                        >
                          <Terminal className="w-3 h-3 text-sky-400" />
                          <span>Log</span>
                        </button>
                        <button
                          onClick={() => navigate({ to: "/research" as any })}
                          className="p-1 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-[#232b3b] transition-colors"
                          title="View Results"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        {runsData && runsData.totalPages > 1 && (
          <div className="p-3 bg-[#111520] border-t border-[#232b3b] flex items-center justify-between text-xs text-slate-400">
            <div>
              Showing page {runsData.page + 1} of {runsData.totalPages} ({runsData.totalItems} total runs)
            </div>
            <div className="flex items-center gap-2">
              <button
                disabled={filter.page === 0}
                onClick={() => setFilter((prev) => ({ ...prev, page: prev.page - 1 }))}
                className="p-1.5 rounded-lg bg-[#161b26] border border-[#232b3b] text-slate-300 hover:bg-[#232b3b] disabled:opacity-40"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                disabled={filter.page + 1 >= runsData.totalPages}
                onClick={() => setFilter((prev) => ({ ...prev, page: prev.page + 1 }))}
                className="p-1.5 rounded-lg bg-[#161b26] border border-[#232b3b] text-slate-300 hover:bg-[#232b3b] disabled:opacity-40"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Execution Log Drawer */}
      <LiveLogDrawer
        isOpen={selectedRunForLog !== null}
        onClose={() => setSelectedRunForLog(null)}
        runId={selectedRunForLog ?? 0}
        events={logsData?.list || []}
        isStreaming={false}
      />
    </div>
  );
};
