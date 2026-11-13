export interface BacktestTrade {
  time: string;
  setup: string;
  side: "CE" | "PE";
  dayType: string | null;
  strike: number;
  mode: "ATM" | "ITM" | "OTM" | "LOTTERY";
  delta: number;
  entryPremium: number;
  exitPremium: number;
  pctMove: number;
  outcome: "STOP" | "TARGET" | "STALLED" | "NO_NEW_HIGH" | "TIME" | "EOD";
  holdMinutes: number;
  netPnl: number;
}

export interface BacktestDayResult {
  date: string;
  code: string;
  error?: string;
  lotSize?: number;
  expiry?: string;
  dte?: number;
  opportunities?: number;
  wins?: number;
  losses?: number;
  winRatePct?: number | null;
  netPnl?: number;
  heldBackByGuardrails?: number;
  trades?: BacktestTrade[];
}

export interface BacktestIndexTotals {
  code: string;
  opportunities: number;
  wins: number;
  losses: number;
  winRatePct: number | null;
  netPnl: number;
  daysRun: number;
}

export interface BacktestTotals {
  opportunities: number;
  wins: number;
  losses: number;
  winRatePct: number | null;
  netPnl: number;
  datesRun: number;
  indicesRun: number;
  errors: number;
}

export interface BacktestRunResult {
  runs: BacktestDayResult[];
  perIndex: BacktestIndexTotals[];
  totals: BacktestTotals;
}

export interface RunBacktestParams {
  dates: string[];
  codes: string[];
}

// ───────────── FROM-TO range backtest (POST /backtest/range, GET /backtest/range/{jobId}) ─────────────
export interface RangeBacktestParams {
  fromDate: string;
  toDate: string;
  codes: string[];
  capital: number;
  maxLossPct: number;
  sizing: "MAX_LOTS" | "RISK";
}

export interface RangeStats {
  trades: number;
  wins: number;
  losses: number;
  winRatePct: number | null;
  netPnl: number;
  avgPnl: number | null;
  profitFactor: number | null;
  best: number | null;
  worst: number | null;
}

export interface RangeTrade {
  date: string;
  code: string;
  time: string;
  exitTime: string;
  setup: string;
  side: "CE" | "PE";
  mode: string;
  strike: number;
  delta: number;
  entryPremium: number;
  exitPremium: number;
  pctMove: number;
  outcome: "STOP" | "TRAIL" | "TIME_EXIT" | "EOD";
  holdMinutes: number;
  riskPerLot: number;
  premiumPerLot: number;
  lotSize: number;
  netPnl: number;
  reason: string;
}

export interface RangeRuleImpact extends RangeStats {
  rule: string;
  blockedSignals: number;
  verdict: "SAVED" | "COST";
  impact: number;
}

export interface RangeSetupStats extends RangeStats {
  setup: string;
  policy: string;
}

export interface RangeDaily {
  date: string;
  trades: number;
  netPnl: number;
  cumPnl: number;
}

export interface RangePortfolioTrade extends RangeTrade {
  lots: number;
  qty: number;
  capitalUsed: number;
  riskAmount: number;
  netPnlLots: number;
}

export interface RangePortfolio extends RangeStats {
  capital: number;
  sizing: "MAX_LOTS" | "RISK";
  oneLotRiskPct: number;
  maxLossPct: number;
  maxDrawdown: number;
  endingEquity: number;
  returnPct: number | null;
  avgLots: number | null;
  maxLots: number | null;
  skipped: Record<string, number>;
  daily: (RangeDaily & { equity: number })[];
  tradeList: RangePortfolioTrade[];
}

export interface RangeBacktestResult {
  range: { from: string | null; to: string | null; tradingDays: number; codes: string[]; filters: string; fiiOpenCodes: string; pricing: string };
  totals: RangeStats & {
    maxDrawdown: number;
    firstHalfPnl: number;
    secondHalfPnl: number;
    tradesPerDay: number;
    splitNote: string;
  };
  perIndex: (RangeStats & { code: string })[];
  perSetup: RangeSetupStats[];
  ruleImpact: RangeRuleImpact[];
  blockedSetups: RangeSetupStats[];
  daily: RangeDaily[];
  portfolio: RangePortfolio;
  trades: RangeTrade[];
  errors: { date: string; code: string; error: string }[];
}

export interface RangeBacktestJob {
  jobId: string;
  state: "RUNNING" | "DONE" | "FAILED";
  stage: string;
  progressPct: number;
  startedAt: string;
  finishedAt: string | null;
  error: string | null;
  request: RangeBacktestParams;
  result?: RangeBacktestResult | null;
}
