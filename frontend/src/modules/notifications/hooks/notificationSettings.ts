import { useSyncExternalStore } from "react";
import { NotificationSettings } from "../types/notifications.types";

const KEY = "autotrader.notificationSettings";

export const DEFAULT_SETTINGS: NotificationSettings = {
  enabled: true,
  desktop: true,
  desktopOnlyInBackground: false,
  toast: true,
  sound: true,
  kinds: {
    NEW_SUGGESTION: true,
    TRADE_LOCKED: true,
    TRADE_ENTERED: true,
    EXIT_SIGNAL: true,
    TRADE_EXITED: true,
    SESSION_HALTED: true,
    LEARNING: true,
    RESEARCH: false,
  },
};

function read(): NotificationSettings {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return DEFAULT_SETTINGS;
    const saved = JSON.parse(raw) as Partial<NotificationSettings>;
    return { ...DEFAULT_SETTINGS, ...saved, kinds: { ...DEFAULT_SETTINGS.kinds, ...(saved.kinds ?? {}) } };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

let current: NotificationSettings = read();
const listeners = new Set<() => void>();

export function getNotificationSettings(): NotificationSettings {
  return current;
}

export function saveNotificationSettings(next: NotificationSettings): void {
  current = next;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // storage full or blocked: settings still apply until the page reloads
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useNotificationSettings(): NotificationSettings {
  return useSyncExternalStore(subscribe, getNotificationSettings);
}
