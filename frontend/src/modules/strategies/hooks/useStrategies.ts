import {
  useMutation,
  useQuery,
  useQueryClient,
  keepPreviousData,
} from "@tanstack/react-query";
import {
  activateStrategyVersion,
  addPerformanceSnapshot,
  applyDayShift,
  checkGuardrails,
  cloneStrategy,
  createRule,
  createStrategy,
  deleteRule,
  deleteStrategy,
  evaluateStrategy,
  exportStrategies,
  getRule,
  getStrategy,
  getStrategyHealth,
  getStrategyRequirements,
  getStrategyVersion,
  importStrategies,
  overrideStrategyHealth,
  recomputeAllHealth,
  searchPerformanceSnapshots,
  searchRuleVersions,
  searchRules,
  searchStrategies,
  searchStrategyVersions,
  seedDefaults,
  updateRule,
  updateStrategy,
  updateStrategyEnabled,
  updateStrategyLifecycle,
  validateStrategyDefinition,
} from "../api/strategies.api";
import {
  rulesQueryKeys,
  strategiesQueryKeys,
} from "../queryKeys/strategiesQueryKeys";
import {
  DayShiftPayload,
  RuleCreatePayload,
  RuleFilter,
  RuleUpdatePayload,
  StrategyCreatePayload,
  StrategyFilter,
  StrategyUpdatePayload,
} from "../types/strategies.types";

// ================= Strategies Hooks =================

export function useStrategiesSearch(filter: StrategyFilter) {
  return useQuery({
    queryKey: strategiesQueryKeys.list(filter),
    queryFn: () => searchStrategies(filter),
    placeholderData: keepPreviousData,
  });
}

export function useStrategyDetail(id: number) {
  return useQuery({
    queryKey: strategiesQueryKeys.detail(id),
    queryFn: () => getStrategy(id),
    enabled: id > 0,
  });
}

export function useStrategyVersions(id: number, filter?: any) {
  return useQuery({
    queryKey: [...strategiesQueryKeys.versions(id), filter],
    queryFn: () => searchStrategyVersions(id, filter),
    enabled: id > 0,
  });
}

export function useStrategyVersion(id: number, versionNo: number) {
  return useQuery({
    queryKey: strategiesQueryKeys.version(id, versionNo),
    queryFn: () => getStrategyVersion(id, versionNo),
    enabled: id > 0 && versionNo > 0,
  });
}

export function useStrategyRequirements(id: number, versionNo: number) {
  return useQuery({
    queryKey: strategiesQueryKeys.requirements(id, versionNo),
    queryFn: () => getStrategyRequirements(id, versionNo),
    enabled: id > 0 && versionNo > 0,
  });
}

export function useCreateStrategy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: StrategyCreatePayload) => createStrategy(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: strategiesQueryKeys.lists() });
    },
  });
}

export function useUpdateStrategy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: StrategyUpdatePayload }) =>
      updateStrategy(id, payload),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: strategiesQueryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: strategiesQueryKeys.detail(data.id) });
    },
  });
}

export function useDeleteStrategy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteStrategy(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: strategiesQueryKeys.lists() });
    },
  });
}

export function useCloneStrategy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => cloneStrategy(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: strategiesQueryKeys.lists() });
    },
  });
}

export function useApplyDayShift() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: DayShiftPayload) => applyDayShift(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: strategiesQueryKeys.all });
    },
  });
}

export function useUpdateStrategyEnabled() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      updateStrategyEnabled(id, enabled),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: strategiesQueryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: strategiesQueryKeys.detail(data.id) });
    },
  });
}

export function useUpdateStrategyLifecycle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, to, reason }: { id: number; to: string; reason: string }) =>
      updateStrategyLifecycle(id, to, reason),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: strategiesQueryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: strategiesQueryKeys.detail(data.id) });
    },
  });
}

export function useActivateStrategyVersion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, versionNo }: { id: number; versionNo: number }) =>
      activateStrategyVersion(id, versionNo),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: strategiesQueryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: strategiesQueryKeys.detail(data.id) });
      queryClient.invalidateQueries({ queryKey: strategiesQueryKeys.versions(data.id) });
    },
  });
}

export function useValidateDefinition() {
  return useMutation({
    mutationFn: (definition: Record<string, any>) =>
      validateStrategyDefinition(definition),
  });
}

export function useEvaluateStrategy() {
  return useMutation({
    mutationFn: ({ versionId, context }: { versionId: number; context: Record<string, any> }) =>
      evaluateStrategy(versionId, context),
  });
}

// ================= Performance & Health Hooks =================

export function useStrategyPerformance(strategyId: number, filter?: any) {
  return useQuery({
    queryKey: [...strategiesQueryKeys.performance(strategyId), filter],
    queryFn: () => searchPerformanceSnapshots(strategyId, filter),
    enabled: strategyId > 0,
  });
}

export function useAddPerformanceSnapshot() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ strategyId, payload }: { strategyId: number; payload: any }) =>
      addPerformanceSnapshot(strategyId, payload),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({
        queryKey: strategiesQueryKeys.performance(vars.strategyId),
      });
      queryClient.invalidateQueries({
        queryKey: strategiesQueryKeys.detail(vars.strategyId),
      });
      queryClient.invalidateQueries({ queryKey: strategiesQueryKeys.lists() });
    },
  });
}

export function useStrategyHealth(strategyId: number) {
  return useQuery({
    queryKey: strategiesQueryKeys.health(strategyId),
    queryFn: () => getStrategyHealth(strategyId),
    enabled: strategyId > 0,
  });
}

export function useOverrideStrategyHealth() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      strategyId,
      payload,
    }: {
      strategyId: number;
      payload: { health: string; reason: string; until?: string };
    }) => overrideStrategyHealth(strategyId, payload),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({
        queryKey: strategiesQueryKeys.health(vars.strategyId),
      });
      queryClient.invalidateQueries({
        queryKey: strategiesQueryKeys.detail(vars.strategyId),
      });
      queryClient.invalidateQueries({ queryKey: strategiesQueryKeys.lists() });
    },
  });
}

export function useRecomputeHealth() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => recomputeAllHealth(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: strategiesQueryKeys.all });
    },
  });
}

// ================= Rules Hooks =================

export function useRulesSearch(filter: RuleFilter) {
  return useQuery({
    queryKey: rulesQueryKeys.list(filter),
    queryFn: () => searchRules(filter),
    placeholderData: keepPreviousData,
  });
}

export function useRuleDetail(id: number) {
  return useQuery({
    queryKey: rulesQueryKeys.detail(id),
    queryFn: () => getRule(id),
    enabled: id > 0,
  });
}

export function useRuleVersions(id: number) {
  return useQuery({
    queryKey: rulesQueryKeys.versions(id),
    queryFn: () => searchRuleVersions(id),
    enabled: id > 0,
  });
}

export function useCreateRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RuleCreatePayload) => createRule(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: rulesQueryKeys.lists() });
    },
  });
}

export function useUpdateRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: RuleUpdatePayload }) =>
      updateRule(id, payload),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: rulesQueryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: rulesQueryKeys.detail(data.id) });
    },
  });
}

export function useDeleteRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteRule(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: rulesQueryKeys.lists() });
    },
  });
}

export function useCheckGuardrails() {
  return useMutation({
    mutationFn: ({
      context,
      includeStale = false,
    }: {
      context: Record<string, any>;
      includeStale?: boolean;
    }) => checkGuardrails(context, includeStale),
  });
}

// ================= Imports & Seed Hooks =================

export function useSeedDefaults() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => seedDefaults(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: strategiesQueryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: rulesQueryKeys.lists() });
    },
  });
}

export function useImportStrategies() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      sourceFormat: "BUNDLE_V2" | "LEGACY_ALGO_V1";
      mode: "SKIP" | "UPDATE";
      dryRun: boolean;
      content: any;
    }) => importStrategies(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: strategiesQueryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: rulesQueryKeys.lists() });
    },
  });
}

export function useExportStrategies() {
  return useMutation({
    mutationFn: (payload: { ids?: number[]; includePerformance?: boolean }) =>
      exportStrategies(payload),
  });
}
