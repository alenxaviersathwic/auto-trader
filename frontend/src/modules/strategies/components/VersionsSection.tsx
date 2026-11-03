import React, { useState } from "react";
import { GitCompare, X } from "lucide-react";
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
    <div className="sd-panel">
      <div className="sd-card">
        <div className="sd-card-header">
          <div>
            <span className="sd-card-title">Version History ({versions.length})</span>
            <p className="sd-card-sub">
              Immutable SHA-hashed strategy snapshots. Activate any version to roll back live execution logic.
            </p>
          </div>
          {versions.length >= 2 && (
            <button
              type="button"
              className="sd-ctrl-btn"
              onClick={() => {
                setCompareV1(versions[0].id);
                setCompareV2(versions[1].id);
                setShowDiff(true);
              }}
            >
              <GitCompare size={13} />
              <span>Compare Versions</span>
            </button>
          )}
        </div>

        {isLoading ? (
          <div className="sd-empty-inline">Loading version history…</div>
        ) : (
          <div className="table-scroll-container">
            <table className="data-table sd-compact-table">
              <thead>
                <tr>
                  <th>Version</th>
                  <th>Created At</th>
                  <th>Change Note</th>
                  <th>Content Hash</th>
                  <th>Status</th>
                  <th style={{ textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {versions.map((v) => {
                  const isActive = v.id === currentVersionId;
                  return (
                    <tr key={v.id}>
                      <td>
                        <span className="sd-tag sd-tag--cyan mono">v{v.versionNo}</span>
                      </td>
                      <td className="mono text-muted">
                        {v.createdAt ? new Date(v.createdAt).toLocaleString("en-IN") : "—"}
                      </td>
                      <td className="text-heading">
                        {v.changeNote || "Initial strategy version"}
                      </td>
                      <td className="mono text-muted" title={v.contentHash}>
                        {v.contentHash ? `${v.contentHash.substring(0, 12)}…` : "—"}
                      </td>
                      <td>
                        {isActive ? (
                          <span className="sd-tag sd-tag--green">ACTIVE</span>
                        ) : (
                          <span className="sd-tag">SNAPSHOT</span>
                        )}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {!isActive ? (
                          <button
                            type="button"
                            className="sd-ctrl-btn"
                            onClick={() => handleActivate(v.versionNo)}
                            disabled={activateMutation.isPending}
                          >
                            Activate
                          </button>
                        ) : (
                          <span className="micro text-muted mono">Current</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Compare Diff Modal */}
      {showDiff && (
        <div className="modal-backdrop" onClick={() => setShowDiff(false)}>
          <div
            className="modal"
            style={{ maxWidth: 920 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sd-card-header">
              <span className="sd-card-title">Compare Version Definitions</span>
              <button
                type="button"
                className="sd-ctrl-btn"
                onClick={() => setShowDiff(false)}
              >
                <X size={13} />
              </button>
            </div>

            <div className="sd-overview-cols" style={{ marginBottom: 12 }}>
              <div className="form-group">
                <label className="form-label">Version A</label>
                <select
                  className="select mono"
                  value={compareV1 || ""}
                  onChange={(e) => setCompareV1(Number(e.target.value))}
                >
                  {versions.map((v) => (
                    <option key={v.id} value={v.id}>
                      v{v.versionNo} — {v.changeNote || "Snapshot"} ({v.createdAt?.substring(0, 10)})
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Version B</label>
                <select
                  className="select mono"
                  value={compareV2 || ""}
                  onChange={(e) => setCompareV2(Number(e.target.value))}
                >
                  {versions.map((v) => (
                    <option key={v.id} value={v.id}>
                      v{v.versionNo} — {v.changeNote || "Snapshot"} ({v.createdAt?.substring(0, 10)})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="sd-overview-cols">
              <div className="dv-json-box">
                <div style={{ marginBottom: 6 }}>
                  <span className="sd-tag sd-tag--cyan mono">
                    v{getVersionById(compareV1)?.versionNo} Definition
                  </span>
                </div>
                <pre className="dv-json-pre" style={{ maxHeight: 360 }}>
                  {JSON.stringify(getVersionById(compareV1)?.definition, null, 2)}
                </pre>
              </div>
              <div className="dv-json-box">
                <div style={{ marginBottom: 6 }}>
                  <span className="sd-tag sd-tag--green mono">
                    v{getVersionById(compareV2)?.versionNo} Definition
                  </span>
                </div>
                <pre className="dv-json-pre" style={{ maxHeight: 360 }}>
                  {JSON.stringify(getVersionById(compareV2)?.definition, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
