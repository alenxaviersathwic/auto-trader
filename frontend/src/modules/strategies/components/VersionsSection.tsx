import React, { useState } from "react";
import { CheckCircle2, GitCompare } from "lucide-react";
import { StrategyVersion } from "../types/strategies.types";
import { useActivateStrategyVersion, useStrategyVersions } from "../hooks/useStrategies";

interface VersionsSectionProps {
  strategyId: number;
  currentVersionId?: number | null;
}

export const VersionsSection: React.FC<VersionsSectionProps> = ({
  strategyId,
  currentVersionId,
}) => {
  const { data: versionsData, isLoading } = useStrategyVersions(strategyId);
  const activateMutation = useActivateStrategyVersion();

  const [compareV1, setCompareV1] = useState<number | null>(null);
  const [compareV2, setCompareV2] = useState<number | null>(null);
  const [showDiff, setShowDiff] = useState(false);

  const versions: StrategyVersion[] = versionsData?.list || [];

  const handleActivate = (versionNo: number) => {
    activateMutation.mutate({ id: strategyId, versionNo });
  };

  const getVersionById = (id: number | null) => {
    return versions.find((v) => v.id === id);
  };

  return (
    <div className="versions-section">
      <div className="flex justify-between items-center mb-4">
        <div>
          <h3 className="section-heading text-lg font-semibold text-primary">
            Version History & Audit Log
          </h3>
          <p className="text-xs text-muted">
            All strategy versions are strictly immutable. Activating a version changes the current execution definition.
          </p>
        </div>
        {versions.length >= 2 && (
          <button
            type="button"
            className="btn-outline flex items-center gap-1.5 text-xs"
            onClick={() => {
              if (versions.length >= 2) {
                setCompareV1(versions[0].id);
                setCompareV2(versions[1].id);
                setShowDiff(true);
              }
            }}
          >
            <GitCompare size={14} />
            <span>Compare Definitions</span>
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="p-4 text-center text-muted">Loading version history...</div>
      ) : (
        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                <th>Version</th>
                <th>Created At</th>
                <th>Change Note</th>
                <th>Content Hash</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((v) => {
                const isActive = v.id === currentVersionId;
                return (
                  <tr key={v.id} className={isActive ? "active-version-row" : ""}>
                    <td className="font-mono font-bold text-cyan">
                      v{v.versionNo}
                    </td>
                    <td className="text-xs text-muted">
                      {v.createdAt ? new Date(v.createdAt).toLocaleString() : "—"}
                    </td>
                    <td className="text-sm text-secondary">
                      {v.changeNote || "Initial version or update"}
                    </td>
                    <td className="font-mono text-xs text-muted" title={v.contentHash}>
                      {v.contentHash ? `${v.contentHash.substring(0, 8)}...` : "—"}
                    </td>
                    <td>
                      {isActive ? (
                        <span className="badge-pill bg-emerald flex items-center gap-1">
                          <CheckCircle2 size={12} />
                          Active
                        </span>
                      ) : (
                        <span className="text-xs text-muted">Archived</span>
                      )}
                    </td>
                    <td>
                      {!isActive && (
                        <button
                          type="button"
                          className="btn-outline text-xs"
                          onClick={() => handleActivate(v.versionNo)}
                          disabled={activateMutation.isPending}
                        >
                          Activate
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Compare Diff Modal */}
      {showDiff && (
        <div className="modal-backdrop">
          <div className="modal">
            <div className="modal-header">
              <h3 className="modal-title font-semibold text-primary flex items-center gap-2">
                <GitCompare size={16} />
                Compare Version Definitions
              </h3>
              <button
                type="button"
                className="btn-modal-close"
                onClick={() => setShowDiff(false)}
              >
                ✕
              </button>
            </div>
            <div className="p-4">
              <div className="flex gap-4 mb-4">
                <div className="flex-1">
                  <label className="text-xs text-muted block mb-1">Version A</label>
                  <select
                    className="select w-full"
                    value={compareV1 || ""}
                    onChange={(e) => setCompareV1(Number(e.target.value))}
                  >
                    {versions.map((v) => (
                      <option key={v.id} value={v.id}>
                        v{v.versionNo} ({v.createdAt?.substring(0, 10)})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex-1">
                  <label className="text-xs text-muted block mb-1">Version B</label>
                  <select
                    className="select w-full"
                    value={compareV2 || ""}
                    onChange={(e) => setCompareV2(Number(e.target.value))}
                  >
                    {versions.map((v) => (
                      <option key={v.id} value={v.id}>
                        v{v.versionNo} ({v.createdAt?.substring(0, 10)})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="card-surface p-3 border border-subtle rounded">
                  <span className="text-xs text-cyan font-mono block mb-2">
                    Version {getVersionById(compareV1)?.versionNo} Definition:
                  </span>
                  <pre className="text-xs font-mono max-h-96 overflow-y-auto text-secondary">
                    {JSON.stringify(getVersionById(compareV1)?.definition, null, 2)}
                  </pre>
                </div>
                <div className="card-surface p-3 border border-subtle rounded">
                  <span className="text-xs text-emerald font-mono block mb-2">
                    Version {getVersionById(compareV2)?.versionNo} Definition:
                  </span>
                  <pre className="text-xs font-mono max-h-96 overflow-y-auto text-secondary">
                    {JSON.stringify(getVersionById(compareV2)?.definition, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
