import { httpClient } from "../../../core/api/httpClient";
import { PageResult } from "../../../core/types/pagination.types";
import {
  AutopsySearchFilter,
  GuardSearchFilter,
  ScorecardSearchFilter,
  SetupGuard,
  SetupScorecard,
  TradeAutopsy,
} from "../types/learning.types";

export async function searchAutopsies(filter: AutopsySearchFilter): Promise<PageResult<TradeAutopsy>> {
  return httpClient.post("/learning/autopsies/search", filter);
}

export async function getTradeAutopsy(tradeId: number): Promise<TradeAutopsy> {
  return httpClient.get(`/learning/autopsies/trade/${tradeId}`);
}

export async function searchScorecards(filter: ScorecardSearchFilter): Promise<PageResult<SetupScorecard>> {
  return httpClient.post("/learning/scorecards/search", filter);
}

/** Resume a setup the manager's autopsy sub-agent paused (counting restarts from now). */
export async function resumeSetup(setup: string, managerCode?: string): Promise<SetupScorecard> {
  const q = managerCode ? `?managerCode=${encodeURIComponent(managerCode)}` : "";
  return httpClient.post(`/learning/scorecards/${encodeURIComponent(setup)}/resume${q}`);
}

export async function searchGuards(filter: GuardSearchFilter): Promise<PageResult<SetupGuard>> {
  return httpClient.post("/learning/guards/search", filter);
}

export async function applyGuard(id: number): Promise<SetupGuard> {
  return httpClient.post(`/learning/guards/${id}/apply`);
}

export async function rejectGuard(id: number): Promise<SetupGuard> {
  return httpClient.post(`/learning/guards/${id}/reject`);
}
