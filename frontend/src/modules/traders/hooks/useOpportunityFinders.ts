import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { opportunityFinderApi } from "../api/opportunityFinder.api";
import { opportunityFinderQueryKeys } from "../queryKeys/opportunityFinderQueryKeys";
import { OpportunityFinderUpdate, OptionType } from "../types/opportunityFinder.types";

/** Finders (optionally only those working on `optionType`), in display order. */
export function useOpportunityFinders(optionType?: OptionType) {
  return useQuery({
    queryKey: opportunityFinderQueryKeys.list(optionType),
    queryFn: () => opportunityFinderApi.list(optionType),
    staleTime: 30000,
  });
}

/** Change a finder's markets (optionTypes) / enabled flag; every finder list refetches. */
export function useUpdateOpportunityFinder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ code, body }: { code: string; body: OpportunityFinderUpdate }) =>
      opportunityFinderApi.update(code, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: opportunityFinderQueryKeys.all }),
  });
}
