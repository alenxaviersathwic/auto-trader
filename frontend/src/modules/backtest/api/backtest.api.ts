import { httpClient } from "../../../core/api/httpClient";
import { BacktestRunResult, RunBacktestParams } from "../types/backtest.types";

/** One run replays the live engine, minute by minute, over real Upstox candles for every date x
 * index picked -- can take a few seconds per date x index, so give it real room. */
const RUN_TIMEOUT_MS = 3 * 60 * 1000;

export const backtestApi = {
  async run(params: RunBacktestParams): Promise<BacktestRunResult> {
    return httpClient.post("/backtest/run", params, { timeout: RUN_TIMEOUT_MS });
  },
};
