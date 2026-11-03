import React, { useState } from "react";
import { Copy, Check } from "lucide-react";

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
  const [copied, setCopied] = useState(false);

  if (!definition) {
    return (
      <div className="sd-card">
        <div className="sd-empty-inline">No definition available for this version.</div>
      </div>
    );
  }

  const defFormat = definition.format || format;

  const handleCopyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(definition, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  // Format operand into clean readable string
  const formatOperand = (op: any): string => {
    if (!op) return "—";
    if (op.const !== undefined) {
      if (op.type === "TIME") return String(op.const);
      if (Array.isArray(op.const)) return `[${op.const.join(", ")}]`;
      return String(op.const);
    }
    if (op.param !== undefined) {
      return `$${op.param}`;
    }
    const source = op.source;
    if (source === "PRICE") {
      const tf = op.timeframe ? ` (${op.timeframe})` : "";
      const bar = op.bar && op.bar !== "CURRENT" ? ` [${op.bar}]` : "";
      return `Price.${op.field}${tf}${bar}`;
    }
    if (source === "DAY") {
      return `${op.day}.${op.field}`;
    }
    if (source === "INDICATOR") {
      const params =
        op.params && Object.keys(op.params).length > 0
          ? `(${Object.entries(op.params)
              .map(([k, v]) => `${k}=${v}`)
              .join(", ")})`
          : "";
      const inst = op.instance ? `[${op.instance}]` : "";
      const out = op.output && op.output !== "value" ? `.${op.output}` : "";
      const tf = op.timeframe ? ` (${op.timeframe})` : "";
      return `${op.code}${inst}${out}${params}${tf}`;
    }
    if (source === "TIME") {
      return op.field || "TimeOfDay";
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

  const formatOperator = (op: string): string => {
    switch (op) {
      case "IS_ABOVE":
        return ">";
      case "IS_ABOVE_OR_EQUAL":
        return "≥";
      case "IS_BELOW":
        return "<";
      case "IS_BELOW_OR_EQUAL":
        return "≤";
      case "EQUALS":
        return "=";
      case "NOT_EQUALS":
        return "≠";
      case "CROSSES_ABOVE":
        return "crosses above";
      case "CROSSES_BELOW":
        return "crosses below";
      case "IN":
        return "in";
      case "NOT_IN":
        return "not in";
      case "BETWEEN":
        return "between";
      default:
        return op;
    }
  };

  const renderConditionNode = (node: any, depth: number = 0): React.ReactNode => {
    if (!node) {
      return <span className="text-muted mono">Unconditional (Always Trigger)</span>;
    }

    if (node.op) {
      const items = node.items || [];
      const joinLabel = node.op === "ALL" ? "AND" : node.op === "ANY" ? "OR" : "NOT";

      if (items.length === 0) {
        return <span className="text-muted mono">None</span>;
      }

      return (
        <div className={`dv-cond-group ${depth > 0 ? "is-nested" : ""}`}>
          <div className="dv-cond-items">
            {items.map((sub: any, i: number) => (
              <React.Fragment key={i}>
                <div className="dv-cond-row">{renderConditionNode(sub, depth + 1)}</div>
                {i < items.length - 1 && (
                  <div className="dv-cond-join">
                    <span className={`dv-join-tag mono ${node.op === "ANY" ? "is-or" : "is-and"}`}>
                      {joinLabel}
                    </span>
                  </div>
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
      );
    }

    if (node.left && node.operator) {
      return (
        <div className="dv-cond-line">
          <span className="dv-expr-left mono">{formatOperand(node.left)}</span>
          <span className="dv-expr-op mono">{formatOperator(node.operator)}</span>
          <span className="dv-expr-right mono">{formatOperand(node.right)}</span>
        </div>
      );
    }

    return <pre className="dv-raw-inline">{JSON.stringify(node, null, 2)}</pre>;
  };

  return (
    <div className="sd-panel">
      {/* Compact Header Toolbar */}
      <div className="sd-card">
        <div className="sd-card-header" style={{ marginBottom: 0, borderBottom: "none", paddingBottom: 0 }}>
          <div className="sd-topbar-left">
            <span className="sd-card-title">Rule Definition</span>
            <span className="sd-tag sd-tag--cyan mono">{defFormat}</span>
            <span className="sd-tag mono">Schema v{definition.schemaVersion || 2}</span>
          </div>

          <div className="sd-topbar-right">
            <button type="button" className="sd-ctrl-btn" onClick={handleCopyJson}>
              {copied ? <Check size={12} className="text-green" /> : <Copy size={12} />}
              <span>{copied ? "Copied" : "Copy JSON"}</span>
            </button>

            <div className="sd-seg-group">
              <button
                type="button"
                className={`sd-seg-btn ${viewMode === "structured" ? "active" : ""}`}
                onClick={() => setViewMode("structured")}
              >
                Structured
              </button>
              <button
                type="button"
                className={`sd-seg-btn ${viewMode === "json" ? "active" : ""}`}
                onClick={() => setViewMode("json")}
              >
                Raw JSON
              </button>
            </div>
          </div>
        </div>
      </div>

      {viewMode === "json" ? (
        <div className="sd-card">
          <div className="dv-json-box">
            <pre className="dv-json-pre">{JSON.stringify(definition, null, 2)}</pre>
          </div>
        </div>
      ) : defFormat === "SUMMARY" ? (
        <div className="sd-card">
          <div className="sd-card-header">
            <span className="sd-card-title">Descriptive Summary Specification</span>
          </div>
          <div className="sd-spec-list">
            <div className="sd-spec-row">
              <span className="sd-spec-key">Entry Label</span>
              <span className="sd-spec-val">{definition.summary?.entryLabel || "—"}</span>
            </div>
            <div className="sd-spec-row">
              <span className="sd-spec-key">Target R:R</span>
              <span className="sd-spec-val mono text-green">
                {definition.summary?.targetRr ? `${definition.summary.targetRr} : 1` : "—"}
              </span>
            </div>
            <div className="sd-spec-row">
              <span className="sd-spec-key">Max Risk %</span>
              <span className="sd-spec-val mono text-red">
                {definition.summary?.maxRiskPct ? `${definition.summary.maxRiskPct}%` : "—"}
              </span>
            </div>
            <div className="sd-spec-row">
              <span className="sd-spec-key">Required Indicators</span>
              <span className="sd-spec-val mono text-cyan">
                {(definition.summary?.indicators || []).join(", ") || "—"}
              </span>
            </div>
          </div>
        </div>
      ) : defFormat === "EVALUATOR" ? (
        <div className="sd-card">
          <div className="sd-card-header">
            <span className="sd-card-title">Code-Backed Evaluator</span>
            <span className="sd-tag sd-tag--cyan mono">{definition.evaluator}</span>
          </div>
          {Object.keys(definition.parameters || {}).length > 0 && (
            <div className="table-scroll-container">
              <table className="data-table sd-compact-table">
                <thead>
                  <tr>
                    <th>Parameter Key</th>
                    <th>Configured Value</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(definition.parameters || {}).map(([key, val]: [string, any]) => (
                    <tr key={key}>
                      <td className="mono text-cyan">{key}</td>
                      <td className="mono text-green">
                        {typeof val === "object" ? JSON.stringify(val) : String(val)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <div className="sd-panel">
          {/* Case Selector Strip */}
          {Array.isArray(definition.cases) && definition.cases.length > 1 && (
            <div className="sd-tabs-nav" style={{ borderBottom: "none" }}>
              {definition.cases.map((c: any, idx: number) => {
                const isActive = activeCaseIdx === idx;
                const bias = c.bias || "DYNAMIC";
                return (
                  <button
                    key={c.key || idx}
                    type="button"
                    className={`sd-nav-tab ${isActive ? "active" : ""}`}
                    onClick={() => setActiveCaseIdx(idx)}
                  >
                    <span>Case #{c.key ?? idx + 1}</span>
                    <span
                      className={`sd-tag ${
                        bias === "BULLISH"
                          ? "sd-tag--green"
                          : bias === "BEARISH"
                          ? "sd-tag--red"
                          : "sd-tag--cyan"
                      }`}
                    >
                      {bias}
                    </span>
                  </button>
                );
              })}
            </div>
          )}

          {definition.cases && definition.cases[activeCaseIdx] && (
            <div className="sd-panel">
              {/* Entry & Exit Side-by-Side */}
              <div className="sd-overview-cols">
                <div className="sd-card">
                  <div className="sd-card-header">
                    <span className="sd-card-title">Entry Condition</span>
                    <span className="sd-tag sd-tag--green">ENTRY WHEN</span>
                  </div>
                  <div className="dv-tree-surface">
                    {renderConditionNode(definition.cases[activeCaseIdx].entry?.when)}
                  </div>
                </div>

                <div className="sd-card">
                  <div className="sd-card-header">
                    <span className="sd-card-title">Exit Condition</span>
                    <span className="sd-tag sd-tag--red">EXIT WHEN</span>
                  </div>
                  <div className="dv-tree-surface">
                    {renderConditionNode(definition.cases[activeCaseIdx].exit?.when)}
                  </div>
                </div>
              </div>

              {/* Legs Table */}
              <div className="sd-card">
                <div className="sd-card-header">
                  <span className="sd-card-title">
                    Execution Legs ({(definition.cases[activeCaseIdx].entry?.legs || []).length})
                  </span>
                  <span className="sd-tag mono">
                    CASE #{definition.cases[activeCaseIdx].key ?? activeCaseIdx + 1} ·{" "}
                    {definition.cases[activeCaseIdx].bias || "DYNAMIC"}
                  </span>
                </div>
                {(definition.cases[activeCaseIdx].entry?.legs || []).length === 0 ? (
                  <div className="sd-empty-inline">No option legs configured for this case.</div>
                ) : (
                  <div className="table-scroll-container">
                    <table className="data-table sd-compact-table">
                      <thead>
                        <tr>
                          <th>Leg</th>
                          <th>Side</th>
                          <th>Option</th>
                          <th>Expiry</th>
                          <th>Strike Selector</th>
                          <th>Qty</th>
                          <th>Stop Loss</th>
                          <th>Target</th>
                          <th>Trailing Stop</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(definition.cases[activeCaseIdx].entry?.legs || []).map(
                          (leg: any, idx: number) => (
                            <tr key={leg.legId || idx}>
                              <td className="mono text-heading">#{leg.legId || idx + 1}</td>
                              <td>
                                <span
                                  className={`sd-tag ${
                                    leg.side === "BUY" ? "sd-tag--green" : "sd-tag--red"
                                  }`}
                                >
                                  {leg.side}
                                </span>
                              </td>
                              <td className="mono">{leg.instrument?.optionType || "CE/PE"}</td>
                              <td className="mono">
                                {leg.instrument?.expiry?.cycle || "WEEKLY"} (
                                {leg.instrument?.expiry?.index || 1})
                              </td>
                              <td className="mono text-cyan">
                                {leg.instrument?.strike?.selector === "ATM_OFFSET"
                                  ? `ATM ${
                                      leg.instrument.strike.steps > 0
                                        ? `+${leg.instrument.strike.steps}`
                                        : leg.instrument.strike.steps === 0
                                        ? "(0)"
                                        : leg.instrument.strike.steps
                                    }`
                                  : leg.instrument?.strike?.selector === "DELTA"
                                  ? `Delta ${leg.instrument.strike.delta}`
                                  : leg.instrument?.strike?.selector === "PREMIUM"
                                  ? `₹${leg.instrument.strike.premium}`
                                  : JSON.stringify(leg.instrument?.strike || "ATM")}
                              </td>
                              <td className="mono">
                                {leg.quantity?.value ?? 1} {leg.quantity?.unit || "LOT"}
                              </td>
                              <td className="mono text-red">
                                {leg.stopLoss
                                  ? `-${leg.stopLoss.value}${
                                      leg.stopLoss.type === "PERCENT" ? "%" : "pt"
                                    }`
                                  : "—"}
                              </td>
                              <td className="mono text-green">
                                {leg.target
                                  ? `+${leg.target.value}${
                                      leg.target.type === "PERCENT" ? "%" : "pt"
                                    }`
                                  : "—"}
                              </td>
                              <td className="mono text-cyan">
                                {leg.stopLoss?.trail
                                  ? `+${leg.stopLoss.trail.adjustValue} / +${leg.stopLoss.trail.trailingValue}`
                                  : "—"}
                              </td>
                            </tr>
                          )
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Adjustments */}
              {Array.isArray(definition.cases[activeCaseIdx].adjustments) &&
                definition.cases[activeCaseIdx].adjustments.length > 0 && (
                  <div className="sd-card">
                    <div className="sd-card-header">
                      <span className="sd-card-title">Intra-Session Adjustments</span>
                      <span className="sd-tag sd-tag--amber">
                        {definition.cases[activeCaseIdx].adjustments.length} RULES
                      </span>
                    </div>
                    <div className="sd-panel">
                      {definition.cases[activeCaseIdx].adjustments.map((adj: any, idx: number) => (
                        <div key={adj.key || idx} className="dv-tree-surface">
                          <div className="sd-topbar-left" style={{ marginBottom: 8 }}>
                            <span className="sd-tag sd-tag--amber mono">
                              #{adj.key || idx + 1}
                            </span>
                            {(adj.actions || []).map((act: any, i: number) => (
                              <span key={i} className="sd-tag sd-tag--cyan mono">
                                {act.type === "CLOSE_LEG"
                                  ? `Close Leg #${act.legId}`
                                  : act.type === "OPEN_LEG"
                                  ? `Open Leg #${act.legId} (${act.side} ${act.instrument?.optionType})`
                                  : act.type}
                              </span>
                            ))}
                          </div>
                          {renderConditionNode(adj.when)}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
