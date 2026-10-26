import React, { useState } from "react";
import { ResearchRunEvent } from "../types/research.types";
import { Terminal, X } from "lucide-react";

interface LiveLogDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  runId: number;
  events: ResearchRunEvent[];
  isStreaming?: boolean;
}

export const LiveLogDrawer: React.FC<LiveLogDrawerProps> = ({
  isOpen,
  onClose,
  runId,
  events,
  isStreaming = false,
}) => {
  const [levelFilter, setLevelFilter] = useState<string>("ALL");

  if (!isOpen) return null;

  const filteredEvents = events.filter((e) => {
    if (levelFilter === "ALL") return true;
    return e.level === levelFilter;
  });

  const getLevelBadge = (level: string) => {
    switch (level) {
      case "WARN":
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-400 font-bold border border-amber-500/30">
            WARN
          </span>
        );
      case "ERROR":
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] bg-rose-500/20 text-rose-400 font-bold border border-rose-500/30">
            ERROR
          </span>
        );
      case "INFO":
      default:
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] bg-sky-500/20 text-sky-400 font-semibold border border-sky-500/30">
            INFO
          </span>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-[#0e1117] border-l border-[#232b3b] w-full max-w-2xl h-full flex flex-col shadow-2xl animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="p-4 bg-[#161b26] border-b border-[#232b3b] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-[#111520] border border-[#232b3b] text-sky-400">
              <Terminal className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-slate-100">Live Research Log</h3>
                <span className="text-xs font-mono text-slate-400">Run #{runId}</span>
                {isStreaming && (
                  <span className="flex items-center gap-1 text-[11px] text-emerald-400 font-medium animate-pulse">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    LIVE
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5">Real-time workflow execution telemetry</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={levelFilter}
              onChange={(e) => setLevelFilter(e.target.value)}
              className="bg-[#111520] border border-[#232b3b] text-xs text-slate-300 rounded px-2 py-1 outline-none"
            >
              <option value="ALL">All Levels</option>
              <option value="INFO">INFO Only</option>
              <option value="WARN">WARN Only</option>
              <option value="ERROR">ERROR Only</option>
            </select>

            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-200 p-1.5 rounded hover:bg-[#232b3b] transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Log Viewer Content */}
        <div className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-2 bg-[#090c10]">
          {filteredEvents.length === 0 ? (
            <div className="text-slate-500 text-center py-12">No execution events recorded for this run.</div>
          ) : (
            filteredEvents.map((evt) => (
              <div
                key={evt.id || evt.seq}
                className="p-2 rounded border border-[#1b2230] bg-[#10141d] hover:bg-[#151a26] transition-colors"
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <div className="flex items-center gap-2">
                    {getLevelBadge(evt.level)}
                    <span className="text-purple-400 font-bold">{evt.node}</span>
                    <span className="text-slate-500 text-[10px]">#{evt.seq}</span>
                  </div>
                  <span className="text-slate-500 text-[10px]">
                    {new Date(evt.createdAt).toLocaleTimeString()}
                  </span>
                </div>
                <div className="text-slate-200 whitespace-pre-wrap break-words">{evt.message}</div>
                {evt.data && Object.keys(evt.data).length > 0 && (
                  <pre className="mt-1.5 p-1.5 rounded bg-[#090c10] text-[10px] text-slate-400 overflow-x-auto border border-[#1b2230]">
                    {JSON.stringify(evt.data, null, 2)}
                  </pre>
                )}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="p-3 bg-[#161b26] border-t border-[#232b3b] text-xs text-slate-400 flex items-center justify-between">
          <span>{filteredEvents.length} events logged</span>
          <button
            onClick={onClose}
            className="px-3 py-1 rounded bg-[#232b3b] hover:bg-[#2e384d] text-slate-200 text-xs transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
