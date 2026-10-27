import React, { useState } from "react";
import { CheckCircle2, AlertCircle, Play, Code, Settings } from "lucide-react";
import { useValidateDefinition } from "../hooks/useStrategies";
import { ValidationResult } from "../types/strategies.types";

interface DefinitionEditorProps {
  initialDefinition: Record<string, any>;
  onChange: (def: Record<string, any>) => void;
  currentVersionNo?: number;
}

export const DefinitionEditor: React.FC<DefinitionEditorProps> = ({
  initialDefinition,
  onChange,
  currentVersionNo = 1,
}) => {
  const [editorMode, setEditorMode] = useState<"builder" | "json">("json");
  const [jsonText, setJsonText] = useState<string>(
    JSON.stringify(initialDefinition || {}, null, 2)
  );
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);

  const validateMutation = useValidateDefinition();

  const handleJsonChange = (val: string) => {
    setJsonText(val);
    try {
      const parsed = JSON.parse(val);
      setJsonError(null);
      onChange(parsed);
    } catch (err: any) {
      setJsonError(err.message || "Invalid JSON syntax");
    }
  };

  const handleValidate = () => {
    try {
      const parsed = JSON.parse(jsonText);
      validateMutation.mutate(parsed, {
        onSuccess: (res) => {
          setValidationResult(res);
        },
      });
    } catch (err: any) {
      setJsonError(err.message || "Cannot parse JSON to validate");
    }
  };

  return (
    <div className="definition-editor">
      <div className="editor-toolbar">
        <div className="editor-mode-toggle">
          <button
            type="button"
            className={`mode-btn ${editorMode === "json" ? "active" : ""}`}
            onClick={() => setEditorMode("json")}
          >
            <Code size={14} />
            <span>JSON Editor</span>
          </button>
          <button
            type="button"
            className={`mode-btn ${editorMode === "builder" ? "active" : ""}`}
            onClick={() => setEditorMode("builder")}
          >
            <Settings size={14} />
            <span>Builder Mode (Visual)</span>
          </button>
        </div>

        <div className="editor-actions">
          <span className="version-bump-hint">
            Saving definition creates version #{currentVersionNo + 1}
          </span>
          <button
            type="button"
            className="btn-validate"
            onClick={handleValidate}
            disabled={validateMutation.isPending}
          >
            <Play size={14} />
            <span>{validateMutation.isPending ? "Validating..." : "Validate Schema"}</span>
          </button>
        </div>
      </div>

      {jsonError && (
        <div className="validation-banner error">
          <AlertCircle size={16} />
          <span>JSON Syntax Error: {jsonError}</span>
        </div>
      )}

      {validationResult && (
        <div
          className={`validation-banner ${validationResult.valid ? "success" : "error"}`}
        >
          {validationResult.valid ? (
            <CheckCircle2 size={16} className="text-emerald" />
          ) : (
            <AlertCircle size={16} className="text-rose" />
          )}
          <div className="validation-msg">
            <strong>
              {validationResult.valid
                ? `Definition is valid! Executable: ${validationResult.executable ? "YES" : "NO"}`
                : "Validation issues detected:"}
            </strong>
            {validationResult.issues && validationResult.issues.length > 0 && (
              <ul className="issue-list">
                {validationResult.issues.map((iss, i) => (
                  <li key={i} className={`issue-item ${iss.severity.toLowerCase()}`}>
                    <span className="issue-path font-mono">{iss.path}:</span>{" "}
                    <span className="issue-text">{iss.message}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {editorMode === "json" ? (
        <div className="code-editor-area">
          <textarea
            className="json-textarea font-mono"
            value={jsonText}
            onChange={(e) => handleJsonChange(e.target.value)}
            rows={22}
            spellCheck={false}
          />
        </div>
      ) : (
        <div className="visual-builder-placeholder card-surface p-4">
          <div className="builder-header mb-4">
            <h4 className="font-semibold text-primary">Visual Rule Tree Configurator</h4>
            <p className="text-xs text-muted">
              Configure bounds and risk policies directly, or switch to JSON mode for arbitrary nested conditions.
            </p>
          </div>
          <div className="builder-form-grid">
            <div className="form-group">
              <label>Definition Format</label>
              <select
                className="select w-full"
                value={initialDefinition.format || "RULE_TREE"}
                onChange={(e) => {
                  const updated = { ...initialDefinition, format: e.target.value };
                  handleJsonChange(JSON.stringify(updated, null, 2));
                }}
              >
                <option value="RULE_TREE">RULE_TREE (Executable Condition Tree)</option>
                <option value="EVALUATOR">EVALUATOR (Code-Backed Evaluator)</option>
                <option value="SUMMARY">SUMMARY (Descriptive Specification)</option>
              </select>
            </div>
            <div className="form-group">
              <label>Stop Mode</label>
              <select
                className="select w-full"
                value={initialDefinition.riskPolicy?.stopMode || "STRATEGY_FIXED"}
                onChange={(e) => {
                  const updated = {
                    ...initialDefinition,
                    riskPolicy: {
                      ...(initialDefinition.riskPolicy || {}),
                      stopMode: e.target.value,
                    },
                  };
                  handleJsonChange(JSON.stringify(updated, null, 2));
                }}
              >
                <option value="STRATEGY_FIXED">STRATEGY_FIXED (Legacy fixed leg stops)</option>
                <option value="ADVISORY">ADVISORY (Session graph structural stops)</option>
                <option value="EVALUATOR_OWNED">EVALUATOR_OWNED (Code evaluator decides)</option>
              </select>
            </div>
            <div className="form-group">
              <label>Entry Session Time</label>
              <input
                type="text"
                className="input w-full"
                placeholder="09:15"
                defaultValue={initialDefinition.bounds?.session?.entryTime || "09:15"}
                onBlur={(e) => {
                  const updated = {
                    ...initialDefinition,
                    bounds: {
                      ...(initialDefinition.bounds || {}),
                      session: {
                        ...(initialDefinition.bounds?.session || {}),
                        entryTime: e.target.value,
                      },
                    },
                  };
                  handleJsonChange(JSON.stringify(updated, null, 2));
                }}
              />
            </div>
            <div className="form-group">
              <label>Exit Session Time</label>
              <input
                type="text"
                className="input w-full"
                placeholder="15:14"
                defaultValue={initialDefinition.bounds?.session?.exitTime || "15:14"}
                onBlur={(e) => {
                  const updated = {
                    ...initialDefinition,
                    bounds: {
                      ...(initialDefinition.bounds || {}),
                      session: {
                        ...(initialDefinition.bounds?.session || {}),
                        exitTime: e.target.value,
                      },
                    },
                  };
                  handleJsonChange(JSON.stringify(updated, null, 2));
                }}
              />
            </div>
          </div>
          <div className="text-center mt-6">
            <button
              type="button"
              className="btn-outline text-xs"
              onClick={() => setEditorMode("json")}
            >
              Switch to JSON Editor to edit Legs & Condition Trees
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
