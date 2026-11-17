import { httpClient } from "../../../core/api/httpClient";
import { OpportunityFinder, OpportunityFinderUpdate, OptionType } from "../types/opportunityFinder.types";

export const opportunityFinderApi = {
  /** All finders, or only those that work on one market. */
  async list(optionType?: OptionType): Promise<OpportunityFinder[]> {
    return httpClient.get("/opportunity-finders", { params: optionType ? { optionType } : {} });
  },

  async update(code: string, body: OpportunityFinderUpdate): Promise<OpportunityFinder> {
    return httpClient.put(`/opportunity-finders/${code}`, body);
  },
};
