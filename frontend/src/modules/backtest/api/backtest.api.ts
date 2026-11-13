import { httpClient } from "../../../core/api/httpClient";
import {
  BacktestRunResult,
  RangeBacktestJob,
  RangeBacktestParams,
  RunBacktestParams,
} from "../types/backtest.types";

/** One run replays the live engine, minute by minute, over real Upstox candles for every date x
 * index picked -- can take a few seconds per date x index, so give it real room. */
const RUN_TIMEOUT_MS = 3 * 60 * 1000;

export const backtestApi = {
  async run(params: RunBacktestParams): Promise<BacktestRunResult> {
    return httpClient.post("/backtest/run", params, { timeout: RUN_TIMEOUT_MS });
  },
  /** Starts a FROM-TO backtest in the background; returns the job (poll rangeStatus for progress + result). */
  async startRange(params: RangeBacktestParams): Promise<RangeBacktestJob> {
    return httpClient.post("/backtest/range", params);
  },
  async rangeStatus(jobId: string): Promise<RangeBacktestJob> {
    return httpClient.get(`/backtest/range/${jobId}`);
  },
};
