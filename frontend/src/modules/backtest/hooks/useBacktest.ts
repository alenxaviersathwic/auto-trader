import { useMutation, useQuery } from "@tanstack/react-query";
import { backtestApi } from "../api/backtest.api";
import { backtestQueryKeys } from "../queryKeys/backtestQueryKeys";
import { RangeBacktestParams, RunBacktestParams } from "../types/backtest.types";

/** Triggers one backtest run (POST /api/v1/backtest/run). An action, not a cached read -- the
 * same date/index combination can mean a different result once the Upstox candle cache updates,
 * so this is a mutation rather than a useQuery the page would otherwise treat as stable. */
export function useRunBacktest() {
  return useMutation({
    mutationFn: (params: RunBacktestParams) => backtestApi.run(params),
  });
}

/** Starts a FROM-TO range backtest job (POST /api/v1/backtest/range). */
export function useStartRangeBacktest() {
  return useMutation({
    mutationFn: (params: RangeBacktestParams) => backtestApi.startRange(params),
  });
}

/** Polls a range backtest job every 2 s while it is RUNNING; stops once DONE or FAILED. */
export function useRangeBacktestJob(jobId: string | null) {
  return useQuery({
    queryKey: backtestQueryKeys.rangeJob(jobId ?? "none"),
    queryFn: () => backtestApi.rangeStatus(jobId as string),
    enabled: !!jobId,
    refetchInterval: (q) => (q.state.data?.state === "RUNNING" || !q.state.data ? 2000 : false),
  });
}
