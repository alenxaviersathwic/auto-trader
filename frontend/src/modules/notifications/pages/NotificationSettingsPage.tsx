import React, { useState } from "react";
import { Bell, BellOff, Send } from "lucide-react";
import { saveNotificationSettings, useNotificationSettings } from "../hooks/notificationSettings";
import { desktopPermission, playTone, requestDesktopPermission, showDesktop } from "../hooks/notifyDevice";
import { useRecentNotifications } from "../hooks/useNotifications";
import { KIND_META, KIND_ORDER } from "../types/notificationMeta";
import { AppNotification, NotificationSettings } from "../types/notifications.types";

const hms = (iso: string): string =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false });

const Toggle: React.FC<{ on: boolean; label: string; disabled?: boolean; onChange: (on: boolean) => void }> = ({
  on,
  label,
  disabled,
  onChange,
}) => (
  <button
    type="button"
    className={`desk-switch ${on ? "desk-switch--on" : ""}`}
    role="switch"
    aria-checked={on}
    aria-label={label}
    disabled={disabled}
    onClick={() => onChange(!on)}
  >
    <span className="desk-switch__track">
      <span className="desk-switch__thumb" />
    </span>
    <span className="micro">{on ? "ON" : "OFF"}</span>
  </button>
);

/** Settings > Notifications: which events alert you, and how (desktop, in-app, sound). */
export const NotificationSettingsPage: React.FC = () => {
  const s = useNotificationSettings();
  const [permission, setPermission] = useState(desktopPermission());
  const recent = useRecentNotifications({ page: 0, limit: 15, sortBy: "createdAt", sortDir: "desc" });
  const set = (patch: Partial<NotificationSettings>) => saveNotificationSettings({ ...s, ...patch });
  const off = !s.enabled;

  const sendTest = () => {
    const n: AppNotification = {
      id: 0, kind: "TRADE_EXITED", title: "Test notification", body: "This is how a trade alert looks.",
      severity: "success", sessionId: null, tradeId: null, link: null, data: {}, createdAt: new Date().toISOString(),
    };
    if (s.desktop) showDesktop(n, () => undefined);
    if (s.sound) playTone("success");
  };

  return (
    <div className="te-desk nt-page">
      <header className="te-head">
        <div className="te-head__left">
          <h1 className="page-title">Notifications</h1>
          <span className="micro text-muted">Saved in this browser. Alerts arrive while the app is open in any tab.</span>
        </div>
        <div className="te-head__right">
          <button type="button" className="te-btn te-btn--ghost te-btn--sm" onClick={sendTest} disabled={off}>
            <Send size={12} /> Send a test
          </button>
          <Toggle on={s.enabled} label="All notifications" onChange={(on) => set({ enabled: on })} />
        </div>
      </header>

      <section className="te-panel" aria-label="Delivery">
        <span className="te-panel__title">How to alert you</span>
        <div className="te-row">
          <span className="te-row__main">
            <span className="te-row__title">Desktop notifications</span>
            <span className="te-row__sub">
              {permission === "granted"
                ? "Allowed in this browser."
                : permission === "denied"
                  ? "Blocked in this browser: allow notifications for this site in the browser's site settings."
                  : permission === "unsupported"
                    ? "This browser has no desktop notifications."
                    : "Not allowed yet."}
            </span>
          </span>
          <span className="te-chips">
            {permission === "default" && (
              <button
                type="button"
                className="te-btn te-btn--primary te-btn--sm"
                onClick={async () => setPermission(await requestDesktopPermission())}
              >
                <Bell size={12} /> Allow
              </button>
            )}
            <Toggle on={s.desktop && permission === "granted"} label="Desktop notifications" disabled={off || permission !== "granted"}
              onChange={(on) => set({ desktop: on })} />
          </span>
        </div>
        <div className="te-row">
          <span className="te-row__main">
            <span className="te-row__title">Desktop only when the app is in the background</span>
            <span className="te-row__sub">While you are looking at the app, the in-app alert is enough.</span>
          </span>
          <Toggle on={s.desktopOnlyInBackground} label="Desktop only in background" disabled={off || !s.desktop}
            onChange={(on) => set({ desktopOnlyInBackground: on })} />
        </div>
        <div className="te-row">
          <span className="te-row__main">
            <span className="te-row__title">In-app alerts</span>
            <span className="te-row__sub">Bottom-right; click one to open its session or trade.</span>
          </span>
          <Toggle on={s.toast} label="In-app alerts" disabled={off} onChange={(on) => set({ toast: on })} />
        </div>
        <div className="te-row">
          <span className="te-row__main">
            <span className="te-row__title">Sound</span>
            <span className="te-row__sub">A short tone; the pattern differs for success, warning and loss.</span>
          </span>
          <Toggle on={s.sound} label="Sound" disabled={off} onChange={(on) => set({ sound: on })} />
        </div>
      </section>

      <section className="te-panel" aria-label="Events">
        <span className="te-panel__title">What to alert you about</span>
        {KIND_ORDER.map((k) => (
          <div key={k} className="te-row">
            <span className="te-row__main">
              <span className="te-row__title">{KIND_META[k].label}</span>
              <span className="te-row__sub">{KIND_META[k].description}</span>
            </span>
            <Toggle on={s.kinds[k]} label={KIND_META[k].label} disabled={off}
              onChange={(on) => set({ kinds: { ...s.kinds, [k]: on } })} />
          </div>
        ))}
      </section>

      <section className="te-panel" aria-label="Recent notifications">
        <span className="te-panel__title">
          {off ? <BellOff size={14} /> : <Bell size={14} />} Recent (kept by the server since it started)
        </span>
        {(recent.data?.list ?? []).length === 0 ? (
          <span className="micro text-muted">Nothing yet.</span>
        ) : (
          (recent.data?.list ?? []).map((n) => (
            <div key={n.id} className="te-row">
              <span className="te-row__main">
                <span className="te-row__title">
                  <span className={`nt-dot nt-dot--${n.severity}`} /> {n.title}
                </span>
                <span className="te-row__sub">{n.body}</span>
              </span>
              <span className="te-row__end">
                <span className="te-pill">{KIND_META[n.kind]?.label ?? n.kind}</span>
                <span className="micro text-muted mono">{hms(n.createdAt)}</span>
              </span>
            </div>
          ))
        )}
      </section>
    </div>
  );
};
