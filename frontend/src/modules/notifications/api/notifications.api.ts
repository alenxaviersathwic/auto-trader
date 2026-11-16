import { httpClient } from "../../../core/api/httpClient";
import { PageResult } from "../../../core/types/pagination.types";
import { AppNotification, NotificationSearchFilter } from "../types/notifications.types";

/** Recent notifications kept by the backend hub (in memory, newest first by default). */
export async function searchNotifications(filter: NotificationSearchFilter): Promise<PageResult<AppNotification>> {
  return httpClient.post("/notifications/search", filter);
}

/** SSE endpoint the notification center listens on. */
export const NOTIFICATION_STREAM_URL = "/api/v1/notifications/stream";
