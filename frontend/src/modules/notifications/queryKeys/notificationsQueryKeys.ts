import { NotificationSearchFilter } from "../types/notifications.types";

export const notificationsQueryKeys = {
  all: ["notifications"] as const,
  list: (filter: NotificationSearchFilter) => [...notificationsQueryKeys.all, "list", filter] as const,
};
