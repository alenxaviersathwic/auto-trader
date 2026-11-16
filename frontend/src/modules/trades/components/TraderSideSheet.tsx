import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  ClipboardCheck,
  Cpu,
  ExternalLink,
  Layers,
  Loader2,
  Play,
  Plus,
  Radio,
  Sparkles,
  Square,
  TrendingDown,
  TrendingUp,
  X,
  Zap,
} from "lucide-react";
import {
  ActiveTrade,
  TradeDirectInsertPayload,
  TraderPreset,
} from "../types/trades.types";
import {
  useAdjustTrade,
  useExitTrade,
  useInsertDirectTrade,
  useTradeDetail,
} from "../hooks/useTrades";
import { useTradeStream } from "../hooks/useTradeStream";
import { useSessionSearch } from "../../sessions/hooks/useSessions";
import { TradePremiumChart } from "./TradePremiumChart";
import { TradeLiveLadder } from "./TradeLiveLadder";
import {
  FibRetracementChart,
  OptionChainOAChart,
  buildDefaultOAAnalysis,
  computeFibLevels,
} from "./FibAndOACharts";
import {
  useCheckOpportunity,
  useLatestOpportunities,
  useOpportunityCards,
  useOpportunityLoop,
  useStartOpportunity,
  useStopAll,
} from "../../opportunities/hooks/useOpportunities";
import { Opportunity, OpportunityCheckItem } from "../../opportunities/types/opportunities.types";
import { CheckVerdict } from "../../opportunities/components/CheckVerdict";
import {
  formatCompactRupee,
  formatExpiry,
  formatRupee,
} from "../../opportunities/components/formatters";
import { LOT_SIZES } from "../../opportunities/components/underlyingNames";

export type SideSheetMode = "SUGGESTIONS" | "TRADE_INSPECT" | "INSERT_TRADE";

export interface TraderSideSheetProps {
  mode: SideSheetMode;
  preset: TraderPreset;
  allPresets: TraderPreset[];
  selectedTradeId?: number | null;
  defaultSessionId?: number;
  onChangeMode: (mode: SideSheetMode) => void;
  onSelectPreset: (code: string) => void;
  onSelectTrade: (tradeId: number) => void;
  onClose: () => void;
}

function mapOpportunityToTrader(op: Opportunity): string {
  const s = (op.strategy || "").toLowerCase();
  if (
    s.includes("fib") ||
    s.includes("pullback") ||
    s.includes("ema") ||
    s.includes("supertrend") ||
    s.includes("golden") ||
    s.includes("swing")
  ) {
    return "FIB_GOLDEN_TRADER";
  }
  if (
    s.includes("orb") ||
    s.includes("open drive") ||
    s.includes("fii") ||
    s.includes("breakout") ||
    s.includes("momentum") ||
    s.includes("gamma") ||
    s.includes("squeeze")
  ) {
    return "ORB_WAVE_TRADER";
  }
  if (
    s.includes("vwap") ||
    s.includes("cpr") ||
    s.includes("pivot") ||
    s.includes("rsi") ||
    s.includes("oi") ||
    s.includes("flow")
  ) {
    return "FLOW_VWAP_TRADER";
  }
  if (op.rewardRisk >= 1.8) return "ORB_WAVE_TRADER";
  if (op.confidence >= 78) return "FIB_GOLDEN_TRADER";
  return "FLOW_VWAP_TRADER";
}

interface SyntheticSuggestion {
  id: number;
  traderCode: string;
  underlyingCode: string;
  optionType: "CE" | "PE";
  strike: number;
  expiry: string;
  spot: number;
  entry: number;
  stop: number;
  target: number;
  confidence: number;
  rewardRisk: number;
  strategy: string;
  reasons: string[];
  risks: string[];
}

const DEFAULT_SUGGESTIONS: SyntheticSuggestion[] = [
  {
    id: -101,
    traderCode: "FIB_GOLDEN_TRADER",
    underlyingCode: "NIFTY",
    optionType: "CE",
    strike: 24500,
    expiry: new Date().toISOString().slice(0, 10),
    spot: 24518,
    entry: 120,
    stop: 92,
    target: 175,
    confidence: 86,
    rewardRisk: 1.96,
    strategy: "Fibonacci 0.618 Golden Pocket + Put OI Floor",
    reasons: [
      "Option premium pulled back into 0.50–0.618 Golden Pocket (₹118–₹122) after impulse wave from ₹84 → ₹175",
      "OA Structure: +29% Put OI writing floor at 24,450 backs 0.786 Stop Loss (₹92); Call unwinding above 24,550 opens 1.272 (₹190) & 1.618 (₹209) extensions",
      "1m bullish engulfing candle with 1.48x volume ratio confirmation",
    ],
    risks: ["Avoid chasing above ₹126 where initial R:R drops below 1.5x"],
  },
  {
    id: -102,
    traderCode: "FIB_GOLDEN_TRADER",
    underlyingCode: "BANKNIFTY",
    optionType: "CE",
    strike: 52200,
    expiry: new Date().toISOString().slice(0, 10),
    spot: 52240,
    entry: 240,
    stop: 190,
    target: 340,
    confidence: 83,
    rewardRisk: 2.0,
    strategy: "Fibonacci Golden Pocket + EMA-20 Bounce",
    reasons: [
      "Clean 0.618 retracement hold at ₹240 with banking heavyweights holding above session VWAP",
      "OA Structure: PCR 1.28 with strong Put OI support wall at 52,100 and 1.272 Fib extension at ₹367",
    ],
    risks: ["Watch 52,500 Call OI resistance wall for partial profit lock"],
  },
  {
    id: -201,
    traderCode: "ORB_WAVE_TRADER",
    underlyingCode: "NIFTY",
    optionType: "CE",
    strike: 24550,
    expiry: new Date().toISOString().slice(0, 10),
    spot: 24542,
    entry: 50,
    stop: 35,
    target: 100,
    confidence: 88,
    rewardRisk: 3.33,
    strategy: "15m Opening Range Breakout + Step-Wave (100→120→150)",
    reasons: [
      "High-velocity 15m ORB breakout with 1.62x volume expansion and expanding 1m ATR",
      "Step-Wave Brain ready: Planned Target ₹100, Projected 1.618 Wave ₹150 — at ₹90 (80% move) locks SL at ₹75 and steps Target 100 → 120 → 150",
      "OA Structure: Short-covering by 24,500 Call writers (-16% Call OI) accelerating gamma expansion",
    ],
    risks: ["Trail SL aggressively if 1m candle prints upper wick ratio > 0.45"],
  },
  {
    id: -202,
    traderCode: "ORB_WAVE_TRADER",
    underlyingCode: "SENSEX",
    optionType: "PE",
    strike: 80800,
    expiry: new Date().toISOString().slice(0, 10),
    spot: 80760,
    entry: 165,
    stop: 128,
    target: 245,
    confidence: 81,
    rewardRisk: 2.16,
    strategy: "Volatility Squeeze Breakdown + Wave Runner",
    reasons: [
      "Multi-bar consolidation box breakdown with 1.45x Put volume surge",
      "OA Structure: Call OI wall addition (+26%) at 80,900 capping upside; wave extension projects ₹294 (1.618x)",
    ],
    risks: ["Keep initial stop above 0.786 box high (₹128)"],
  },
  {
    id: -301,
    traderCode: "FLOW_VWAP_TRADER",
    underlyingCode: "NIFTY",
    optionType: "PE",
    strike: 24450,
    expiry: new Date().toISOString().slice(0, 10),
    spot: 24435,
    entry: 110,
    stop: 86,
    target: 158,
    confidence: 84,
    rewardRisk: 2.0,
    strategy: "Institutional OI Unwinding Trap + VWAP Rejection",
    reasons: [
      "OA Structure: Put writers trapped at 24,500 (-18% OI unwinding) while Call OI builds heavily (+31%) at 24,500 ceiling",
      "Price rejected cleanly off Session VWAP with 1s Step-Guard ready to lock +30% at 50% progress and +50% at 80% progress",
    ],
    risks: ["Square off if Spot reclaims Session VWAP on 5m close"],
  },
  {
    id: -302,
    traderCode: "FLOW_VWAP_TRADER",
    underlyingCode: "CRUDEOIL",
    optionType: "CE",
    strike: 6100,
    expiry: new Date().toISOString().slice(0, 10),
    spot: 6112,
    entry: 95,
    stop: 74,
    target: 138,
    confidence: 80,
    rewardRisk: 2.05,
    strategy: "MCX Session VWAP Reclaim + Put OI Wall",
    reasons: [
      "Reclaimed MCX Session VWAP with strong 6,050 Put OI support floor and rising 1m volume",
      "1.272 Fib extension at ₹149 and 1.618 wave ceiling at ₹164",
    ],
    risks: ["Inventory data volatility window"],
  },
];

export const TraderSideSheet: React.FC<TraderSideSheetProps> = ({
  mode,
  preset,
  allPresets,
  selectedTradeId,
  defaultSessionId,
  onChangeMode,
  onSelectPreset,
  onSelectTrade,
  onClose,
}) => {
  const navigate = useNavigate();

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // ── Live Scanner Engine & Opportunities Hook (from Opportunities module) ──
  const loop = useOpportunityLoop();
  const { cards: oppCards } = useOpportunityCards(loop.running);
  const latestOppsQuery = useLatestOpportunities(loop.running);
  const startScanner = useStartOpportunity();
  const stopAllScanner = useStopAll();
  const checkOpportunity = useCheckOpportunity();

  const [checkedItems, setCheckedItems] = useState<Record<number, OpportunityCheckItem>>({});
  const [checkingOppId, setCheckingOppId] = useState<number | null>(null);
  const [underlyingFilter, setUnderlyingFilter] = useState<string>("ALL");

  const runningScannersCount = oppCards.filter((c) => c.master?.state === "RUNNING").length;

  const handleCheck = (opportunityId: number) => {
    if (opportunityId <= 0) return;
    setCheckingOppId(opportunityId);
    checkOpportunity.mutate(opportunityId, {
      onSuccess: (res) => setCheckedItems((prev) => ({ ...prev, [opportunityId]: res })),
      onSettled: () => setCheckingOppId(null),
    });
  };

  // Merge live scanned opportunities for this Trader with institutional Fib+OA suggestions
  const traderSuggestions = useMemo<SyntheticSuggestion[]>(() => {
    const liveList = (latestOppsQuery.data?.list ?? []).filter(
      (op) => mapOpportunityToTrader(op) === preset.code,
    );
    const mappedLive: SyntheticSuggestion[] = liveList.map((op) => ({
      id: op.id,
      traderCode: preset.code,
      underlyingCode: op.underlyingCode,
      optionType: op.optionType,
      strike: op.strike,
      expiry: op.expiry,
      spot: op.spot || op.strike,
      entry: op.entry,
      stop: op.stop,
      target: op.target,
      confidence: op.confidence,
      rewardRisk: op.rewardRisk,
      strategy: op.strategy || preset.methodology,
      reasons: op.reasons,
      risks: op.risks,
    }));
    const defaultsForPreset = DEFAULT_SUGGESTIONS.filter((d) => d.traderCode === preset.code);
    const combined = [...mappedLive, ...defaultsForPreset];
    if (underlyingFilter === "ALL") return combined;
    return combined.filter((item) => item.underlyingCode === underlyingFilter);
  }, [latestOppsQuery.data, preset.code, preset.methodology, underlyingFilter]);

  // ── Selected Trade Inspection State (`TRADE_INSPECT` mode) ──
  const activeTradeId = selectedTradeId ?? 0;
  const { data: initialTrade } = useTradeDetail(activeTradeId);
  const stream = useTradeStream(
    activeTradeId,
    mode === "TRADE_INSPECT" && !!initialTrade && initialTrade.tradeState === "RUNNING",
  );
  const inspectedTrade: ActiveTrade | undefined = stream.trade ?? initialTrade;
  const adjustMutation = useAdjustTrade(activeTradeId);
  const exitMutation = useExitTrade(activeTradeId);
  const [inspectFeedback, setInspectFeedback] = useState<string | null>(null);

  // ── Direct Trade Inserter Form State (`INSERT_TRADE` mode) ──
  const insertMutation = useInsertDirectTrade();
  const { data: activeSessionsPage } = useSessionSearch({
    page: 0,
    limit: 20,
    sessionStatus: "ACTIVE",
    status: "ACTIVE",
  });
  const activeSessions = activeSessionsPage?.list ?? [];
  const [insSessionId, setInsSessionId] = useState<number | undefined>(defaultSessionId);
  const [insTraderCode, setInsTraderCode] = useState<string>(preset.code);
  const [insUnderlying, setInsUnderlying] = useState<string>("NIFTY");
  const [insOptionType, setInsOptionType] = useState<"CE" | "PE">("CE");
  const [insStrike, setInsStrike] = useState<number>(24500);
  const [insLots, setInsLots] = useState<number>(1);
  const [insSwingLow, setInsSwingLow] = useState<number>(75);
  const [insSwingHigh, setInsSwingHigh] = useState<number>(150);
  const [insEntry, setInsEntry] = useState<number>(100);
  const [insStop, setInsStop] = useState<number>(78);
  const [insTarget, setInsTarget] = useState<number>(150);
  const [insStrategy, setInsStrategy] = useState<string>(
    "Fibonacci 0.618 Golden Pocket + OA Flow",
  );
  const [insConfidence, setInsConfidence] = useState<number>(85);
  const [insOpportunityId, setInsOpportunityId] = useState<number | undefined>(undefined);
  const [insertError, setInsertError] = useState<string | null>(null);

  useEffect(() => {
    setInsTraderCode(preset.code);
  }, [preset.code]);

  const prefillFromSuggestion = (s: SyntheticSuggestion) => {
    setInsTraderCode(s.traderCode);
    setInsUnderlying(s.underlyingCode);
    setInsOptionType(s.optionType);
    setInsStrike(s.strike);
    setInsEntry(s.entry);
    setInsStop(s.stop);
    setInsTarget(s.target);
    setInsSwingLow(Number((s.stop * 0.92).toFixed(2)));
    setInsSwingHigh(s.target);
    setInsStrategy(s.strategy);
    setInsConfidence(Math.round(s.confidence));
    setInsOpportunityId(s.id > 0 ? s.id : undefined);
    setInsertError(null);
    onChangeMode("INSERT_TRADE");
  };

  const handleQuickInsertSuggestion = (s: SyntheticSuggestion) => {
    setInsertError(null);
    const fib = computeFibLevels(s.entry, s.stop, s.target);
    const oa = buildDefaultOAAnalysis(
      s.underlyingCode,
      s.optionType,
      s.strike,
      s.stop,
      s.target,
    );
    const payload: TradeDirectInsertPayload = {
      sessionId: insSessionId || defaultSessionId,
      opportunityId: s.id > 0 ? s.id : undefined,
      traderCode: s.traderCode,
      underlyingCode: s.underlyingCode,
      optionType: s.optionType,
      strike: s.strike,
      expiry: s.expiry,
      entryAt: s.entry,
      initialStop: s.stop,
      initialTarget: s.target,
      lots: 1,
      strategy: s.strategy,
      confidence: Math.round(s.confidence),
      swingLow: fib.swingLow,
      swingHigh: fib.swingHigh,
      oaAnalysis: oa,
    };
    insertMutation.mutate(payload, {
      onSuccess: (created) => {
        onSelectTrade(created.id);
        onChangeMode("TRADE_INSPECT");
      },
      onError: (err) => {
        setInsertError(err instanceof Error ? err.message : "Failed to insert trade");
      },
    });
  };

  const handleRecalcFromFibSwing = (low: number, high: number) => {
    setInsSwingLow(low);
    setInsSwingHigh(high);
    if (high > low && low > 0) {
      const range = high - low;
      // 0.618 retracement from high back toward low:
      const pocketEntry = Number((high - 0.618 * range).toFixed(2));
      const stop786 = Number(Math.max(1, high - 0.786 * range).toFixed(2));
      const tgt100 = Number(high.toFixed(2));
      setInsEntry(pocketEntry);
      setInsStop(stop786);
      setInsTarget(tgt100);
    }
  };

  const handleInsertSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setInsertError(null);
    const oa = buildDefaultOAAnalysis(
      insUnderlying,
      insOptionType,
      insStrike,
      insStop,
      insTarget,
    );
    const payload: TradeDirectInsertPayload = {
      sessionId: insSessionId || defaultSessionId,
      opportunityId: insOpportunityId,
      traderCode: insTraderCode,
      underlyingCode: insUnderlying,
      optionType: insOptionType,
      strike: insStrike,
      entryAt: insEntry,
      initialStop: insStop,
      initialTarget: insTarget,
      lots: Math.max(1, insLots),
      strategy: insStrategy,
      confidence: insConfidence,
      swingLow: insSwingLow,
      swingHigh: insSwingHigh,
      oaAnalysis: oa,
    };
    insertMutation.mutate(payload, {
      onSuccess: (created) => {
        onSelectTrade(created.id);
        onChangeMode("TRADE_INSPECT");
      },
      onError: (err) => {
        setInsertError(err instanceof Error ? err.message : "Could not insert trade");
      },
    });
  };

  const lotSize = LOT_SIZES[insUnderlying] ?? 25;
  const insertQty = Math.max(1, insLots) * lotSize;
  const insertCap = insertQty * insEntry;
  const insertRisk = insertQty * Math.max(0, insEntry - insStop);
  const insertReward = insertQty * Math.max(0, insTarget - insEntry);
  const insertRR =
    insEntry > insStop ? (insTarget - insEntry) / (insEntry - insStop) : 0;
  const insertFib = computeFibLevels(
    insEntry,
    insStop,
    insTarget,
    insSwingLow,
    insSwingHigh,
  );

  return (
    <div className="ss-backdrop" onClick={onClose} role="presentation">
      <div
        className="ss-sheet"
        style={{ width: "min(920px, 100vw)" }}
        role="dialog"
        aria-modal="true"
        aria-label="Trader Suggestions, Fib + OA Analyzer & Live Trade Sidebar"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── 1. Top Terminal Header Bar ── */}
        <div className="ss-head">
          <div className="ss-head-left">
            <div className="ss-eyebrow">
              <span className="sp-symbol sp-symbol--commodity">{preset.shortLabel}</span>
              <h2 className="ss-title">
                {mode === "TRADE_INSPECT" && inspectedTrade
                  ? `Trade #${inspectedTrade.id} · ${inspectedTrade.underlyingCode} ${inspectedTrade.strike} ${inspectedTrade.optionType}`
                  : mode === "INSERT_TRADE"
                    ? "Insert Trade · Fibonacci + OA Option-Chain Analyzer"
                    : `${preset.name} · Live Suggestions`}
              </h2>
              <span className="badge badge--green">
                <Radio size={11} /> 1s TRADER BRAIN
              </span>
            </div>
            <div className="ss-subline">
              <span>{preset.methodology}</span>
            </div>
          </div>

          <div className="ss-head-actions">
            {runningScannersCount > 0 ? (
              <button
                type="button"
                className="sp-btn sp-btn--stop ss-action-btn"
                onClick={() => stopAllScanner.mutate()}
                disabled={stopAllScanner.isPending}
                title="Stop live underlying scanner loop"
              >
                <Square size={11} />
                <span>Stop Scanner ({runningScannersCount})</span>
              </button>
            ) : (
              <button
                type="button"
                className="sp-btn sp-btn--run ss-action-btn"
                onClick={() => startScanner.mutate(undefined)}
                disabled={startScanner.isPending}
                title="Start live underlying scanner loop for Trader suggestions"
              >
                <Play size={11} />
                <span>{startScanner.isPending ? "Starting…" : "Scan Live Setups"}</span>
              </button>
            )}

            <button
              type="button"
              className="ss-close"
              onClick={onClose}
              aria-label="Close sidebar"
            >
              <X size={17} />
            </button>
          </div>
        </div>

        {/* ── 2. Mode & Specialist Trader Switcher Bar ── */}
        <div className="ss-compact-bar">
          <div className="ss-filters-group">
            <button
              type="button"
              className={`ss-filter-btn ${mode === "SUGGESTIONS" ? "is-active" : ""}`}
              onClick={() => onChangeMode("SUGGESTIONS")}
            >
              <Sparkles size={11} style={{ marginRight: 4, display: "inline" }} />
              Trader Suggestions ({traderSuggestions.length})
            </button>

            <button
              type="button"
              className={`ss-filter-btn ${mode === "INSERT_TRADE" ? "is-active" : ""}`}
              onClick={() => onChangeMode("INSERT_TRADE")}
            >
              <Plus size={11} style={{ marginRight: 4, display: "inline" }} />
              Insert Trade (Fib + OA Chart)
            </button>

            {inspectedTrade && (
              <button
                type="button"
                className={`ss-filter-btn ${mode === "TRADE_INSPECT" ? "is-active" : ""}`}
                onClick={() => onChangeMode("TRADE_INSPECT")}
              >
                <Activity size={11} style={{ marginRight: 4, display: "inline" }} />
                Live Trade #{inspectedTrade.id} ({inspectedTrade.underlyingCode}{" "}
                {inspectedTrade.strike} {inspectedTrade.optionType})
              </button>
            )}
          </div>

          {/* Quick Trader Preset Switcher Pills */}
          <div className="ss-view-toggle">
            {allPresets.map((p) => (
              <button
                key={p.code}
                type="button"
                className={`ss-view-btn ${preset.code === p.code ? "is-active" : ""}`}
                onClick={() => onSelectPreset(p.code)}
                title={p.name}
              >
                <span>{p.shortLabel}</span>
              </button>
            ))}
          </div>
        </div>

        {/* ── 3. Scrollable Body ── */}
        <div className="ss-body">
          {insertError && (
            <div className="ss-notice ss-notice--error">
              <AlertTriangle size={14} />
              <span>{insertError}</span>
            </div>
          )}

          {/* =====================================================================
              MODE A: TRADER SUGGESTIONS (Right-Side Bar like old Opportunities)
             ===================================================================== */}
          {mode === "SUGGESTIONS" && (
            <>
              {/* Trader Brain Summary & Underlying Filter */}
              <div className="sd-card">
                <div className="sd-card-header">
                  <div>
                    <span className="sd-card-title">
                      <Cpu size={13} style={{ display: "inline", marginRight: 6 }} />
                      {preset.name} — Discovery &amp; 1-Second Step-Wave Rules
                    </span>
                    <span className="sd-card-sub">{preset.entryLogic}</span>
                  </div>
                  <button
                    type="button"
                    className="sp-btn sp-btn--run"
                    onClick={() => onChangeMode("INSERT_TRADE")}
                  >
                    <Plus size={13} /> Custom Fib + OA Trade
                  </button>
                </div>
                <div className="micro text-secondary">
                  <strong className="text-green">1s Re-Analysis Loop:</strong> {preset.trailLogic}
                </div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: "8px",
                    paddingTop: "6px",
                    borderTop: "1px solid var(--border-subtle)",
                  }}
                >
                  <div className="ss-filters-group">
                    {(
                      ["ALL", "NIFTY", "BANKNIFTY", "SENSEX", "CRUDEOIL"] as const
                    ).map((u) => (
                      <button
                        key={u}
                        type="button"
                        className={`ss-filter-btn ${underlyingFilter === u ? "is-active" : ""}`}
                        onClick={() => setUnderlyingFilter(u)}
                      >
                        {u}
                      </button>
                    ))}
                  </div>
                  <span className="mono micro text-muted">
                    Click &ldquo;Insert with Fib + OA&rdquo; to inspect charts or &ldquo;Quick Launch 1s Trade&rdquo; to enter immediately
                  </span>
                </div>
              </div>

              {/* Suggestions List */}
              <div className="ss-cards-stack">
                {traderSuggestions.map((s) => {
                  const isCall = s.optionType === "CE";
                  const fib = computeFibLevels(s.entry, s.stop, s.target);
                  const oa = buildDefaultOAAnalysis(
                    s.underlyingCode,
                    s.optionType,
                    s.strike,
                    s.stop,
                    s.target,
                  );
                  const lotUnits = LOT_SIZES[s.underlyingCode] ?? 25;
                  const capPerLot = s.entry * lotUnits;
                  const riskPerLot = Math.max(0, s.entry - s.stop) * lotUnits;
                  const rewardPerLot = Math.max(0, s.target - s.entry) * lotUnits;
                  const chk = checkedItems[s.id];
                  const isCheckingThis = checkingOppId === s.id;

                  return (
                    <div
                      key={s.id}
                      className={`oc-card ${isCall ? "oc-card--call" : "oc-card--put"}`}
                    >
                      <div className="oc-head">
                        <div className="oc-head-left">
                          <div className={`oc-action-badge ${isCall ? "is-call" : "is-put"}`}>
                            {isCall ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                            <span>BUY {s.optionType}</span>
                          </div>
                          <div className="oc-contract-block">
                            <span className="oc-strike-val mono">
                              {s.underlyingCode} {s.strike.toLocaleString("en-IN")} {s.optionType}
                            </span>
                            <span className="oc-moneyness-tag is-atm mono">
                              {formatExpiry(s.expiry)}
                            </span>
                          </div>
                          <span className="sd-tag sd-tag--cyan mono">{s.strategy}</span>
                        </div>

                        <div className="oc-head-right">
                          <span className={`badge ${s.id > 0 ? "badge--green" : "badge--amber"}`}>
                            {s.id > 0 ? "LIVE SCAN" : "FIB + OA TEMPLATE"}
                          </span>
                          <div className="oc-edge-chip mono" title="Trader Confidence">
                            <Sparkles size={11} />
                            <span className="oc-edge-val">{s.confidence.toFixed(0)}%</span>
                          </div>
                          <span className="badge badge--green mono">
                            1 : {s.rewardRisk.toFixed(2)} R:R
                          </span>
                        </div>
                      </div>

                      <div className="oc-body">
                        {/* 4-Cell Trade Plan Strip */}
                        <div className="oc-compact-strip">
                          <div className="oc-compact-cell oc-compact-cell--entry">
                            <div className="oc-compact-top">
                              <span>0.618 POCKET ENTRY</span>
                              <span className="mono entry">1 Lot = {lotUnits}</span>
                            </div>
                            <div className="oc-compact-val entry">{formatRupee(s.entry)}</div>
                            <div className="oc-compact-sub">
                              Cap: {formatCompactRupee(capPerLot)} / lot
                            </div>
                          </div>

                          <div className="oc-compact-cell oc-compact-cell--stop">
                            <div className="oc-compact-top">
                              <span>0.786 / OA FLOOR SL</span>
                              <span className="mono neg">
                                Put Wall {oa.putOiSupportWall.toLocaleString("en-IN")}
                              </span>
                            </div>
                            <div className="oc-compact-val neg">{formatRupee(s.stop)}</div>
                            <div className="oc-compact-sub">
                              Risk: -{formatCompactRupee(riskPerLot)} / lot
                            </div>
                          </div>

                          <div className="oc-compact-cell oc-compact-cell--target">
                            <div className="oc-compact-top">
                              <span>1.0 TARGET (T1)</span>
                              <span className="mono pos">
                                <ArrowUpRight size={11} />
                                +₹{(s.target - s.entry).toFixed(1)}
                              </span>
                            </div>
                            <div className="oc-compact-val pos">{formatRupee(s.target)}</div>
                            <div className="oc-compact-sub">
                              Gain: +{formatCompactRupee(rewardPerLot)} / lot
                            </div>
                          </div>

                          <div className="oc-compact-cell oc-compact-cell--rr">
                            <div className="oc-compact-top">
                              <span>STEP-WAVE 1.272 / 1.618</span>
                              <span className="mono" style={{ color: "var(--cyan)" }}>
                                PCR {oa.pcr.toFixed(2)}
                              </span>
                            </div>
                            <div className="oc-compact-val mono" style={{ color: "var(--cyan)" }}>
                              {formatRupee(fib.fib1272)} → {formatRupee(fib.fib1618)}
                            </div>
                            <div className="oc-compact-sub">
                              Locks SL @ {formatRupee(fib.fib618)} → {formatRupee(fib.fib100)}
                            </div>
                          </div>
                        </div>

                        {/* Fibonacci + OA Summary Strip */}
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            flexWrap: "wrap",
                            gap: "8px",
                            padding: "7px 10px",
                            background: "var(--bg-input)",
                            border: "1px solid var(--border-subtle)",
                            borderRadius: "4px",
                            fontSize: "0.72rem",
                          }}
                        >
                          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                            <span className="mono text-secondary">
                              <strong>Fib Wave:</strong> 0.618 ({formatRupee(s.entry)}) → 1.0 (
                              {formatRupee(fib.fib100)}) → 1.272 ({formatRupee(fib.fib1272)}) →
                              1.618 ({formatRupee(fib.fib1618)})
                            </span>
                            <span className="mono text-green">
                              <strong>OA Floor:</strong> {oa.putOiSupportWall.toLocaleString("en-IN")}{" "}
                              Put OI
                            </span>
                            <span className="mono text-amber">
                              <strong>OA Wall:</strong>{" "}
                              {oa.callOiResistanceWall.toLocaleString("en-IN")} Call OI
                            </span>
                          </div>

                          <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                            {s.id > 0 && (
                              <button
                                type="button"
                                className={`oc-check-btn ${chk ? "oc-check-btn--done" : ""}`}
                                onClick={() => handleCheck(s.id)}
                                disabled={isCheckingThis}
                              >
                                {isCheckingThis ? (
                                  <Loader2 size={11} className="sp-spin" />
                                ) : (
                                  <ClipboardCheck size={11} />
                                )}
                                <span>{chk ? "Re-check 1m" : "Check 1m"}</span>
                              </button>
                            )}
                            <button
                              type="button"
                              className="sd-ctrl-btn"
                              onClick={() => prefillFromSuggestion(s)}
                            >
                              <Layers size={12} />
                              <span>Open in Fib + OA Chart</span>
                            </button>
                            <button
                              type="button"
                              className="sd-ctrl-btn sd-ctrl-btn--primary"
                              onClick={() => handleQuickInsertSuggestion(s)}
                              disabled={insertMutation.isPending}
                            >
                              <Play size={12} />
                              <span>
                                {insertMutation.isPending
                                  ? "Launching…"
                                  : "Quick Launch 1s Trade"}
                              </span>
                            </button>
                          </div>
                        </div>

                        {chk && <CheckVerdict result={chk} />}

                        {/* Why This Setup & Watchouts */}
                        <div className="oc-insights-row">
                          <div className="oc-reasons-card">
                            <div className="oc-insights-title pos">
                              <CheckCircle2 size={11} />
                              <span>Why {preset.shortLabel} Picked This (Fib + OA Confluence)</span>
                            </div>
                            <ul className="oc-reasons-list">
                              {s.reasons.map((r, idx) => (
                                <li key={idx}>{r}</li>
                              ))}
                            </ul>
                          </div>
                          {s.risks.length > 0 && (
                            <div className="oc-risks-card">
                              <div className="oc-insights-title warn">
                                <AlertTriangle size={11} />
                                <span>1s Trader Guardrails</span>
                              </div>
                              <ul className="oc-risks-list">
                                {s.risks.map((rk, idx) => (
                                  <li key={idx}>{rk}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}

          {/* =====================================================================
              MODE B: INSERT TRADE WITH FIBONACCI + OA (OPTION CHAIN) CHARTS
             ===================================================================== */}
          {mode === "INSERT_TRADE" && (
            <>
              {/* Quick Pre-fill Strip from Live Trader Suggestions */}
              <div className="sd-card">
                <div className="sd-card-header">
                  <div>
                    <span className="sd-card-title">
                      1-Click Pre-Fill from {preset.shortLabel} Live Suggestions
                    </span>
                    <span className="sd-card-sub">
                      Select a suggested setup below or customize your own Fibonacci Swing + OA Strike parameters
                    </span>
                  </div>
                </div>
                <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                  {traderSuggestions.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      className={`toggle-chip ${
                        insUnderlying === s.underlyingCode &&
                        insStrike === s.strike &&
                        insOptionType === s.optionType
                          ? "toggle-chip--active"
                          : ""
                      }`}
                      onClick={() => prefillFromSuggestion(s)}
                    >
                      <span className="mono">
                        {s.underlyingCode} {s.strike} {s.optionType} @ ₹{s.entry} (SL ₹{s.stop} →
                        Tgt ₹{s.target})
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Interactive Fibonacci Chart (with 1-Click Target/SL Step Selector) */}
              <FibRetracementChart
                entryAt={insEntry}
                currentStop={insStop}
                currentTarget={insTarget}
                lastPrice={insEntry}
                fibLevels={insertFib}
                onSelectTargetLevel={(tgt, sl) => {
                  setInsTarget(tgt);
                  setInsStop(sl);
                }}
              />

              {/* Interactive OA (Option Chain Call/Put OI & Volume) Chart */}
              <OptionChainOAChart
                underlyingCode={insUnderlying}
                optionType={insOptionType}
                strike={insStrike}
                initialStop={insStop}
                initialTarget={insTarget}
                onSelectStrike={(st) => setInsStrike(st)}
              />

              {/* Trade Parameters & Fibonacci Calculator Form */}
              <form className="sd-card" onSubmit={handleInsertSubmit}>
                <div className="sd-card-header">
                  <div>
                    <span className="sd-card-title">
                      Insert Trade Configuration &amp; Fibonacci Swing Calculator
                    </span>
                    <span className="sd-card-sub">
                      Adjust Swing Low / High to auto-calculate 0.618 Golden Pocket Entry &amp; 0.786 Stop, or enter exact option prices
                    </span>
                  </div>
                  <span className="badge badge--green mono">
                    1 : {insertRR.toFixed(2)} R:R · {insertQty} Qty
                  </span>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
                    gap: "10px",
                  }}
                >
                  <div className="form-group">
                    <label className="form-label">Specialist Trader</label>
                    <select
                      className="select"
                      value={insTraderCode}
                      onChange={(e) => {
                        setInsTraderCode(e.target.value);
                        onSelectPreset(e.target.value);
                      }}
                    >
                      {allPresets.map((p) => (
                        <option key={p.code} value={p.code}>
                          {p.shortLabel} — {p.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Underlying</label>
                    <select
                      className="select mono"
                      value={insUnderlying}
                      onChange={(e) => {
                        const code = e.target.value;
                        setInsUnderlying(code);
                        if (code === "NIFTY") setInsStrike(24500);
                        else if (code === "BANKNIFTY") setInsStrike(52200);
                        else if (code === "SENSEX") setInsStrike(80800);
                        else if (code === "FINNIFTY") setInsStrike(23800);
                        else if (code === "CRUDEOIL") setInsStrike(6100);
                      }}
                    >
                      <option value="NIFTY">NIFTY (Lot 75)</option>
                      <option value="BANKNIFTY">BANKNIFTY (Lot 30)</option>
                      <option value="SENSEX">SENSEX (Lot 20)</option>
                      <option value="FINNIFTY">FINNIFTY (Lot 65)</option>
                      <option value="CRUDEOIL">CRUDEOIL (Lot 100)</option>
                      <option value="NATURALGAS">NATURALGAS (Lot 1250)</option>
                      <option value="GOLDM">GOLDM (Lot 10)</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Option Type</label>
                    <div className="sd-seg-group" style={{ height: 36 }}>
                      {(["CE", "PE"] as const).map((ot) => (
                        <button
                          key={ot}
                          type="button"
                          className={`sd-seg-btn ${insOptionType === ot ? "active" : ""}`}
                          style={{ flex: 1, justifyContent: "center", height: 30 }}
                          onClick={() => setInsOptionType(ot)}
                        >
                          {ot === "CE" ? "CALL (CE)" : "PUT (PE)"}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Strike Price</label>
                    <input
                      type="number"
                      step="50"
                      className="input mono"
                      value={insStrike}
                      onChange={(e) => setInsStrike(Number(e.target.value) || 0)}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Fib Swing Low (₹)</label>
                    <input
                      type="number"
                      step="0.5"
                      className="input mono"
                      value={insSwingLow}
                      onChange={(e) =>
                        handleRecalcFromFibSwing(Number(e.target.value) || 0, insSwingHigh)
                      }
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Fib Swing High 1.0 (₹)</label>
                    <input
                      type="number"
                      step="0.5"
                      className="input mono"
                      value={insSwingHigh}
                      onChange={(e) =>
                        handleRecalcFromFibSwing(insSwingLow, Number(e.target.value) || 0)
                      }
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Entry @ 0.618 (₹)</label>
                    <input
                      type="number"
                      step="0.05"
                      className="input mono"
                      value={insEntry}
                      onChange={(e) => setInsEntry(Number(e.target.value) || 0)}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Stop Loss @ 0.786 (₹)</label>
                    <input
                      type="number"
                      step="0.05"
                      className="input mono text-red"
                      value={insStop}
                      onChange={(e) => setInsStop(Number(e.target.value) || 0)}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Target (1.0 / 1.272) (₹)</label>
                    <input
                      type="number"
                      step="0.05"
                      className="input mono text-green"
                      value={insTarget}
                      onChange={(e) => setInsTarget(Number(e.target.value) || 0)}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Lots (1 Lot = {lotSize})</label>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      className="input mono"
                      value={insLots}
                      onChange={(e) => setInsLots(Math.max(1, Number(e.target.value) || 1))}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Target Session</label>
                    <select
                      className="select"
                      value={insSessionId ?? ""}
                      onChange={(e) =>
                        setInsSessionId(e.target.value ? Number(e.target.value) : undefined)
                      }
                    >
                      <option value="">Auto-resolve / Create Active Session</option>
                      {activeSessions.map((sess) => (
                        <option key={sess.id} value={sess.id}>
                          S#{sess.id} — {sess.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Strategy / Setup Tag</label>
                    <input
                      type="text"
                      className="input"
                      value={insStrategy}
                      onChange={(e) => setInsStrategy(e.target.value)}
                    />
                  </div>
                </div>

                {/* Live Sizing & Step-Wave Preview Strip */}
                <div className="sd-telemetry-strip" style={{ borderRadius: 4, marginTop: 6 }}>
                  <div className="sd-telemetry-cell">
                    <span className="sd-telemetry-label">Capital Required</span>
                    <span className="sd-telemetry-val">{formatRupee(insertCap)}</span>
                    <span className="sd-telemetry-sub">
                      {insLots} × {lotSize} = {insertQty} qty
                    </span>
                  </div>
                  <div className="sd-telemetry-cell">
                    <span className="sd-telemetry-label">Max Risk (at SL)</span>
                    <span className="sd-telemetry-val text-red">-{formatRupee(insertRisk)}</span>
                    <span className="sd-telemetry-sub">SL ₹{insStop.toFixed(2)}</span>
                  </div>
                  <div className="sd-telemetry-cell">
                    <span className="sd-telemetry-label">T1 Reward (1.0)</span>
                    <span className="sd-telemetry-val text-green">
                      +{formatRupee(insertReward)}
                    </span>
                    <span className="sd-telemetry-sub">Target ₹{insTarget.toFixed(2)}</span>
                  </div>
                  <div className="sd-telemetry-cell">
                    <span className="sd-telemetry-label">Step-Wave 1.272</span>
                    <span className="sd-telemetry-val" style={{ color: "var(--cyan)" }}>
                      {formatRupee(insertFib.fib1272)}
                    </span>
                    <span className="sd-telemetry-sub">
                      Locks SL @ {formatRupee(insertFib.fib618)}
                    </span>
                  </div>
                  <div className="sd-telemetry-cell">
                    <span className="sd-telemetry-label">Wave Ceiling 1.618</span>
                    <span className="sd-telemetry-val" style={{ color: "var(--cyan)" }}>
                      {formatRupee(insertFib.fib1618)}
                    </span>
                    <span className="sd-telemetry-sub">
                      Locks SL @ {formatRupee(insertFib.fib100)}
                    </span>
                  </div>
                  <div className="sd-telemetry-cell" style={{ justifyContent: "center" }}>
                    <button
                      type="submit"
                      className="sp-btn sp-btn--run"
                      style={{ width: "100%", justifyContent: "center", height: 36 }}
                      disabled={insertMutation.isPending}
                    >
                      <Play size={13} />
                      <span>
                        {insertMutation.isPending ? "Inserting…" : "Insert & Start 1s Loop"}
                      </span>
                    </button>
                  </div>
                </div>
              </form>
            </>
          )}

          {/* =====================================================================
              MODE C: TRADE INSPECT SIDEBAR (When clicking any Trade row)
             ===================================================================== */}
          {mode === "TRADE_INSPECT" && inspectedTrade && (
            <>
              {/* Live 1-Second Trader Suggestion & Action Banner */}
              <div
                className="sd-card"
                style={{
                  borderColor:
                    inspectedTrade.marketTelemetry?.exitSignal
                      ? "var(--warning-amber)"
                      : "rgba(56, 189, 248, 0.4)",
                  background: inspectedTrade.marketTelemetry?.exitSignal
                    ? "var(--warning-amber-tint)"
                    : "rgba(56, 189, 248, 0.05)",
                }}
              >
                <div className="sd-card-header">
                  <div>
                    <span className="sd-card-title">
                      <Zap size={13} style={{ display: "inline", marginRight: 6 }} />
                      1-Second Trader Brain Live Suggestion —{" "}
                      {inspectedTrade.marketTelemetry?.traderName || preset.name}
                    </span>
                    <span className="sd-card-sub">
                      {inspectedTrade.marketTelemetry?.exitRecommendation ||
                        `Monitoring 1m structure (${inspectedTrade.marketTelemetry?.candleStructure ?? "STEADY"}) · Volume ${inspectedTrade.marketTelemetry?.volumeRatio ?? 1}x · Projected Wave Ceiling ${formatRupee(inspectedTrade.marketTelemetry?.projectedTarget ?? inspectedTrade.currentTarget)}`}
                    </span>
                  </div>

                  <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                    {inspectedTrade.tradeState === "RUNNING" && (
                      <>
                        <button
                          type="button"
                          className="sd-ctrl-btn sd-ctrl-btn--primary"
                          disabled={adjustMutation.isPending}
                          onClick={() => {
                            const fib = computeFibLevels(
                              inspectedTrade.entryAt,
                              inspectedTrade.initialStop,
                              inspectedTrade.initialTarget,
                            );
                            const nextStop =
                              inspectedTrade.currentTarget >= fib.fib1272
                                ? fib.fib100
                                : fib.fib618;
                            const nextTarget =
                              inspectedTrade.currentTarget >= fib.fib1272
                                ? fib.fib1618
                                : fib.fib1272;
                            adjustMutation.mutate(
                              {
                                currentStop: nextStop,
                                currentTarget: nextTarget,
                                reason: `Applied Trader Step-Wave Suggestion: SL → ₹${nextStop}, Target → ₹${nextTarget}`,
                              },
                              {
                                onSuccess: (u) =>
                                  setInspectFeedback(
                                    `Stepped SL to ₹${u.currentStop} & Target to ₹${u.currentTarget}`,
                                  ),
                              },
                            );
                          }}
                        >
                          <ArrowUpRight size={12} />
                          <span>Step Wave (Lock SL &amp; Expand Target)</span>
                        </button>

                        <button
                          type="button"
                          className="sd-ctrl-btn sd-ctrl-btn--danger"
                          disabled={exitMutation.isPending}
                          onClick={() =>
                            exitMutation.mutate(
                              { reason: "MANUAL_EXIT" },
                              {
                                onSuccess: (closed) =>
                                  setInspectFeedback(
                                    `Squared off at ₹${closed.exitPrice ?? closed.lastPrice}`,
                                  ),
                              },
                            )
                          }
                        >
                          <Square size={12} />
                          <span>Square Off</span>
                        </button>
                      </>
                    )}

                    <button
                      type="button"
                      className="sd-ctrl-btn"
                      onClick={() =>
                        navigate({
                          to: "/trades/$tradeId",
                          params: { tradeId: String(inspectedTrade.id) },
                        })
                      }
                    >
                      <ExternalLink size={12} />
                      <span>Full Cockpit</span>
                    </button>
                  </div>
                </div>

                {inspectFeedback && (
                  <div className="micro text-green" style={{ display: "flex", gap: 6 }}>
                    <CheckCircle2 size={13} />
                    <span>{inspectFeedback}</span>
                  </div>
                )}

                {/* Compact 5-KPI Telemetry Row */}
                <div className="sd-telemetry-strip" style={{ borderRadius: 4 }}>
                  <div className="sd-telemetry-cell">
                    <span className="sd-telemetry-label">Entry → LTP</span>
                    <span className="sd-telemetry-val">
                      {formatRupee(inspectedTrade.entryAt)} →{" "}
                      {formatRupee(inspectedTrade.exitPrice ?? inspectedTrade.lastPrice)}
                    </span>
                  </div>
                  <div className="sd-telemetry-cell">
                    <span className="sd-telemetry-label">Net P&amp;L</span>
                    <span
                      className={`sd-telemetry-val ${
                        inspectedTrade.netPnl > 0
                          ? "text-green"
                          : inspectedTrade.netPnl < 0
                            ? "text-red"
                            : ""
                      }`}
                    >
                      {formatRupee(inspectedTrade.netPnl)} (
                      {inspectedTrade.pnlPct >= 0 ? "+" : ""}
                      {inspectedTrade.pnlPct.toFixed(1)}%)
                    </span>
                  </div>
                  <div className="sd-telemetry-cell">
                    <span className="sd-telemetry-label">Active SL</span>
                    <span className="sd-telemetry-val text-red">
                      {formatRupee(inspectedTrade.currentStop)}
                    </span>
                  </div>
                  <div className="sd-telemetry-cell">
                    <span className="sd-telemetry-label">Active Target</span>
                    <span className="sd-telemetry-val text-green">
                      {formatRupee(inspectedTrade.currentTarget)}
                    </span>
                  </div>
                  <div className="sd-telemetry-cell">
                    <span className="sd-telemetry-label">Wave Ceiling</span>
                    <span className="sd-telemetry-val" style={{ color: "var(--cyan)" }}>
                      {formatRupee(
                        inspectedTrade.marketTelemetry?.projectedTarget ??
                          inspectedTrade.currentTarget,
                      )}
                    </span>
                  </div>
                  <div className="sd-telemetry-cell">
                    <span className="sd-telemetry-label">Lots (Qty)</span>
                    <span className="sd-telemetry-val">
                      {inspectedTrade.lots} ({inspectedTrade.quantity})
                    </span>
                  </div>
                </div>
              </div>

              {/* Live Price Ladder */}
              <TradeLiveLadder trade={inspectedTrade} />

              {/* Live 1m Option Premium Trajectory Graph */}
              <TradePremiumChart trade={inspectedTrade} />

              {/* Fibonacci Retracement & Extension Chart (with 1-Click Live Level Override!) */}
              <FibRetracementChart
                entryAt={inspectedTrade.entryAt}
                currentStop={inspectedTrade.currentStop}
                currentTarget={inspectedTrade.currentTarget}
                lastPrice={inspectedTrade.exitPrice ?? inspectedTrade.lastPrice}
                fibLevels={inspectedTrade.marketTelemetry?.fibLevels}
                onSelectTargetLevel={
                  inspectedTrade.tradeState === "RUNNING"
                    ? (tgt, sl, lbl) => {
                        adjustMutation.mutate(
                          {
                            currentStop: sl,
                            currentTarget: tgt,
                            reason: `Applied Fib Level (${lbl}): SL ₹${sl}, Target ₹${tgt}`,
                          },
                          {
                            onSuccess: (u) =>
                              setInspectFeedback(
                                `Updated SL to ₹${u.currentStop} & Target to ₹${u.currentTarget} (${lbl})`,
                              ),
                          },
                        );
                      }
                    : undefined
                }
              />

              {/* OA (Option Chain Call/Put OI & Volume) Structure Chart */}
              <OptionChainOAChart
                underlyingCode={inspectedTrade.underlyingCode}
                optionType={inspectedTrade.optionType}
                strike={inspectedTrade.strike}
                initialStop={inspectedTrade.currentStop}
                initialTarget={inspectedTrade.currentTarget}
                oaAnalysis={inspectedTrade.marketTelemetry?.oaAnalysis}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
};

