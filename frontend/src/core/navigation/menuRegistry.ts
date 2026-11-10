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

import { Users, TrendingUp, BotMessageSquare, Sparkles, Lightbulb, CalendarClock, History, Activity } from "lucide-react";

export const menuRegistry = new MenuRegistry();

// Register Strategy & Rules unified navigation item
menuRegistry.register({
  id: "strategies-module",
  label: "Strategies & Rules",
  path: "/strategies",
  icon: TrendingUp,
  order: 1,
});

// Register Research Engine navigation item
menuRegistry.register({
  id: "research-engine",
  label: "Research Engine",
  path: "/research",
  icon: Sparkles,
  order: 3,
});

// Register Opportunities navigation item
menuRegistry.register({
  id: "opportunities-engine",
  label: "Opportunities",
  path: "/opportunities",
  icon: Lightbulb,
  order: 4,
});

// Register Trading Sessions navigation item
menuRegistry.register({
  id: "trading-sessions",
  label: "Sessions",
  path: "/sessions",
  icon: CalendarClock,
  order: 2,
});

// Register Active Trader navigation item
menuRegistry.register({
  id: "active-trader",
  label: "Active Trader",
  path: "/trades",
  icon: Activity,
  order: 2.5,
});

// Register Backtest navigation item
menuRegistry.register({
  id: "backtest",
  label: "Backtest",
  path: "/backtest",
  icon: History,
  order: 6,
});

// Register AI Master chat navigation item
menuRegistry.register({
  id: "master-chat",
  label: "AI Master",
  path: "/master",
  icon: BotMessageSquare,
  order: 5,
});

// Register Users Module navigation item
menuRegistry.register({
  id: "users-settings",
  label: "Users & Accounts",
  path: "/settings/users",
  icon: Users,
  order: 10,
});

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
