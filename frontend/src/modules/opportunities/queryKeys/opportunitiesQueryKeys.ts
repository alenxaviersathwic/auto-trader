export const opportunitiesQueryKeys = {
  all: ["opportunities"] as const,
  researchTop: () => [...opportunitiesQueryKeys.all, "researchTop"] as const,
  todayMasters: () => [...opportunitiesQueryKeys.all, "todayMasters"] as const,
  latest: (underlying?: string) => [...opportunitiesQueryKeys.all, "latest", underlying ?? "all"] as const,
};

