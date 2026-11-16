import { AutopsySearchFilter, GuardSearchFilter, ScorecardSearchFilter } from "../types/learning.types";

export const learningQueryKeys = {
  all: ["learning"] as const,
  autopsies: () => [...learningQueryKeys.all, "autopsies"] as const,
  autopsyList: (filter: AutopsySearchFilter) => [...learningQueryKeys.autopsies(), filter] as const,
  tradeAutopsy: (tradeId: number) => [...learningQueryKeys.autopsies(), "trade", tradeId] as const,
  scorecards: () => [...learningQueryKeys.all, "scorecards"] as const,
  scorecardList: (filter: ScorecardSearchFilter) => [...learningQueryKeys.scorecards(), filter] as const,
  guards: () => [...learningQueryKeys.all, "guards"] as const,
  guardList: (filter: GuardSearchFilter) => [...learningQueryKeys.guards(), filter] as const,
};
