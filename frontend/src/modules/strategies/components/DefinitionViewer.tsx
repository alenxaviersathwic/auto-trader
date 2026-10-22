import React, { useState } from "react";
import { Code, Eye, FileText, Layers, Cpu } from "lucide-react";

interface DefinitionViewerProps {
  definition?: Record<string, any> | null;
  format?: string;
}

export const DefinitionViewer: React.FC<DefinitionViewerProps> = ({
  definition,
  format = "RULE_TREE",
}) => {
  const [viewMode, setViewMode] = useState<"structured" | "json">("structured");
  const [activeCaseIdx, setActiveCaseIdx] = useState<number>(0);

  if (!definition) {
    return <div className="text-muted p-4">No definition available.</div>;
  }

  const defFormat = definition.format || format;

  // Helper to turn typed Operand into friendly readable string
  const formatOperand = (op: any): string => {
    if (!op) return "—";
    if (op.const !== undefined) {
      if (op.type === "TIME") return `time ${op.const}`;
      if (Array.isArray(op.const)) return `[${op.const.join(", ")}]`;
      return String(op.const);
    }
    if (op.param !== undefined) {
      return `parameter(${op.param})`;
    }
    const source = op.source;
    if (source === "PRICE") {
      const tf = op.timeframe ? ` (${op.timeframe})` : "";
      const bar = op.bar && op.bar !== "CURRENT" ? ` ${op.bar}` : "";
      return `Price.${op.field}${tf}${bar}`;
    }
    if (source === "DAY") {
      return `${op.day}.${op.field}`;
    }
    if (source === "INDICATOR") {
      const params = op.params ? `(${JSON.stringify(op.params)})` : "";
      const inst = op.instance ? ` [${op.instance}]` : "";
      const out = op.output && op.output !== "value" ? `.${op.output}` : "";
      return `${op.code}${inst}${out}${params}`;
    }
    if (source === "TIME") {
      return `TimeOfDay`;
    }
    if (source === "CONTEXT") {
      return `Context.${op.field}`;
    }
    if (source === "POSITION") {
      return `Position[Case ${op.caseKey}, Leg ${op.legId}].${op.field}`;
    }
    if (source === "TRADE_PLAN") {
      return `TradePlan.${op.field}`;
    }
    return JSON.stringify(op);
  };

  // Helper to format operator
  const formatOperator = (op: string): string => {
    switch (op) {
      case "IS_ABOVE":
        return "is above";
      case "IS_ABOVE_OR_EQUAL":
        return "is at or above";
      case "IS_BELOW":
        return "is below";
      case "IS_BELOW_OR_EQUAL":
        return "is at or below";
      case "EQUALS":
        return "equals";
      case "NOT_EQUALS":
        return "does not equal";
      case "CROSSES_ABOVE":
        return "crosses above";
      case "CROSSES_BELOW":
        return "crosses below";
      case "IN":
        return "is in";
      case "NOT_IN":
        return "is not in";
      case "BETWEEN":
        return "is between";
      default:
        return op;
    }
  };

  // Helper to render ConditionNode recursively
  const renderConditionNode = (node: any, depth: number = 0): React.ReactNode => {
    if (!node) return <span className="text-muted">None (Always trigger)</span>;

    if (node.op) {
      const items = node.items || [];
      const joinLabel = node.op === "ALL" ? "AND" : node.op === "ANY" ? "OR" : "NOT";

      return (
        <div className={`condition-group depth-${depth}`}>
          <div className="condition-group-badge">{node.op}</div>
          <div className="condition-group-items">
            {items.map((sub: any, i: number) => (
              <React.Fragment key={i}>
                <div className="condition-row">
                  {renderConditionNode(sub, depth + 1)}
                </div>
                {i < items.length - 1 && (
                  <div className="condition-connector">{joinLabel}</div>
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
      );
    }

    if (node.left && node.operator) {
      return (
        <div className="condition-sentence">
          <span className="operand-left">{formatOperand(node.left)}</span>
          <span className="operator-badge">{formatOperator(node.operator)}</span>
          <span className="operand-right">{formatOperand(node.right)}</span>
        </div>
      );
    }

    return <pre className="text-xs">{JSON.stringify(node, null, 2)}</pre>;
  };

  return (
    <div className="definition-viewer">
      <div className="definition-viewer-header">
        <div className="viewer-title-group">
          <Layers size={18} className="text-cyan" />
          <h3 className="viewer-title">Definition ({defFormat})</h3>
          <span className="badge-pill schema-version">v{definition.schemaVersion || 2}</span>
        </div>
        <div className="viewer-actions">
          <button
            type="button"
            className={`btn-toggle-view ${viewMode === "structured" ? "active" : ""}`}
            onClick={() => setViewMode("structured")}
          >
            <Eye size={14} />
            <span>Structured View</span>
          </button>
          <button
            type="button"
            className={`btn-toggle-view ${viewMode === "json" ? "active" : ""}`}
            onClick={() => setViewMode("json")}
          >
            <Code size={14} />
            <span>Raw JSON</span>
          </button>
        </div>
      </div>

      {viewMode === "json" ? (
        <div className="raw-json-container">
          <pre className="raw-json-content">
            {JSON.stringify(definition, null, 2)}
          </pre>
        </div>
      ) : defFormat === "SUMMARY" ? (
        <div className="summary-format-view">
          <div className="card-sub-header">
            <FileText size={16} />
            <h4>Descriptive Summary Specification</h4>
          </div>
          <p className="text-muted text-sm mb-4">
            This strategy was imported as a legacy summary with no executable entry or exit rule trees.
          </p>
          <div className="summary-grid">
            <div className="summary-item">
              <label>Entry Label</label>
              <span>{definition.summary?.entryLabel || "—"}</span>
            </div>
            <div className="summary-item">
              <label>Target R:R</label>
              <span>{definition.summary?.targetRr ? `${definition.summary.targetRr} : 1` : "—"}</span>
            </div>
            <div className="summary-item">
              <label>Max Risk %</label>
              <span>{definition.summary?.maxRiskPct ? `${definition.summary.maxRiskPct}%` : "—"}</span>
            </div>
            <div className="summary-item">
              <label>Exchange</label>
              <span>{definition.summary?.exchange || "—"}</span>
            </div>
          </div>
          <div className="indicators-tag-list mt-4">
            <label className="text-xs text-muted block mb-2">Required Technical Indicators:</label>
            <div className="tag-flex">
              {(definition.summary?.indicators || []).map((ind: string, idx: number) => (
                <span key={idx} className="badge-indicator">
                  {ind}
                </span>
              ))}
            </div>
          </div>
        </div>
      ) : defFormat === "EVALUATOR" ? (
        <div className="evaluator-format-view">
          <div className="card-sub-header">
            <Cpu size={16} />
            <h4>Code-Backed Evaluator Strategy</h4>
          </div>
          <div className="evaluator-details-grid">
            <div className="evaluator-meta-item">
              <label>Registered Evaluator Code</label>
              <span className="font-mono text-cyan">{definition.evaluator}</span>
            </div>
            <div className="evaluator-meta-item">
              <label>Stop Mode</label>
              <span className="badge-pill">{definition.riskPolicy?.stopMode || "EVALUATOR_OWNED"}</span>
            </div>
          </div>
          <div className="evaluator-params-section mt-4">
            <label className="text-xs text-muted block mb-2">Evaluator Parameters:</label>
            <table className="data-table params-table">
              <thead>
                <tr>
                  <th>Parameter Name</th>
                  <th>Configured Value</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(definition.parameters || {}).map(([key, val]) => (
                  <tr key={key}>
                    <td className="font-mono text-sm">{key}</td>
                    <td className="font-mono text-emerald">{String(val)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="rule-tree-format-view">
          {/* Parallel Cases or Single Case Tabs */}
          {Array.isArray(definition.cases) && definition.cases.length > 1 && (
            <div className="case-tabs">
              {definition.cases.map((c: any, idx: number) => (
                <button
                  key={c.key || idx}
                  type="button"
                  className={`case-tab-btn ${activeCaseIdx === idx ? "active" : ""}`}
                  onClick={() => setActiveCaseIdx(idx)}
                >
                  Case {c.key || idx} ({c.bias || "DYNAMIC"})
                </button>
              ))}
            </div>
          )}

          {definition.cases && definition.cases[activeCaseIdx] && (
            <div className="active-case-content">
              {/* Entry Conditions */}
              <div className="section-block">
                <div className="block-title">
                  <span className="step-badge entry">ENTRY</span>
                  <h4>Entry Rule (When Condition)</h4>
                </div>
                <div className="condition-tree-box">
                  {renderConditionNode(definition.cases[activeCaseIdx].entry?.when)}
                </div>
              </div>

              {/* Legs Table */}
              <div className="section-block">
                <div className="block-title">
                  <span className="step-badge legs">LEGS</span>
                  <h4>Entry Orders & Execution Legs</h4>
                </div>
                <div className="table-responsive">
                  <table className="data-table legs-table">
                    <thead>
                      <tr>
                        <th>Leg ID</th>
                        <th>Action</th>
                        <th>Option</th>
                        <th>Expiry</th>
                        <th>Strike Selector</th>
                        <th>Quantity</th>
                        <th>Stop Loss</th>
                        <th>Target</th>
                        <th>Trailing Stop</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(definition.cases[activeCaseIdx].entry?.legs || []).map(
                        (leg: any) => (
                          <tr key={leg.legId}>
                            <td className="font-mono">{leg.legId}</td>
                            <td>
                              <span
                                className={`badge-pill ${leg.side === "BUY" ? "bg-emerald" : "bg-rose"}`}
                              >
                                {leg.side}
                              </span>
                            </td>
                            <td>
                              <span className="badge-pill bg-elevated">
                                {leg.instrument?.optionType || "CE/PE"}
                              </span>
                            </td>
                            <td>
                              {leg.instrument?.expiry?.cycle || "WEEKLY"} (
                              {leg.instrument?.expiry?.index || 1})
                            </td>
                            <td className="font-mono">
                              {leg.instrument?.strike?.selector === "ATM_OFFSET"
                                ? `ATM ${leg.instrument.strike.steps >= 0 ? `+${leg.instrument.strike.steps}` : leg.instrument.strike.steps}`
                                : leg.instrument?.strike?.selector === "DELTA"
                                ? `Delta ${leg.instrument.strike.delta}`
                                : leg.instrument?.strike?.selector === "PREMIUM"
                                ? `₹${leg.instrument.strike.premium}`
                                : JSON.stringify(leg.instrument?.strike)}
                            </td>
                            <td>
                              {leg.quantity?.value} {leg.quantity?.unit || "LOT"}
                            </td>
                            <td>
                              {leg.stopLoss ? (
                                <span className="text-rose">
                                  {leg.stopLoss.value}
                                  {leg.stopLoss.type === "PERCENT" ? "%" : " pts"}
                                </span>
                              ) : (
                                "—"
                              )}
                            </td>
                            <td>
                              {leg.target ? (
                                <span className="text-emerald">
                                  {leg.target.value}
                                  {leg.target.type === "PERCENT" ? "%" : " pts"}
                                </span>
                              ) : (
                                "—"
                              )}
                            </td>
                            <td>
                              {leg.stopLoss?.trail ? (
                                <span className="text-cyan text-xs">
                                  +{leg.stopLoss.trail.adjustValue} / +{leg.stopLoss.trail.trailingValue}
                                </span>
                              ) : (
                                "—"
                              )}
                            </td>
                          </tr>
                        )
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Exit Conditions */}
              <div className="section-block">
                <div className="block-title">
                  <span className="step-badge exit">EXIT</span>
                  <h4>Exit Rule (When Condition)</h4>
                </div>
                <div className="condition-tree-box">
                  {renderConditionNode(definition.cases[activeCaseIdx].exit?.when)}
                </div>
              </div>

              {/* Adjustments */}
              {Array.isArray(definition.cases[activeCaseIdx].adjustments) &&
                definition.cases[activeCaseIdx].adjustments.length > 0 && (
                  <div className="section-block">
                    <div className="block-title">
                      <span className="step-badge adjust">ADJUST</span>
                      <h4>Dynamic Intra-Session Adjustments</h4>
                    </div>
                    <div className="adjustments-list">
                      {definition.cases[activeCaseIdx].adjustments.map((adj: any) => (
                        <div key={adj.key} className="adjustment-card">
                          <div className="adj-header">
                            <span className="adj-key font-mono">{adj.key}</span>
                            <span className="text-muted text-xs">Trigger Condition:</span>
                          </div>
                          <div className="adj-condition">
                            {renderConditionNode(adj.when)}
                          </div>
                          <div className="adj-actions">
                            <label className="text-xs text-muted">Triggered Actions:</label>
                            <div className="action-tags">
                              {(adj.actions || []).map((act: any, i: number) => (
                                <span key={i} className="action-tag">
                                  {act.type === "CLOSE_LEG"
                                    ? `Close Leg #${act.legId}`
                                    : act.type === "OPEN_LEG"
                                    ? `Open Leg #${act.legId} (${act.side} ${act.instrument?.optionType})`
                                    : act.type}
                                </span>
                              ))}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
            </div>
          )}

          {/* Bounds & Guardrails */}
          {definition.bounds && (
            <div className="section-block bounds-block">
              <div className="block-title">
                <span className="step-badge bounds">BOUNDS</span>
                <h4>Session Bounds & Risk Caps</h4>
              </div>
              <div className="bounds-grid">
                <div className="bound-item">
                  <label>Trading Window</label>
                  <span>
                    {definition.bounds.session?.entryTime || "09:15"} —{" "}
                    {definition.bounds.session?.exitTime || "15:14"}
                  </span>
                </div>
                <div className="bound-item">
                  <label>Max Trades / Day</label>
                  <span>{definition.bounds.maxTradesPerDay || "Unlimited"}</span>
                </div>
                <div className="bound-item">
                  <label>Day Stop Gain</label>
                  <span className="text-emerald">
                    {definition.bounds.dayStopGain?.value
                      ? `₹${definition.bounds.dayStopGain.value}`
                      : "—"}
                  </span>
                </div>
                <div className="bound-item">
                  <label>Day Stop Loss</label>
                  <span className="text-rose">
                    {definition.bounds.dayStopLoss?.value
                      ? `₹${definition.bounds.dayStopLoss.value}`
                      : "—"}
                  </span>
                </div>
                <div className="bound-item">
                  <label>Strategy Stop Loss</label>
                  <span className="text-rose">
                    {definition.bounds.strategyStopLoss?.value
                      ? `₹${definition.bounds.strategyStopLoss.value}`
                      : "—"}
                  </span>
                </div>
                <div className="bound-item">
                  <label>Stop Mode</label>
                  <span className="badge-pill">
                    {definition.riskPolicy?.stopMode || "STRATEGY_FIXED"}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
