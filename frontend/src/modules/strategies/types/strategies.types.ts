import { BaseEntity } from "../../../core/types/baseEntity.types";
import { BaseFilter } from "../../../core/types/filter.types";

export type StrategyCategory =
  | "MOMENTUM"
  | "BREAKOUT"
  | "TREND"
  | "REVERSAL"
  | "VWAP"
  | "PREMIUM_SELLING"
  | "VOLATILITY"
  | "OI_BASED"
  | "EVENT"
  | "OTHER";

export type StrategyStructure =
  | "SINGLE_LONG"
  | "BULL_PUT_SPREAD"
  | "BEAR_CALL_SPREAD"
  | "IRON_CONDOR"
  | "SHORT_STRANGLE"
  | "CUSTOM_MULTI_LEG"
  | "MIXED";

export type StrategyBias = "BULLISH" | "BEARISH" | "NEUTRAL" | "DYNAMIC";
export type OptionSide = "CALL" | "PUT" | "BOTH";
export type UnderlyingType = "INDEX" | "COMMODITY";
export type Exchange = "NSE" | "BSE" | "MCX";
export type TradingMode = "INTRADAY" | "SHORT_TERM" | "POSITIONAL";
export type ExecutionMode = "PAPER" | "LIVE";
export type DefinitionFormat = "RULE_TREE" | "EVALUATOR" | "SUMMARY";
export type LifecycleStatus = "DRAFT" | "IN_REVIEW" | "ACTIVE" | "SUSPENDED" | "ARCHIVED";
export type HealthStatus = "HEALTHY" | "DEGRADED" | "SUSPENDED" | "UNKNOWN";
export type ValidationStatus = "UNTESTED" | "PAPER_TESTING" | "BACKTESTED" | "LIVE_VALIDATED" | "REJECTED";

export type RuleKind = "GUARDRAIL" | "CONDITION_BLOCK";
export type RuleType =
  | "MARKET_REGIME"
  | "CAPITAL"
  | "DIRECTION_PREFERENCE"
  | "TIME"
  | "LIQUIDITY"
  | "RISK"
  | "ENTRY"
  | "EXIT"
  | "FILTER";
export type RuleAction = "PREFER" | "AVOID" | "WATCH" | "REQUIRE" | "BLOCK";
export type PriorityLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type RegistryType =
  | "INDICATOR"
  | "OPERATOR"
  | "OPERAND_SOURCE"
  | "STRIKE_SELECTOR"
  | "STOP_TYPE"
  | "TARGET_TYPE"
  | "TRAIL_TYPE"
  | "EXPIRY_CYCLE"
  | "LEG_ACTION"
  | "ADJUSTMENT_ACTION"
  | "STRUCTURE"
  | "EVALUATOR"
  | "MARKET";

export type RegistryKind = "BUILT_IN" | "DERIVED" | "CUSTOM";

export interface RegistryItem extends BaseEntity {
  registryType: string;
  code: string;
  name: string;
  kind: RegistryKind;
  version: number;
  schema?: Record<string, any> | null;
  expression?: Record<string, any> | null;
  handlerKey?: string | null;
  executable: boolean;
  requires?: string[] | null;
  description?: string | null;
  enabled: boolean;
}

export interface RegistryFilter extends BaseFilter {
  registryType?: string;
  kind?: string;
  executable?: boolean;
  enabled?: boolean;
}

export interface RegistryCreatePayload {
  registryType: string;
  code: string;
  name: string;
  kind?: string;
  schema?: Record<string, any>;
  expression?: Record<string, any>;
  handlerKey?: string;
  requires?: string[];
  description?: string;
  enabled?: boolean;
}

export interface RegistryUpdatePayload {
  name?: string;
  schema?: Record<string, any>;
  expression?: Record<string, any>;
  handlerKey?: string;
  requires?: string[];
  description?: string;
  enabled?: boolean;
}

export interface StrategyVersion extends BaseEntity {
  strategyId: number;
  versionNo: number;
  schemaVersion: number;
  definition: Record<string, any>;
  contentHash: string;
  changeNote?: string | null;
}

export interface StrategyRuleLink extends BaseEntity {
  strategyVersionId: number;
  ruleId: number;
  role: string;
  required: boolean;
  weight: number;
  sortOrder: number;
  paramOverrides?: Record<string, any> | null;
}

export interface PerformanceSnapshot extends BaseEntity {
  strategyId: number;
  versionNo?: number | null;
  source: "LEGACY_IMPORT" | "PAPER" | "LIVE" | "BACKTEST";
  domain: "PAPER" | "LIVE" | "UNKNOWN";
  periodFrom?: string | null;
  periodTo?: string | null;
  asOf?: string | null;
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  winRatePct: number;
  netPnl: number;
  profitFactor: number;
  maxDrawdown: number;
  legacyHealth?: string | null;
  reliabilityFlags?: string[] | null;
}

export interface HealthEvent extends BaseEntity {
  strategyId: number;
  fromHealth: HealthStatus;
  toHealth: HealthStatus;
  reason: string;
  snapshotId?: number | null;
  triggeredBy: "POLICY" | "MANUAL";
}

export interface HealthPolicy extends BaseEntity {
  code: string;
  name: string;
  scope: any;
  params: {
    minTrades?: number;
    window?: number;
    suspendIfProfitFactorBelow?: number;
    degradeIfProfitFactorBelow?: number;
    suspendIfDrawdownAbove?: number;
    suspendAfterConsecutiveLosses?: number;
    [key: string]: any;
  };
  enabled: boolean;
}

export interface HealthDetails {
  strategyId: number;
  health: HealthStatus;
  effectiveHealth: HealthStatus;
  healthOverride?: HealthStatus | null;
  healthOverrideReason?: string | null;
  healthOverrideUntil?: string | null;
  policyUsed?: Record<string, any> | null;
  recentEvents: HealthEvent[];
}

export interface Strategy extends BaseEntity {
  code: string;
  name: string;
  description?: string | null;
  category: StrategyCategory | string;
  structure?: StrategyStructure | string | null;
  bias?: StrategyBias | string | null;
  optionSide?: OptionSide | string | null;
  markets: string[];
  underlyingTypes: UnderlyingType[] | string[];
  exchange?: Exchange | string | null;
  tradingModes: TradingMode[] | string[];
  executionModes: ExecutionMode[] | string[];
  timeframe?: string | null;
  definitionFormat: DefinitionFormat | string;
  executable: boolean;
  lifecycleStatus: LifecycleStatus | string;
  health: HealthStatus | string;
  healthOverride?: HealthStatus | string | null;
  healthOverrideReason?: string | null;
  healthOverrideUntil?: string | null;
  validationStatus: ValidationStatus | string;
  enabled: boolean;
  riskProfile?: Record<string, any> | null;
  references?: Array<{ title: string; url: string; scope: string }> | null;
  riskNotes?: string[] | null;
  howItWorks?: Array<{ title: string; description: string }> | null;
  tags?: string[] | null;
  attributes?: Record<string, any> | null;
  provenance?: Record<string, any> | null;
  reviewFlags?: string[] | null;
  currentVersionId?: number | null;
  // Computed on read:
  suggestable?: boolean;
  effectiveHealth?: HealthStatus | string;
  currentVersion?: StrategyVersion | null;
  latestPerformance?: PerformanceSnapshot[] | null;
}

export interface StrategyFilter extends BaseFilter {
  category?: string;
  structure?: string;
  bias?: string;
  optionSide?: string;
  market?: string;
  underlyingType?: string;
  exchange?: string;
  tradingMode?: string;
  executionMode?: string;
  lifecycleStatus?: string;
  health?: string;
  validationStatus?: string;
  definitionFormat?: string;
  executable?: boolean;
  suggestable?: boolean;
  hasReviewFlags?: boolean;
  tag?: string;
  source?: string;
}

export interface StrategyCreatePayload {
  code: string;
  name: string;
  description?: string;
  category: string;
  structure?: string;
  bias?: string;
  optionSide?: string;
  markets: string[];
  underlyingTypes?: string[];
  exchange?: string;
  tradingModes?: string[];
  executionModes?: string[];
  timeframe?: string;
  definitionFormat?: string;
  riskProfile?: Record<string, any>;
  references?: Array<{ title: string; url: string; scope: string }>;
  riskNotes?: string[];
  howItWorks?: Array<{ title: string; description: string }>;
  tags?: string[];
  attributes?: Record<string, any>;
  definition: Record<string, any>;
  changeNote?: string;
}

export interface StrategyUpdatePayload {
  name?: string;
  description?: string;
  category?: string;
  structure?: string;
  bias?: string;
  optionSide?: string;
  markets?: string[];
  underlyingTypes?: string[];
  exchange?: string;
  tradingModes?: string[];
  executionModes?: string[];
  timeframe?: string;
  riskProfile?: Record<string, any>;
  references?: Array<{ title: string; url: string; scope: string }>;
  riskNotes?: string[];
  howItWorks?: Array<{ title: string; description: string }>;
  tags?: string[];
  attributes?: Record<string, any>;
  definition?: Record<string, any>;
  changeNote?: string;
}

export interface RuleVersion extends BaseEntity {
  ruleId: number;
  versionNo: number;
  content: {
    when?: Record<string, any>;
    unless?: Record<string, any>;
    require?: Record<string, any>;
    parameters?: Record<string, any>;
    effect?: Record<string, any> | null;
    [key: string]: any;
  };
  changeNote?: string | null;
}

export interface Rule extends BaseEntity {
  code: string;
  name: string;
  ruleKind: RuleKind;
  ruleType: RuleType | string;
  action?: RuleAction | string | null;
  priority: PriorityLevel;
  appliesTo: {
    markets?: string[];
    optionSides?: string[];
    tradingModes?: string[];
    executionDomains?: string[];
    strategyCodes?: string[];
    structures?: string[];
    [key: string]: any;
  };
  conditionText: string;
  currentVersionId?: number | null;
  evidence?: {
    count?: number;
    successRatePct?: number;
    failureRatePct?: number;
    justification?: string;
    window?: string;
    [key: string]: any;
  } | null;
  reviewBy?: string | null;
  executable: boolean;
  reviewFlags?: string[] | null;
  provenance?: Record<string, any> | null;
  enabled: boolean;
  isStale?: boolean;
  currentVersion?: RuleVersion | null;
  usedByStrategies?: Array<{ id: number; code: string; name: string }>;
}

export interface RuleFilter extends BaseFilter {
  ruleKind?: string;
  ruleType?: string;
  action?: string;
  priority?: string;
  market?: string;
  optionSide?: string;
  executionDomain?: string;
  executable?: boolean;
  stale?: boolean;
  enabled?: boolean;
}

export interface RuleCreatePayload {
  code: string;
  name: string;
  ruleKind: RuleKind;
  ruleType: string;
  action?: string;
  priority: PriorityLevel;
  appliesTo: Record<string, any>;
  conditionText: string;
  evidence?: Record<string, any>;
  reviewBy?: string;
  enabled?: boolean;
  content: Record<string, any>;
  changeNote?: string;
}

export interface RuleUpdatePayload {
  name?: string;
  ruleType?: string;
  action?: string;
  priority?: PriorityLevel;
  appliesTo?: Record<string, any>;
  conditionText?: string;
  evidence?: Record<string, any>;
  reviewBy?: string;
  enabled?: boolean;
  content?: Record<string, any>;
  changeNote?: string;
}

export interface GuardrailCheckResult {
  ruleCode: string;
  ruleName: string;
  action: string;
  priority: string;
  message: string;
  met: boolean;
  whenMet: boolean;
  unlessMet: boolean;
  requireMet: boolean;
}

export interface GuardrailCheckResponse {
  results: GuardrailCheckResult[];
  hasBlock: boolean;
  hasAvoid: boolean;
}

export interface ValidationIssue {
  path: string;
  message: string;
  severity: "ERROR" | "WARNING";
}

export interface ValidationResult {
  valid: boolean;
  executable: boolean;
  issues: ValidationIssue[];
}

export interface EvaluateResult {
  entryMet: boolean;
  exitMet: boolean;
  activeCaseKey?: string | null;
  conditions: Array<{
    path: string;
    condition: string;
    passed: boolean;
    leftValue?: any;
    rightValue?: any;
  }>;
  adjustments: Array<{
    key: string;
    whenMet: boolean;
    actions: any[];
  }>;
  targetLegs: any[];
}

export interface ImportBatch extends BaseEntity {
  fileName: string;
  sourceFormat: "BUNDLE_V2" | "LEGACY_ALGO_V1";
  mode: "SKIP" | "UPDATE";
  dryRun: boolean;
  totalItems: number;
  createdCount: number;
  updatedCount: number;
  skippedCount: number;
  failedCount: number;
  errors?: Array<{ index: number; code: string; message: string }> | null;
  warnings?: Array<any> | null;
}
