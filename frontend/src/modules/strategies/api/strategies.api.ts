import { httpClient } from "../../../core/api/httpClient";
import { PageResult } from "../../../core/types/pagination.types";
import {
  EvaluateResult,
  GuardrailCheckResponse,
  HealthDetails,
  ImportBatch,
  PerformanceSnapshot,
  Rule,
  RuleCreatePayload,
  RuleFilter,
  RuleUpdatePayload,
  RuleVersion,
  Strategy,
  StrategyCreatePayload,
  StrategyFilter,
  StrategyUpdatePayload,
  StrategyVersion,
  ValidationResult,
} from "../types/strategies.types";

// ================= Strategies API =================

export async function searchStrategies(
  filter: StrategyFilter
): Promise<PageResult<Strategy>> {
  return httpClient.post("/strategies/search", filter);
}

export async function getStrategy(id: number): Promise<Strategy> {
  return httpClient.get(`/strategies/${id}`);
}

export async function createStrategy(
  payload: StrategyCreatePayload
): Promise<Strategy> {
  return httpClient.post("/strategies", payload);
}

export async function updateStrategy(
  id: number,
  payload: StrategyUpdatePayload
): Promise<Strategy> {
  return httpClient.put(`/strategies/${id}`, payload);
}

export async function deleteStrategy(id: number): Promise<void> {
  return httpClient.delete(`/strategies/${id}`);
}

export async function cloneStrategy(id: number): Promise<Strategy> {
  return httpClient.post(`/strategies/${id}/clone`);
}

export async function updateStrategyEnabled(
  id: number,
  enabled: boolean
): Promise<Strategy> {
  return httpClient.patch(`/strategies/${id}/enabled`, { enabled });
}

export async function updateStrategyLifecycle(
  id: number,
  to: string,
  reason: string
): Promise<Strategy> {
  return httpClient.patch(`/strategies/${id}/lifecycle`, { to, reason });
}

export async function searchStrategyVersions(
  id: number,
  filter: any = { page: 0, limit: 20 }
): Promise<PageResult<StrategyVersion>> {
  return httpClient.post(`/strategies/${id}/versions/search`, filter);
}

export async function getStrategyVersion(
  id: number,
  versionNo: number
): Promise<StrategyVersion> {
  return httpClient.get(`/strategies/${id}/versions/${versionNo}`);
}

export async function activateStrategyVersion(
  id: number,
  versionNo: number
): Promise<Strategy> {
  return httpClient.post(`/strategies/${id}/versions/${versionNo}/activate`);
}

export async function getStrategyRequirements(
  id: number,
  versionNo: number
): Promise<{ versionNo: number; operands: any[] }> {
  return httpClient.get(`/strategies/${id}/versions/${versionNo}/requirements`);
}

export async function validateStrategyDefinition(
  definition: Record<string, any>
): Promise<ValidationResult> {
  return httpClient.post("/strategies/validate", { definition });
}

export async function evaluateStrategy(
  versionId: number,
  context: Record<string, any>
): Promise<EvaluateResult> {
  return httpClient.post("/strategies/evaluate", { versionId, context });
}

// ================= Performance & Health API =================

export async function searchPerformanceSnapshots(
  strategyId: number,
  filter: any = { page: 0, limit: 20 }
): Promise<PageResult<PerformanceSnapshot>> {
  return httpClient.post(`/strategies/${strategyId}/performance/search`, filter);
}

export async function addPerformanceSnapshot(
  strategyId: number,
  payload: any
): Promise<PerformanceSnapshot> {
  return httpClient.post(`/strategies/${strategyId}/performance`, payload);
}

export async function getStrategyHealth(id: number): Promise<HealthDetails> {
  return httpClient.get(`/strategies/${id}/health`);
}

export async function overrideStrategyHealth(
  id: number,
  payload: { health: string; reason: string; until?: string }
): Promise<HealthDetails> {
  return httpClient.post(`/strategies/${id}/health/override`, payload);
}

export async function recomputeAllHealth(): Promise<{
  recomputedCount: number;
  changedCount: number;
  details: any[];
}> {
  return httpClient.post("/strategies/health/recompute");
}

// ================= Rules API =================

export async function searchRules(filter: RuleFilter): Promise<PageResult<Rule>> {
  return httpClient.post("/rules/search", filter);
}

export async function getRule(id: number): Promise<Rule> {
  return httpClient.get(`/rules/${id}`);
}

export async function createRule(payload: RuleCreatePayload): Promise<Rule> {
  return httpClient.post("/rules", payload);
}

export async function updateRule(
  id: number,
  payload: RuleUpdatePayload
): Promise<Rule> {
  return httpClient.put(`/rules/${id}`, payload);
}

export async function deleteRule(id: number): Promise<void> {
  return httpClient.delete(`/rules/${id}`);
}

export async function searchRuleVersions(
  id: number,
  filter: any = { page: 0, limit: 20 }
): Promise<PageResult<RuleVersion>> {
  return httpClient.post(`/rules/${id}/versions/search`, filter);
}

export async function checkGuardrails(
  context: Record<string, any>,
  includeStale: boolean = false
): Promise<GuardrailCheckResponse> {
  return httpClient.post("/rules/check", { context, includeStale });
}

// ================= Strategy Utilities (Seeds, Import, Export) =================

export async function seedDefaults(): Promise<{
  registriesCreated: number;
  healthPoliciesCreated: number;
  strategiesCreated: number;
  rulesCreated: number;
}> {
  return httpClient.post("/strategies/seed-defaults");
}

export async function importStrategies(payload: {
  sourceFormat: "BUNDLE_V2" | "LEGACY_ALGO_V1";
  mode: "SKIP" | "UPDATE";
  dryRun: boolean;
  content: any;
}): Promise<ImportBatch> {
  return httpClient.post("/strategies/import", payload);
}

export async function exportStrategies(payload: {
  ids?: number[];
  includePerformance?: boolean;
}): Promise<any> {
  return httpClient.post("/strategies/export", payload);
}

