import React, { useState } from "react";
import { useParams, useNavigate } from "@tanstack/react-router";
import { ArrowLeft, Save } from "lucide-react";
import { useCreateStrategy, useStrategyDetail, useUpdateStrategy } from "../hooks/useStrategies";
import { DefinitionEditor } from "../components/DefinitionEditor";

export const StrategyEditorPage: React.FC = () => {
  const { id } = useParams({ strict: false }) as { id?: string };
  const strategyId = id ? Number(id) : null;
  const isEditing = Boolean(strategyId);
  const navigate = useNavigate();

  const { data: existingStrategy, isLoading } = useStrategyDetail(strategyId || 0);
  const createMutation = useCreateStrategy();
  const updateMutation = useUpdateStrategy();

  const [formData, setFormData] = useState({
    code: "",
    name: "",
    description: "",
    category: "MOMENTUM",
    structure: "SINGLE_LONG",
    bias: "BULLISH",
    optionSide: "CALL",
    markets: ["NIFTY"],
    underlyingTypes: ["INDEX"],
    exchange: "NSE",
    tradingModes: ["INTRADAY"],
    executionModes: ["PAPER", "LIVE"],
    timeframe: "5m",
    definitionFormat: "RULE_TREE",
  });

  const [definition, setDefinition] = useState<Record<string, any>>({
    schemaVersion: 2,
    format: "RULE_TREE",
    isParallelCases: false,
    cases: [
      {
        key: "0",
        bias: "BULLISH",
        entry: {
          when: {
            left: { source: "PRICE", field: "close", bar: "CURRENT", timeframe: "5m" },
            operator: "IS_ABOVE",
            right: { source: "INDICATOR", code: "VWAP", output: "currentDay", params: null },
          },
          legs: [
            {
              legId: "1",
              side: "BUY",
              instrument: {
                kind: "OPTION",
                optionType: "CE",
                expiry: { cycle: "WEEKLY", index: 1 },
                strike: { selector: "ATM_OFFSET", steps: 0 },
              },
              quantity: { unit: "LOT", value: 1 },
              stopLoss: { type: "PERCENT", value: 30, basis: "ENTRY_PREMIUM" },
              target: { type: "PERCENT", value: 60, basis: "ENTRY_PREMIUM" },
            },
          ],
        },
        exit: {
          when: {
            left: { source: "TIME", field: "timeOfDay" },
            operator: "EQUALS",
            right: { const: "15:14:00", type: "TIME" },
          },
        },
        adjustments: [],
      },
    ],
    bounds: {
      session: { entryTime: "09:15", exitTime: "15:14" },
      maxTradesPerDay: 5,
    },
    riskPolicy: { stopMode: "STRATEGY_FIXED" },
    parameters: {},
    extras: {},
  });

  const [initialized, setInitialized] = useState(false);

  if (isEditing && existingStrategy && !initialized) {
    setFormData({
      code: existingStrategy.code,
      name: existingStrategy.name,
      description: existingStrategy.description || "",
      category: existingStrategy.category,
      structure: existingStrategy.structure || "SINGLE_LONG",
      bias: existingStrategy.bias || "DYNAMIC",
      optionSide: existingStrategy.optionSide || "BOTH",
      markets: existingStrategy.markets || ["NIFTY"],
      underlyingTypes: existingStrategy.underlyingTypes || ["INDEX"],
      exchange: existingStrategy.exchange || "NSE",
      tradingModes: existingStrategy.tradingModes || ["INTRADAY"],
      executionModes: existingStrategy.executionModes || ["PAPER"],
      timeframe: existingStrategy.timeframe || "5m",
      definitionFormat: existingStrategy.definitionFormat || "RULE_TREE",
    });
    if (existingStrategy.currentVersion?.definition) {
      setDefinition(existingStrategy.currentVersion.definition);
    }
    setInitialized(true);
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (isEditing && strategyId) {
      updateMutation.mutate(
        {
          id: strategyId,
          payload: {
            ...formData,
            definition,
            changeNote: "Updated definition and metadata",
          },
        },
        {
          onSuccess: () => {
            navigate({ to: `/strategies/${strategyId}` as any });
          },
        }
      );
    } else {
      createMutation.mutate(
        {
          ...formData,
          definition,
          changeNote: "Initial creation",
        },
        {
          onSuccess: (created) => {
            navigate({ to: `/strategies/${created.id}` as any });
          },
        }
      );
    }
  };

  if (isEditing && isLoading) {
    return <div className="p-8 text-center text-muted">Loading strategy for edit...</div>;
  }

  return (
    <div className="strategy-editor-page module-page">
      <button
        type="button"
        className="btn-back flex items-center gap-1.5 text-xs text-muted hover:text-primary mb-3"
        onClick={() => navigate({ to: isEditing ? (`/strategies/${strategyId}` as any) : ("/strategies" as any) })}
      >
        <ArrowLeft size={14} />
        <span>Back</span>
      </button>

      <form onSubmit={handleSubmit}>
        <div className="flex justify-between items-center mb-4">
          <div>
            <h1 className="text-xl font-bold text-primary">
              {isEditing ? `Edit Strategy: ${existingStrategy?.name}` : "Create New Option Strategy"}
            </h1>
            <p className="text-xs text-muted">
              Define instrument metadata, risk profile, and rule tree logic.
            </p>
          </div>
          <button
            type="submit"
            className="btn-kite-primary text-xs flex items-center gap-1.5"
            disabled={createMutation.isPending || updateMutation.isPending}
          >
            <Save size={14} />
            <span>
              {createMutation.isPending || updateMutation.isPending
                ? "Saving..."
                : isEditing
                ? "Save Changes (Version N+1)"
                : "Create Strategy"}
            </span>
          </button>
        </div>

        {/* Metadata Grid */}
        <div className="card-surface p-4 border border-subtle rounded-lg mb-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="form-group">
            <label className="text-xs text-muted block mb-1">Strategy Code</label>
            <input
              type="text"
              className="filter-input w-full text-xs font-mono"
              placeholder="e.g. nifty_momentum_buying_v2"
              value={formData.code}
              onChange={(e) => setFormData({ ...formData, code: e.target.value })}
              disabled={isEditing}
              required
            />
          </div>
          <div className="form-group md:col-span-2">
            <label className="text-xs text-muted block mb-1">Display Name</label>
            <input
              type="text"
              className="filter-input w-full text-xs"
              placeholder="e.g. Nifty Intraday Trend Surge"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />
          </div>

          <div className="form-group md:col-span-3">
            <label className="text-xs text-muted block mb-1">Description</label>
            <textarea
              className="filter-input w-full text-xs"
              rows={2}
              placeholder="Describe the thesis, setup, and risk approach..."
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label className="text-xs text-muted block mb-1">Category</label>
            <select
              className="filter-select w-full text-xs"
              value={formData.category}
              onChange={(e) => setFormData({ ...formData, category: e.target.value })}
            >
              <option value="MOMENTUM">MOMENTUM</option>
              <option value="BREAKOUT">BREAKOUT</option>
              <option value="TREND">TREND</option>
              <option value="PREMIUM_SELLING">PREMIUM_SELLING</option>
              <option value="VWAP">VWAP</option>
              <option value="VOLATILITY">VOLATILITY</option>
              <option value="OTHER">OTHER</option>
            </select>
          </div>

          <div className="form-group">
            <label className="text-xs text-muted block mb-1">Structure</label>
            <select
              className="filter-select w-full text-xs"
              value={formData.structure}
              onChange={(e) => setFormData({ ...formData, structure: e.target.value })}
            >
              <option value="SINGLE_LONG">SINGLE_LONG</option>
              <option value="BULL_PUT_SPREAD">BULL_PUT_SPREAD</option>
              <option value="BEAR_CALL_SPREAD">BEAR_CALL_SPREAD</option>
              <option value="IRON_CONDOR">IRON_CONDOR</option>
              <option value="SHORT_STRANGLE">SHORT_STRANGLE</option>
              <option value="CUSTOM_MULTI_LEG">CUSTOM_MULTI_LEG</option>
            </select>
          </div>

          <div className="form-group">
            <label className="text-xs text-muted block mb-1">Directional Bias</label>
            <select
              className="filter-select w-full text-xs"
              value={formData.bias}
              onChange={(e) => setFormData({ ...formData, bias: e.target.value })}
            >
              <option value="BULLISH">BULLISH</option>
              <option value="BEARISH">BEARISH</option>
              <option value="NEUTRAL">NEUTRAL</option>
              <option value="DYNAMIC">DYNAMIC</option>
            </select>
          </div>

          <div className="form-group">
            <label className="text-xs text-muted block mb-1">Markets (Comma-separated)</label>
            <input
              type="text"
              className="filter-input w-full text-xs"
              placeholder="NIFTY, BANKNIFTY"
              value={formData.markets.join(", ")}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  markets: e.target.value.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean),
                })
              }
            />
          </div>

          <div className="form-group">
            <label className="text-xs text-muted block mb-1">Exchange</label>
            <select
              className="filter-select w-full text-xs"
              value={formData.exchange}
              onChange={(e) => setFormData({ ...formData, exchange: e.target.value })}
            >
              <option value="NSE">NSE</option>
              <option value="BSE">BSE</option>
              <option value="MCX">MCX</option>
            </select>
          </div>

          <div className="form-group">
            <label className="text-xs text-muted block mb-1">Timeframe</label>
            <input
              type="text"
              className="filter-input w-full text-xs font-mono"
              placeholder="3m, 5m, 15m"
              value={formData.timeframe}
              onChange={(e) => setFormData({ ...formData, timeframe: e.target.value })}
            />
          </div>
        </div>

        {/* Definition Editor Card */}
        <div className="card-surface p-4 border border-subtle rounded-lg">
          <h3 className="font-semibold text-primary mb-2 text-sm">Strategy Definition Schema</h3>
          <DefinitionEditor
            initialDefinition={definition}
            onChange={(d) => setDefinition(d)}
            currentVersionNo={existingStrategy?.currentVersion?.versionNo || 1}
          />
        </div>
      </form>
    </div>
  );
};
