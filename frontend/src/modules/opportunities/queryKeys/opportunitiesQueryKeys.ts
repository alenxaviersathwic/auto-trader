export const opportunitiesQueryKeys = {
  all: ["opportunities"] as const,
  researchTop: () => [...opportunitiesQueryKeys.all, "researchTop"] as const,
  todayMasters: () => [...opportunitiesQueryKeys.all, "todayMasters"] as const,
  latest: (underlying?: string) => [...opportunitiesQueryKeys.all, "latest", underlying ?? "all"] as const,
  masterIterations: (masterId: number) => [...opportunitiesQueryKeys.all, "masterIterations", masterId] as const,
  masterHistory: (masterId: number) => [...opportunitiesQueryKeys.all, "masterHistory", masterId] as const,
};

