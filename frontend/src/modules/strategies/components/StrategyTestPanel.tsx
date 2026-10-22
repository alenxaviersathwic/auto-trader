import React, { useState } from "react";
import { Play, CheckCircle2, XCircle, AlertCircle, Terminal, HelpCircle } from "lucide-react";
import { useEvaluateStrategy } from "../hooks/useStrategies";
import { EvaluateResult } from "../types/strategies.types";

interface StrategyTestPanelProps {
  versionId: number;
}

export const StrategyTestPanel: React.FC<StrategyTestPanelProps> = ({
  versionId,
}) => {
  const [contextJson, setContextJson] = useState<string>(
    JSON.stringify(
      {
        timeOfDay: "09:30:00",
        market: "NIFTY",
        daysToExpire: 0,
        close: 24500,
        indicators: {
          RSI: 22,
          CCI: -160,
          SUPERTREND: 24450,
        },
      },
      null,
      2
    )
  );
  const [testResult, setTestResult] = useState<EvaluateResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const evaluateMutation = useEvaluateStrategy();

  const handleRunEvaluation = () => {
    try {
      const parsedContext = JSON.parse(contextJson);
      setErrorMsg(null);
      evaluateMutation.mutate(
        { versionId, context: parsedContext },
        {
          onSuccess: (data) => setTestResult(data),
          onError: (err: any) => setErrorMsg(err.message || "Evaluation failed"),
        }
      );
    } catch (err: any) {
      setErrorMsg("Context must be valid JSON: " + err.message);
    }
  };

  return (
    <div className="strategy-test-panel">
      <div className="mb-4">
        <h3 className="section-heading text-lg font-semibold text-primary flex items-center gap-2">
          <Terminal size={18} className="text-emerald" />
          Interactive Rule Tree Evaluation Testbed
        </h3>
        <p className="text-xs text-muted">
          Simulate market features, indicator values, and timestamps against this version's rule tree.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Context Input */}
        <div className="card-surface p-4 border border-subtle rounded flex flex-col">
          <div className="flex justify-between items-center mb-2">
            <label className="text-xs font-semibold text-secondary">
              Simulation Context (JSON):
            </label>
            <span className="text-xs text-muted">Feature Snapshot</span>
          </div>
          <textarea
            className="json-textarea font-mono text-xs flex-1"
            rows={14}
            value={contextJson}
            onChange={(e) => setContextJson(e.target.value)}
            spellCheck={false}
          />
          {errorMsg && (
            <div className="text-rose text-xs mt-2 flex items-center gap-1">
              <AlertCircle size={14} />
              <span>{errorMsg}</span>
            </div>
          )}
          <button
            type="button"
            className="btn-kite-primary mt-3 text-xs flex items-center justify-center gap-1.5"
            onClick={handleRunEvaluation}
            disabled={evaluateMutation.isPending}
          >
            <Play size={14} />
            <span>{evaluateMutation.isPending ? "Evaluating..." : "Run Evaluation"}</span>
          </button>
        </div>

        {/* Results Output */}
        <div className="card-surface p-4 border border-subtle rounded">
          <label className="text-xs font-semibold text-secondary block mb-2">
            Evaluation Outcome:
          </label>
          {!testResult ? (
            <div className="h-64 flex flex-col items-center justify-center text-muted text-xs">
              <HelpCircle size={24} className="mb-2 opacity-50" />
              <span>Supply context features and click "Run Evaluation" to see condition verdicts.</span>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Overall Signals */}
              <div className="grid grid-cols-2 gap-2">
                <div
                  className={`p-3 rounded border text-center ${
                    testResult.entryMet
                      ? "border-emerald bg-emerald-glow text-emerald"
                      : "border-subtle bg-surface text-muted"
                  }`}
                >
                  <span className="text-xs block font-bold">ENTRY SIGNAL</span>
                  <span className="text-sm font-semibold">
                    {testResult.entryMet ? "TRIGGERED" : "NO ENTRY"}
                  </span>
                </div>
                <div
                  className={`p-3 rounded border text-center ${
                    testResult.exitMet
                      ? "border-rose bg-rose-glow text-rose"
                      : "border-subtle bg-surface text-muted"
                  }`}
                >
                  <span className="text-xs block font-bold">EXIT SIGNAL</span>
                  <span className="text-sm font-semibold">
                    {testResult.exitMet ? "TRIGGERED" : "NO EXIT"}
                  </span>
                </div>
              </div>

              {/* Condition breakdown */}
              <div>
                <label className="text-xs text-muted block mb-1.5 font-semibold">
                  Condition-by-Condition Verdicts:
                </label>
                <div className="space-y-1.5 max-h-60 overflow-y-auto">
                  {testResult.conditions.map((cond, i) => (
                    <div
                      key={i}
                      className={`p-2 rounded text-xs border flex items-center justify-between ${
                        cond.passed
                          ? "border-emerald/40 bg-emerald/10 text-primary"
                          : "border-subtle bg-surface text-muted"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        {cond.passed ? (
                          <CheckCircle2 size={14} className="text-emerald shrink-0" />
                        ) : (
                          <XCircle size={14} className="text-rose shrink-0" />
                        )}
                        <span className="font-mono text-xs">{cond.condition}</span>
                      </div>
                      <span className="text-xs font-mono text-secondary">
                        {cond.leftValue !== undefined ? String(cond.leftValue) : "—"} vs{" "}
                        {cond.rightValue !== undefined ? String(cond.rightValue) : "—"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Target legs triggered */}
              {testResult.targetLegs && testResult.targetLegs.length > 0 && (
                <div>
                  <label className="text-xs text-muted block mb-1 font-semibold">
                    Triggered Leg Orders:
                  </label>
                  <div className="flex flex-wrap gap-1">
                    {testResult.targetLegs.map((leg, i) => (
                      <span key={i} className="badge-pill bg-cyan font-mono text-xs">
                        Leg #{leg.legId} ({leg.side} {leg.instrument?.optionType})
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
