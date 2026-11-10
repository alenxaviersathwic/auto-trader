import { useMutation } from "@tanstack/react-query";
import { backtestApi } from "../api/backtest.api";
import { RunBacktestParams } from "../types/backtest.types";

/** Triggers one backtest run (POST /api/v1/backtest/run). An action, not a cached read -- the
 * same date/index combination can mean a different result once the Upstox candle cache updates,
 * so this is a mutation rather than a useQuery the page would otherwise treat as stable. */
export function useRunBacktest() {
  return useMutation({
    mutationFn: (params: RunBacktestParams) => backtestApi.run(params),
  });
}
