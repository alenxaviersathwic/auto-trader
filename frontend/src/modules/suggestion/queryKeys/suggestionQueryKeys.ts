export const suggestionQueryKeys = {
  all: ["suggestion"] as const,
  runStatus: () => [...suggestionQueryKeys.all, "runStatus"] as const,
  underlyings: () => [...suggestionQueryKeys.all, "underlyings"] as const,
  latest: (underlying?: string) => [...suggestionQueryKeys.all, "latest", underlying ?? "all"] as const,
};
