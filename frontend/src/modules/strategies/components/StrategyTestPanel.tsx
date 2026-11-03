import React, { useState } from "react";
import { Play, AlertCircle } from "lucide-react";
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
    <div className="sd-panel">
      <div className="sd-overview-cols">
        {/* Context Input */}
        <div className="sd-card">
          <div className="sd-card-header">
            <div>
              <span className="sd-card-title">Simulation Context (JSON)</span>
              <span className="sd-card-sub">
                Simulate market features, indicator values, and timestamps against this version's rule tree.
              </span>
            </div>
            <button
              type="button"
              className="sd-ctrl-btn sd-ctrl-btn--primary"
              onClick={handleRunEvaluation}
              disabled={evaluateMutation.isPending}
            >
              <Play size={12} />
              <span>{evaluateMutation.isPending ? "Evaluating..." : "Run Evaluation"}</span>
            </button>
          </div>
          <textarea
            className="sd-mono-textarea"
            rows={13}
            value={contextJson}
            onChange={(e) => setContextJson(e.target.value)}
            spellCheck={false}
          />
          {errorMsg && (
            <div className="sd-error-line">
              <AlertCircle size={13} />
              <span>{errorMsg}</span>
            </div>
          )}
        </div>

        {/* Results Output */}
        <div className="sd-card">
          <div className="sd-card-header">
            <span className="sd-card-title">Evaluation Outcome</span>
          </div>
          {!testResult ? (
            <div className="sd-empty-state">
              <span>Supply context features and click "Run Evaluation" to inspect condition verdicts.</span>
            </div>
          ) : (
            <div className="sd-panel">
              {/* Overall Signals */}
              <div className="sd-signal-grid">
                <div className={`sd-signal-box is-entry ${testResult.entryMet ? "is-active" : ""}`}>
                  <span className="sd-signal-label">ENTRY SIGNAL</span>
                  <span className="sd-signal-value">{testResult.entryMet ? "TRIGGERED" : "NO ENTRY"}</span>
                </div>
                <div className={`sd-signal-box is-exit ${testResult.exitMet ? "is-active" : ""}`}>
                  <span className="sd-signal-label">EXIT SIGNAL</span>
                  <span className="sd-signal-value">{testResult.exitMet ? "TRIGGERED" : "NO EXIT"}</span>
                </div>
              </div>

              {/* Condition breakdown */}
              <div>
                <div className="sd-card-header" style={{ marginTop: 4 }}>
                  <span className="sd-card-title">Condition Verdicts</span>
                  <span className="sd-tag">{testResult.conditions.length} checks</span>
                </div>
                <div className="sd-cond-list">
                  {testResult.conditions.map((cond, i) => (
                    <div key={i} className={`sd-cond-item ${cond.passed ? "passed" : ""}`}>
                      <div className="sd-cond-left">
                        <span className={`sd-tag ${cond.passed ? "sd-tag--green" : "sd-tag--red"}`}>
                          {cond.passed ? "PASS" : "FAIL"}
                        </span>
                        <span className="sd-cond-expr">{cond.condition}</span>
                      </div>
                      <span className="sd-cond-vals">
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
                  <div className="sd-card-header" style={{ marginTop: 4 }}>
                    <span className="sd-card-title">Triggered Leg Orders</span>
                  </div>
                  <div className="sd-leg-row">
                    {testResult.targetLegs.map((leg, i) => (
                      <span key={i} className="sd-tag sd-tag--cyan font-mono">
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
