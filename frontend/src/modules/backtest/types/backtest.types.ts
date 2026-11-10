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
