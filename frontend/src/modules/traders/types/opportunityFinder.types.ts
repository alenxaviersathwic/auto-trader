import { TraderCode } from "../../trade-history/types/trades.types";

/** Markets a finder works on. INDEX finders read mostly national drivers, COMMODITY finders international ones. */
export type OptionType = "INDEX" | "COMMODITY";
export const OPTION_TYPES: OptionType[] = ["INDEX", "COMMODITY"];

/** One opportunity finder (a "trader" in the UI). Every finder has this same shape; only strategy and method differ. */
export interface OpportunityFinder {
  id: number;
  code: TraderCode;
  name: string;
  shortLabel: string;
  badgeColor: string;
  optionTypes: OptionType[];
  methodology: string;
  entryLogic: string;
  trailLogic: string;
  strategies: string[];
  checks: string[];
  drivers: string;
  liveOnly: boolean;
  enabled: boolean;
  sortOrder: number;
  status: string;
  createdAt: string;
}

export interface OpportunityFinderUpdate {
  optionTypes?: OptionType[];
  enabled?: boolean;
  name?: string;
}
