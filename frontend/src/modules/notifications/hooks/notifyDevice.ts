import { AppNotification, NotificationSeverity } from "../types/notifications.types";

/** Desktop notification permission of this browser ("unsupported" where the Notification API does not exist). */
export function desktopPermission(): NotificationPermission | "unsupported" {
  return typeof window !== "undefined" && "Notification" in window ? Notification.permission : "unsupported";
}

export async function requestDesktopPermission(): Promise<NotificationPermission | "unsupported"> {
  if (desktopPermission() === "unsupported") return "unsupported";
  return Notification.requestPermission();
}

/** OS-level notification; clicking it focuses the app and opens `n.link`. */
export function showDesktop(n: AppNotification, onOpen: (link: string) => void): void {
  if (desktopPermission() !== "granted") return;
  const note = new Notification(n.title, {
    body: n.body,
    tag: `autotrader-${n.kind}-${n.sessionId ?? ""}-${n.tradeId ?? ""}`,
    requireInteraction: n.kind === "EXIT_SIGNAL" || n.kind === "SESSION_HALTED",
  });
  note.onclick = () => {
    window.focus();
    if (n.link) onOpen(n.link);
    note.close();
  };
}

const TONES: Record<NotificationSeverity, number[]> = {
  info: [660],
  success: [660, 880],
  warning: [880, 660, 880],
  danger: [440, 330],
};
let audio: AudioContext | null = null;

/** Short generated beep (no audio file); the pattern says the severity. Silently does nothing if audio is blocked. */
export function playTone(severity: NotificationSeverity): void {
  try {
    audio = audio ?? new AudioContext();
    const t0 = audio.currentTime;
    TONES[severity].forEach((freq, i) => {
      const osc = audio!.createOscillator();
      const gain = audio!.createGain();
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, t0 + i * 0.16);
      gain.gain.exponentialRampToValueAtTime(0.12, t0 + i * 0.16 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + i * 0.16 + 0.14);
      osc.connect(gain).connect(audio!.destination);
      osc.start(t0 + i * 0.16);
      osc.stop(t0 + i * 0.16 + 0.15);
    });
  } catch {
    // no audio device or autoplay blocked
  }
}
