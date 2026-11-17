import React from "react";
import { Activity, Bot, LineChart, Microscope, Newspaper } from "lucide-react";
import { useRecentNotifications } from "../../../notifications/hooks/useNotifications";
import { NotificationKind } from "../../../notifications/types/notifications.types";
import { TradeAutopsy } from "../../../autopsy/types/learning.types";
import { VERDICT_META } from "../../../autopsy/types/learningMeta";
import { formatSignedRupee } from "../../../opportunity-finder/components/formatters";

const hhmm = (iso: string): string =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });

type Actor = "manager" | "trader" | "autopsy" | "news";
const ACTOR: Record<NotificationKind, Actor> = {
  NEW_SUGGESTION: "manager",
  TRADE_LOCKED: "manager",
  SESSION_HALTED: "manager",
  TRADE_ENTERED: "trader",
  EXIT_SIGNAL: "trader",
  TRADE_EXITED: "trader",
  LEARNING: "autopsy",
  RESEARCH: "manager",
  MARKET_MOVE: "news",
};
const ACTOR_META: Record<Actor, { label: string; icon: React.ReactNode }> = {
  manager: { label: "Manager", icon: <Bot size={11} /> },
  trader: { label: "Trader", icon: <LineChart size={11} /> },
  autopsy: { label: "Autopsy", icon: <Microscope size={11} /> },
  news: { label: "News", icon: <Newspaper size={11} /> },
};

interface Entry {
  key: string;
  at: string;
  actor: Actor;
  title: string;
  body: string;
  tone: "info" | "success" | "warning" | "danger";
}

interface Props {
  sessionId: number;
  autopsies: TradeAutopsy[];
}

/** What the session's agents did, newest first: the manager's suggestions and locks, the trader's entries and exits,
 *  and the autopsy sub-agent's reviews. Alerts come from the server since its last start. */
export const AgentActivityFeed: React.FC<Props> = ({ sessionId, autopsies }) => {
  const notes = useRecentNotifications({ page: 0, limit: 30, sortDir: "desc", sessionId }, 10000);
  const entries: Entry[] = [
    ...(notes.data?.list ?? []).map((n) => ({
      key: `n${n.id}`,
      at: n.createdAt,
      actor: ACTOR[n.kind] ?? "manager",
      title: n.title,
      body: n.body,
      tone: n.severity,
    })),
    ...autopsies.map((a) => ({
      key: `a${a.id}`,
      at: a.createdAt,
      actor: "autopsy" as Actor,
      title: `Reviewed trade #${a.tradeId}: ${VERDICT_META[a.verdict]?.label.toLowerCase() ?? a.verdict}`,
      body: `${a.setup.replace(/_/g, " ")} ${a.rMultiple >= 0 ? "+" : ""}${a.rMultiple.toFixed(1)}R, ${formatSignedRupee(a.netPnl)}${
        a.lessons[0] ? ` · ${a.lessons[0]}` : ""
      }`,
      tone: (a.outcome === "WIN" ? "success" : "danger") as Entry["tone"],
    })),
  ]
    .sort((x, y) => Date.parse(y.at) - Date.parse(x.at))
    .slice(0, 25);

  return (
    <section className="te-panel ag-feed" aria-label="Agent activity">
      <span className="te-panel__title">
        <Activity size={14} className="text-muted" /> Agent activity
      </span>
      {entries.length === 0 ? (
        <span className="micro text-muted">Suggestions, locks, exits and autopsy reviews appear here as they happen.</span>
      ) : (
        <ol className="ag-feed__list">
          {entries.map((e) => (
            <li key={e.key} className={`ag-feed__item ag-feed__item--${e.tone}`}>
              <span className="ag-feed__time mono">{hhmm(e.at)}</span>
              <span className={`ag-feed__actor ag-feed__actor--${e.actor}`}>
                {ACTOR_META[e.actor].icon} {ACTOR_META[e.actor].label}
              </span>
              <span className="ag-feed__text">
                <strong>{e.title}</strong>
                <span className="text-muted">{e.body}</span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
};
