import React from "react";
import { ListChecks, Info } from "lucide-react";
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
    return <div className="p-4 text-center text-muted">Analyzing required operands...</div>;
  }

  const operands = (data as any)?.requirements || (data as any)?.operands || [];

  return (
    <div className="requirements-section">
      <div className="mb-4">
        <h3 className="section-heading text-lg font-semibold text-primary flex items-center gap-2">
          <ListChecks size={20} className="text-cyan" />
          Pre-Computation Requirements (v{versionNo})
        </h3>
        <p className="text-xs text-muted">
          All external market data feeds, indicator calculations, and contextual inputs required before this strategy can evaluate.
        </p>
      </div>

      {operands.length === 0 ? (
        <div className="card-surface p-4 text-center text-muted">
          <Info size={18} className="mx-auto mb-1 text-cyan" />
          <p className="text-xs">No external indicator or price requirements detected for this version.</p>
        </div>
      ) : (
        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Indicator / Code</th>
                <th>Field / Output</th>
                <th>Timeframe</th>
                <th>Bar</th>
                <th>Configured Parameters</th>
              </tr>
            </thead>
            <tbody>
              {operands.map((op: any, idx: number) => (
                <tr key={idx}>
                  <td>
                    <span className="badge-pill bg-elevated font-mono">
                      {op.source}
                    </span>
                  </td>
                  <td className="font-mono text-cyan font-semibold">
                    {op.code || op.field || op.day || "—"}
                  </td>
                  <td>
                    <span className="badge-pill bg-surface text-secondary">
                      {op.output || op.field || "value"}
                    </span>
                  </td>
                  <td className="font-mono text-xs">
                    {op.timeframe || <span className="text-muted">engine default</span>}
                  </td>
                  <td className="text-xs">
                    {op.bar || "CURRENT"}
                  </td>
                  <td className="font-mono text-xs text-muted">
                    {op.params ? JSON.stringify(op.params) : "default"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
