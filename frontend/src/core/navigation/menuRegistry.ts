import React from "react";

export interface MenuItem {
  id: string;
  label: string;
  path: string;
  icon?: React.ComponentType<{ className?: string }>;
  order?: number;
  badge?: string;
}

class MenuRegistry {
  private items: Map<string, MenuItem> = new Map();
  private listeners: Set<() => void> = new Set();

  register(item: MenuItem): void {
    this.items.set(item.id, item);
    this.notify();
  }

  unregister(id: string): void {
    if (this.items.delete(id)) {
      this.notify();
    }
  }

  getAll(): MenuItem[] {
    return Array.from(this.items.values()).sort(
      (a, b) => (a.order ?? 100) - (b.order ?? 100)
    );
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify(): void {
    for (const listener of this.listeners) {
      listener();
    }
  }
}

import { Users, TrendingUp, BotMessageSquare, Sparkles, History, Activity, Bell, House, Bot } from "lucide-react";

export const menuRegistry = new MenuRegistry();

// Menu, in trading order: Sessions is the home page ("/" opens it), then who trades, then research and testing,
// then records and settings.
menuRegistry.register({ id: "trading-sessions", label: "Sessions", path: "/sessions", icon: House, order: 1 });
// The two opportunity traders and the session managers that run them (two tabs)
menuRegistry.register({ id: "traders", label: "Traders", path: "/traders", icon: Bot, order: 2 });
menuRegistry.register({ id: "research-engine", label: "Research Engine", path: "/research", icon: Sparkles, order: 3 });
menuRegistry.register({ id: "backtest", label: "Backtest", path: "/backtest", icon: History, order: 4 });
// Trade history: every trade and its autopsy (trading itself happens on the session screen)
menuRegistry.register({ id: "active-trader", label: "Trade history", path: "/trades", icon: Activity, order: 5 });
menuRegistry.register({ id: "strategies-module", label: "Strategies & Rules", path: "/strategies", icon: TrendingUp, order: 6 });
menuRegistry.register({ id: "master-chat", label: "AI Master", path: "/master", icon: BotMessageSquare, order: 7 });
// Notification settings: which events alert you, and how
menuRegistry.register({ id: "notification-settings", label: "Notifications", path: "/settings/notifications", icon: Bell, order: 9 });
menuRegistry.register({ id: "users-settings", label: "Users & Accounts", path: "/settings/users", icon: Users, order: 10 });

/**
 * React hook to access registered menu items dynamically.
 */
export function useMenuItems(): MenuItem[] {
  const [items, setItems] = React.useState<MenuItem[]>(() => menuRegistry.getAll());

  React.useEffect(() => {
    return menuRegistry.subscribe(() => {
      setItems(menuRegistry.getAll());
    });
  }, []);

  return items;
}
