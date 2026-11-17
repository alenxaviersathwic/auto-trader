import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { commodityDeskApi } from "../api/commodityDesk.api";
import { commodityDeskQueryKeys } from "../queryKeys/commodityDeskQueryKeys";
import { DeskDecisionFilter } from "../types/commodityDesk.types";

/** The desk's newest decision per commodity + recent sudden moves; refreshed while the page is open. */
export function useDeskLatest(hours = 6, refetchMs = 15000) {
  return useQuery({
    queryKey: commodityDeskQueryKeys.latest(hours),
    queryFn: () => commodityDeskApi.getLatest(hours),
    refetchInterval: refetchMs,
  });
}

export function useDeskDecisions(filter: DeskDecisionFilter, enabled = true) {
  return useQuery({
    queryKey: commodityDeskQueryKeys.decisions(filter),
    queryFn: () => commodityDeskApi.searchDecisions(filter),
    placeholderData: keepPreviousData,
    enabled,
  });
}

/** Live agent status, polled fast so the working flow animates in step with the backend. */
export function useDeskLive(refetchMs = 2000) {
  return useQuery({
    queryKey: commodityDeskQueryKeys.live(),
    queryFn: () => commodityDeskApi.getLive(),
    refetchInterval: refetchMs,
  });
}
