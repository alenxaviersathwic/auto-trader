import React from "react";

export const BACKTEST_INDEX_CODES = ["NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY", "MIDCPNIFTY"] as const;

interface Props {
  selected: string[];
  onToggle: (code: string) => void;
}

/** Chip-style multi-select for the index underlyings a backtest run should cover. */
export const IndexMultiSelect: React.FC<Props> = ({ selected, onToggle }) => {
  const selectedSet = new Set(selected);
  return (
    <div className="backtest-index-select">
      {BACKTEST_INDEX_CODES.map((code) => {
        const active = selectedSet.has(code);
        return (
          <button
            type="button"
            key={code}
            onClick={() => onToggle(code)}
            className={`badge ticker backtest-index-chip ${active ? "backtest-index-chip--selected" : ""}`}
          >
            {code}
          </button>
        );
      })}
    </div>
  );
};
