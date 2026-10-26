import React, { useState } from "react";
import { useSemanticSearch } from "../hooks/useResearch";
import { SemanticSearchHit } from "../types/research.types";
import { Search, Sparkles, ChevronDown, ChevronUp, ExternalLink, Hash } from "lucide-react";

export const SemanticSearchBox: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState<"CHUNKS" | "CLAIMS" | "BRIEFS">("CLAIMS");
  const [results, setResults] = useState<SemanticSearchHit[]>([]);

  const { mutate: performSearch, isPending } = useSemanticSearch();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    performSearch(
      {
        query: query.trim(),
        scope,
        topK: 8,
      },
      {
        onSuccess: (data) => {
          setResults(data.hits);
        },
      }
    );
  };

  return (
    <div className="bg-[#161b26] border border-[#232b3b] rounded-2xl p-4 shadow-lg transition-all duration-200">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              PGVector Semantic Search
              <span className="text-[10px] font-normal px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-[#232b3b]">
                Lookup Tool Only
              </span>
            </h3>
            <p className="text-[11px] text-slate-400">
              Query verified news claims and embedded chunks by meaning. Not an input to scoring.
            </p>
          </div>
        </div>

        <button
          onClick={() => setIsOpen(!isOpen)}
          className="text-xs text-sky-400 hover:text-sky-300 font-medium flex items-center gap-1"
        >
          {isOpen ? "Hide Search" : "Search Stored Articles"}
          {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      {isOpen && (
        <div className="mt-4 pt-3 border-t border-[#232b3b] space-y-4 animate-in fade-in duration-150">
          <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-2.5">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Ask anything, e.g. 'OPEC production cuts', 'RBI rate pause stance', 'Bank penalties'..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2 rounded-xl bg-[#0e1117] border border-[#232b3b] text-xs text-slate-200 focus:outline-none focus:border-sky-500"
              />
            </div>

            {/* Scope selector */}
            <div className="flex items-center bg-[#111520] p-1 rounded-xl border border-[#232b3b] text-xs">
              {(["CLAIMS", "CHUNKS", "BRIEFS"] as const).map((s) => (
                <button
                  type="button"
                  key={s}
                  onClick={() => setScope(s)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                    scope === s
                      ? "bg-[#232b3b] text-sky-400 shadow-sm"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>

            <button
              type="submit"
              disabled={isPending || !query.trim()}
              className="px-4 py-2 rounded-xl text-xs font-semibold bg-sky-500 hover:bg-sky-400 text-black disabled:opacity-40 transition-colors shadow-md"
            >
              {isPending ? "Searching..." : "Vector Search"}
            </button>
          </form>

          {/* Results list */}
          {results.length > 0 && (
            <div className="space-y-2.5 pt-2">
              <div className="text-xs font-semibold text-slate-400">
                Found {results.length} semantic matches in {scope.toLowerCase()}:
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {results.map((hit, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-xl bg-[#111520] border border-[#232b3b] space-y-1.5 text-xs"
                  >
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-semibold text-sky-400 flex items-center gap-1">
                        <Hash className="w-3 h-3" />
                        {hit.metadata?.underlyingCode || hit.type}
                      </span>
                      <span className="font-mono text-emerald-400 font-medium">
                        {(hit.similarity * 100).toFixed(1)}% match
                      </span>
                    </div>

                    <p className="text-slate-300 leading-relaxed line-clamp-3">
                      {hit.text}
                    </p>

                    <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-[#232b3b]/60">
                      <span>{hit.metadata?.domain || hit.metadata?.channel || "Vector Hit"}</span>
                      {hit.metadata?.url && (
                        <a
                          href={hit.metadata.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sky-400 hover:underline flex items-center gap-0.5"
                        >
                          Source <ExternalLink className="w-2.5 h-2.5" />
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
