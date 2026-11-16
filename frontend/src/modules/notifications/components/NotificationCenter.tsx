import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { NOTIFICATION_STREAM_URL } from "../api/notifications.api";
import { notificationsQueryKeys } from "../queryKeys/notificationsQueryKeys";
import { getNotificationSettings } from "../hooks/notificationSettings";
import { playTone, showDesktop } from "../hooks/notifyDevice";
import { AppNotification, NotificationSeverity } from "../types/notifications.types";

const TOAST_MS = 7000;
const MAX_TOASTS = 4;
const STALE_MS = 2 * 60 * 1000; // replayed after a reconnect and older than this: recorded, not announced

const ICON: Record<NotificationSeverity, React.ReactNode> = {
  info: <Info size={15} />,
  success: <CheckCircle2 size={15} />,
  warning: <AlertTriangle size={15} />,
  danger: <XCircle size={15} />,
};

/**
 * Listens to the backend notification stream for the whole app (mounted once in the layout) and announces each
 * notification the user's settings allow: in-app toast, desktop notification, sound.
 */
export const NotificationCenter: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [toasts, setToasts] = useState<AppNotification[]>([]);
  const timers = useRef(new Map<number, number>());

  const dismiss = useCallback((id: number) => {
    setToasts((ts) => ts.filter((t) => t.id !== id));
    window.clearTimeout(timers.current.get(id));
    timers.current.delete(id);
  }, []);

  const open = useCallback((link: string) => navigate({ to: link }), [navigate]);

  useEffect(() => {
    const es = new EventSource(NOTIFICATION_STREAM_URL);
    es.addEventListener("notification", (e) => {
      let n: AppNotification;
      try {
        n = JSON.parse((e as MessageEvent<string>).data) as AppNotification;
      } catch {
        return;
      }
      queryClient.invalidateQueries({ queryKey: notificationsQueryKeys.all });
      const s = getNotificationSettings();
      if (!s.enabled || !s.kinds[n.kind]) return;
      if (Date.now() - Date.parse(n.createdAt) > STALE_MS) return;
      if (s.toast) {
        setToasts((ts) => [n, ...ts].slice(0, MAX_TOASTS));
        timers.current.set(n.id, window.setTimeout(() => dismiss(n.id), TOAST_MS));
      }
      if (s.desktop && (!s.desktopOnlyInBackground || document.hidden)) showDesktop(n, open);
      if (s.sound) playTone(n.severity);
    });
    const pending = timers.current;
    return () => {
      es.close();
      pending.forEach((t) => window.clearTimeout(t));
    };
  }, [queryClient, dismiss, open]);

  if (toasts.length === 0) return null;
  return (
    <div className="nt-stack" role="region" aria-label="Notifications" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`nt-toast nt-toast--${t.severity}`}>
          <span className="nt-toast__icon">{ICON[t.severity]}</span>
          <button
            type="button"
            className="nt-toast__main"
            onClick={() => {
              if (t.link) open(t.link);
              dismiss(t.id);
            }}
          >
            <span className="nt-toast__title">{t.title}</span>
            <span className="nt-toast__body">{t.body}</span>
          </button>
          <button type="button" className="nt-toast__close" aria-label="Dismiss" onClick={() => dismiss(t.id)}>
            <X size={13} />
          </button>
        </div>
      ))}
    </div>
  );
};

