# 13. Notifications and automatic research

Two features that run for the whole app rather than one page:

1. **Local notifications**: the backend raises an alert when something happens to a session or trade; the browser
   shows it as an in-app toast, a desktop (OS) notification and a short tone, as the user's settings allow.
2. **Automatic research**: the Research Engine runs at start-up and then every 30 minutes, but only while the system
   is not busy.

---

## 1. Notifications

### Flow

```
producer (session loop, trade service, learning service, research job)
   └─ core/events/notify.notify(kind, title, body, severity, sessionId, tradeId, link, data)
        └─ event_bus.publish("notification", payload)        (never raises; a failed alert never breaks trading)
             └─ NotificationHub (modules/notifications/service/notification_hub.py)
                  ├─ ring buffer: last 300, in memory (lost on restart)
                  └─ one asyncio.Queue(200) per SSE subscriber (oldest dropped if a client stalls)
                       └─ GET /api/v1/notifications/stream   (SSE, event name "notification", 20 s heartbeat)
                            └─ NotificationCenter (frontend, mounted once in AppLayout)
                                 ├─ toast (bottom-right, 7 s, click opens `link`)
                                 ├─ desktop Notification API (click focuses the tab and opens `link`)
                                 └─ WebAudio tone (pattern by severity)
```

### Kinds and producers

| Kind | Raised by | When |
|---|---|---|
| NEW_SUGGESTION | session_loop_service | A loop pass saved new picks (one alert per pass, names the best) |
| TRADE_LOCKED | session_loop_service | Manual lock, or auto-lock in SEMI_AUTO / FULL_AUTO |
| TRADE_ENTERED | trade_service | Trade pilot started for a trade |
| EXIT_SIGNAL | trade_service | SEMI_AUTO: the pilot wants out (once per distinct reason); the user squares off |
| TRADE_EXITED | trade_service._finalize_exit | Trade closed: reason + net P&L |
| SESSION_HALTED | session_loop_service | Daily MAX_LOSS or WEEKLY_LOSS hit |
| LEARNING | learning_service | A setup was paused, or a guard was proposed / applied |
| RESEARCH | research_schedule_job | A scheduled research run finished |

### API

- `GET /notifications/stream?afterId=N` — SSE. With `afterId` (or the browser's `Last-Event-ID` header on
  reconnect, which wins) it first replays buffered notifications newer than that id; without either it sends only
  new ones. Each event's SSE `id` is the notification id, so the browser resumes without duplicates.
- `POST /notifications/search` — `NotificationSearchFilter` (kind, sessionId, afterId) over the in-memory buffer.

### Settings (frontend)

`/settings/notifications`, stored in `localStorage` key `autotrader.notificationSettings` (per browser, like the
desktop permission itself):

- master switch; desktop on/off (needs browser permission, the page has an **Allow** button); desktop only when the
  tab is in the background; in-app toasts; sound;
- one toggle per kind (RESEARCH is off by default).

Replayed notifications older than 2 minutes are recorded in the list but not announced. Alerts only arrive while the
app is open in some tab: there is no service worker / web push.

---

## 2. Automatic research

`modules/research/job/research_schedule_job.py`, registered in `main.py` lifespan:

- job `research-auto-startup`: once, `RESEARCH_AUTO_STARTUP_DELAY_S` (60 s) after start-up;
- job `research-auto`: every `RESEARCH_AUTO_INTERVAL_MIN` (30) minutes.

Each firing calls `run_if_idle(trigger)`, which runs `decide()`; checks in order:

1. `RESEARCH_AUTO_ENABLED`;
2. inside `RESEARCH_AUTO_WINDOW` ("07:00-23:30" IST);
3. no research run already active;
4. system usage `< RESEARCH_AUTO_MAX_LOAD_PCT` (50).

### System usage

`modules/system/service/system_load.py`:

```
cpuPct = loadavg(1 min) / cpu cores * 100          (None on Windows)
appPct = units / SYSTEM_APP_CAPACITY * 100         (capacity 12)
units  = running session loops + session scans + trade pilots
usagePct = max(cpuPct, appPct)
```

So with capacity 12, six or more live units (e.g. 3 sessions running + 3 trades locked) is 50% and research is
skipped until the next slot, even if the CPU is idle.

`GET /research/schedule` returns the settings, the next run time and the last decision
(`ran`, `reason`, `runId`, `usage`); the Research page shows it as the **Auto** pill
(`skipped 17:44 · 58% load · next 18:14`).

### Settings (`.env`)

| Key | Default |
|---|---|
| RESEARCH_AUTO_ENABLED | true |
| RESEARCH_AUTO_INTERVAL_MIN | 30 |
| RESEARCH_AUTO_MAX_LOAD_PCT | 50 |
| RESEARCH_AUTO_WINDOW | 07:00-23:30 |
| RESEARCH_AUTO_STARTUP_DELAY_S | 60 |
| SYSTEM_APP_CAPACITY | 12 |
