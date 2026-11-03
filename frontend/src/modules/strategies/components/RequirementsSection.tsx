import React from "react";
import { useStrategyRequirements } from "../hooks/useStrategies";

interface RequirementsSectionProps {
  strategyId: number;
  versionNo: number;
}

export const RequirementsSection: React.FC<RequirementsSectionProps> = ({
  strategyId,
  versionNo,
}) => {
  const { data, isLoading } = useStrategyRequirements(strategyId, versionNo);

  if (isLoading) {
    return (
      <div className="sd-card">
        <div className="sd-empty-inline">Analyzing required market feeds &amp; indicators…</div>
      </div>
    );
  }

  const operands = (data as any)?.requirements || (data as any)?.operands || [];

  return (
    <div className="sd-panel">
      <div className="sd-card">
        <div className="sd-card-header">
          <div>
            <span className="sd-card-title">
              Pre-Computation Requirements ({operands.length})
            </span>
            <p className="sd-card-sub">
              Market data feeds, technical indicators, and context inputs required for v{versionNo}.
            </p>
          </div>
          <span className="sd-tag sd-tag--cyan mono">v{versionNo}</span>
        </div>

        {operands.length === 0 ? (
          <div className="sd-empty-inline">
            No external indicator or price feed dependencies detected for this version.
          </div>
        ) : (
          <div className="table-scroll-container">
            <table className="data-table sd-compact-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Indicator / Code</th>
                  <th>Field / Output</th>
                  <th>Timeframe</th>
                  <th>Bar Reference</th>
                  <th>Parameters</th>
                </tr>
              </thead>
              <tbody>
                {operands.map((op: any, idx: number) => (
                  <tr key={idx}>
                    <td>
                      <span
                        className={`sd-tag mono ${
                          op.source === "INDICATOR"
                            ? "sd-tag--cyan"
                            : op.source === "PRICE"
                            ? "sd-tag--green"
                            : ""
                        }`}
                      >
                        {op.source}
                      </span>
                    </td>
                    <td className="mono text-heading">
                      {op.code || op.field || op.day || "—"}
                    </td>
                    <td className="mono text-secondary">
                      {op.output || op.field || "value"}
                    </td>
                    <td className="mono text-cyan">
                      {op.timeframe || <span className="text-muted">default</span>}
                    </td>
                    <td className="mono">{op.bar || "CURRENT"}</td>
                    <td className="mono text-muted">
                      {op.params ? JSON.stringify(op.params) : "default"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
