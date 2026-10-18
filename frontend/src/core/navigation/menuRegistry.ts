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

import { Users } from "lucide-react";

export const menuRegistry = new MenuRegistry();

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
