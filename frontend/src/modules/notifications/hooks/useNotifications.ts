import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { searchNotifications } from "../api/notifications.api";
import { notificationsQueryKeys } from "../queryKeys/notificationsQueryKeys";
import { NotificationSearchFilter } from "../types/notifications.types";

export function useRecentNotifications(filter: NotificationSearchFilter, refetchIntervalMs = 10000) {
  return useQuery({
    queryKey: notificationsQueryKeys.list(filter),
    queryFn: () => searchNotifications(filter),
    placeholderData: keepPreviousData,
    refetchInterval: refetchIntervalMs,
  });
}
