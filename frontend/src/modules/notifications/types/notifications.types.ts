import { BaseFilter } from "../../../core/types/filter.types";

export type NotificationKind =
  | "NEW_SUGGESTION"
  | "TRADE_LOCKED"
  | "TRADE_ENTERED"
  | "EXIT_SIGNAL"
  | "TRADE_EXITED"
  | "SESSION_HALTED"
  | "LEARNING"
  | "RESEARCH"
  | "MARKET_MOVE";

export type NotificationSeverity = "info" | "success" | "warning" | "danger";

/** One notification from the backend hub (modules/notifications). */
export interface AppNotification {
  id: number;
  kind: NotificationKind;
  title: string;
  body: string;
  severity: NotificationSeverity;
  sessionId: number | null;
  tradeId: number | null;
  link: string | null;
  data: Record<string, unknown>;
  createdAt: string;
}

export interface NotificationSearchFilter extends BaseFilter {
  kind?: NotificationKind;
  sessionId?: number;
  afterId?: number;
}

/** What to show and how; kept in this browser (desktop permission is per browser too). */
export interface NotificationSettings {
  enabled: boolean;
  desktop: boolean;
  /** Desktop notifications only while this tab is in the background (toasts still show). */
  desktopOnlyInBackground: boolean;
  toast: boolean;
  sound: boolean;
  kinds: Record<NotificationKind, boolean>;
}
