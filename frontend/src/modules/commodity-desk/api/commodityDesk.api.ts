import { httpClient } from "../../../core/api/httpClient";
import { DeskDecisionFilter, DeskDecisionPage, DeskLatest, DeskLive } from "../types/commodityDesk.types";

export const commodityDeskApi = {
  /** Newest desk decision per commodity and the sudden moves of the last `hours`. */
  async getLatest(hours = 6): Promise<DeskLatest> {
    return httpClient.get("/commodity-desk/latest", { params: { hours } });
  },

  /** What every desk and news check is doing right now. */
  async getLive(): Promise<DeskLive> {
    return httpClient.get("/commodity-desk/live");
  },

  async searchDecisions(filter: DeskDecisionFilter): Promise<DeskDecisionPage> {
    return httpClient.post("/commodity-desk/decisions/search", filter);
  },
};
