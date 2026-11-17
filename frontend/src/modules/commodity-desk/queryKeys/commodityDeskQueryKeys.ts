import { DeskDecisionFilter } from "../types/commodityDesk.types";

export const commodityDeskQueryKeys = {
  all: ["commodityDesk"] as const,
  live: () => [...commodityDeskQueryKeys.all, "live"] as const,
  latest: (hours: number) => [...commodityDeskQueryKeys.all, "latest", hours] as const,
  decisions: (filter: DeskDecisionFilter) => [...commodityDeskQueryKeys.all, "decisions", filter] as const,
};
