export const backtestQueryKeys = {
  all: ["backtest"] as const,
  run: (dates: string[], codes: string[]) =>
    [...backtestQueryKeys.all, "run", [...dates].sort(), [...codes].sort()] as const,
};
