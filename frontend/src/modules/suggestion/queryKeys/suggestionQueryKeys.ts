export const suggestionQueryKeys = {
  all: ["suggestion"] as const,
  researchTop: () => [...suggestionQueryKeys.all, "researchTop"] as const,
  todayMasters: () => [...suggestionQueryKeys.all, "todayMasters"] as const,
  latest: (underlying?: string) => [...suggestionQueryKeys.all, "latest", underlying ?? "all"] as const,
};
