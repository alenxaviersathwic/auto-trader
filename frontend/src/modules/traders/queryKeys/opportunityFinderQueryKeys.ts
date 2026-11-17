import { OptionType } from "../types/opportunityFinder.types";

export const opportunityFinderQueryKeys = {
  all: ["opportunityFinders"] as const,
  list: (optionType?: OptionType) => [...opportunityFinderQueryKeys.all, "list", optionType ?? "ALL"] as const,
};
