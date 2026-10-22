import { RuleFilter, StrategyFilter } from "../types/strategies.types";

export const strategiesQueryKeys = {
  all: ["strategies"] as const,
  lists: () => [...strategiesQueryKeys.all, "list"] as const,
  list: (filter: StrategyFilter) => [...strategiesQueryKeys.lists(), filter] as const,
  details: () => [...strategiesQueryKeys.all, "detail"] as const,
  detail: (id: number) => [...strategiesQueryKeys.details(), id] as const,
  versions: (id: number) => [...strategiesQueryKeys.detail(id), "versions"] as const,
  version: (id: number, versionNo: number) =>
    [...strategiesQueryKeys.versions(id), versionNo] as const,
  requirements: (id: number, versionNo: number) =>
    [...strategiesQueryKeys.versions(id), versionNo, "requirements"] as const,
  performance: (id: number) => [...strategiesQueryKeys.detail(id), "performance"] as const,
  health: (id: number) => [...strategiesQueryKeys.detail(id), "health"] as const,
};

export const rulesQueryKeys = {
  all: ["rules"] as const,
  lists: () => [...rulesQueryKeys.all, "list"] as const,
  list: (filter: RuleFilter) => [...rulesQueryKeys.lists(), filter] as const,
  details: () => [...rulesQueryKeys.all, "detail"] as const,
  detail: (id: number) => [...rulesQueryKeys.details(), id] as const,
  versions: (id: number) => [...rulesQueryKeys.detail(id), "versions"] as const,
};

