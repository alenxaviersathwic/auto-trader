export const backtestQueryKeys = {
  all: ["backtest"] as const,
  run: (dates: string[], codes: string[]) =>
    [...backtestQueryKeys.all, "run", [...dates].sort(), [...codes].sort()] as const,
  rangeJob: (jobId: string) => [...backtestQueryKeys.all, "range", jobId] as const,
};
