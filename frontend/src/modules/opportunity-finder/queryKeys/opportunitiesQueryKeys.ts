export const opportunitiesQueryKeys = {
  all: ["opportunities"] as const,
  researchTop: () => [...opportunitiesQueryKeys.all, "researchTop"] as const,
  todayMasters: () => [...opportunitiesQueryKeys.all, "todayMasters"] as const,
  latest: (underlying?: string) => [...opportunitiesQueryKeys.all, "latest", underlying ?? "all"] as const,
  masterIterations: (masterId: number) => [...opportunitiesQueryKeys.all, "masterIterations", masterId] as const,
  recentIterations: (masterId: number, limit: number) =>
    [...opportunitiesQueryKeys.all, "recentIterations", masterId, limit] as const,
  masterHistory: (masterId: number) => [...opportunitiesQueryKeys.all, "masterHistory", masterId] as const,
  chart: (code: string, timeframe = "5m") => [...opportunitiesQueryKeys.all, "chart", code, timeframe] as const,
};

