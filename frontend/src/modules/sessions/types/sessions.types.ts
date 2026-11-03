import { BaseFilter } from "../../../core/types/filter.types";

export type SessionScope = "INDEX" | "COMMODITY";
export type SessionType = "FULL_AUTO" | "SEMI_AUTO" | "MANUAL";
export type SessionStatus = "ACTIVE" | "CLOSED" | "EXPIRED";

export interface TradingSession {
  id: number;
  name: string;
  tradeDate: string;
  userId: number;
  capital: number;
  maxLossPercentage: number;
  scope: SessionScope;
  underlyings: string[];
  commodityItems: string[];
  sessionType: SessionType;
  routeThroughUpstox: boolean;
  sessionStatus: SessionStatus;
  haltReason: string | null;
  haltedAt: string | null;
  closedAt: string | null;
  status: "ACTIVE" | "DELETED";
  createdAt: string;
}

export interface TradingSessionCreatePayload {
  name?: string;
  tradeDate: string;
  userId: number;
  capital: number;
  maxLossPercentage?: number;
  scope: SessionScope;
  underlyings?: string[];
  commodityItems?: string[];
  sessionType?: SessionType;
  routeThroughUpstox?: boolean;
}

export interface TradingSessionUpdatePayload {
  name?: string;
  capital?: number;
  maxLossPercentage?: number;
  underlyings?: string[];
  commodityItems?: string[];
  sessionType?: SessionType;
  routeThroughUpstox?: boolean;
  sessionStatus?: SessionStatus;
}

export interface TradingSessionSearchFilter extends BaseFilter {
  scope?: SessionScope;
  sessionStatus?: SessionStatus;
  sessionType?: SessionType;
  userId?: number;
  tradeDate?: string;
}
