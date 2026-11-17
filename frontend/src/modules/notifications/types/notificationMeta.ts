import { NotificationKind } from "./notifications.types";

export const KIND_META: Record<NotificationKind, { label: string; description: string }> = {
  NEW_SUGGESTION: { label: "New suggestion", description: "A session got new setups to take (one alert per loop pass)." },
  TRADE_LOCKED: { label: "Trade locked", description: "A pick was locked, by you or automatically in semi / full auto." },
  TRADE_ENTERED: { label: "Trade entered", description: "A trade started, with its entry, stop and target." },
  EXIT_SIGNAL: { label: "Exit signal", description: "Semi-auto: the trader wants out and you square off." },
  TRADE_EXITED: { label: "Trade closed", description: "A trade closed, with the reason and net P&L." },
  SESSION_HALTED: { label: "Session halted", description: "A session hit its daily or weekly loss limit." },
  LEARNING: { label: "Learning", description: "The autopsy agent paused a losing setup or proposed a rule." },
  RESEARCH: { label: "Research", description: "A scheduled Research Engine run finished." },
  MARKET_MOVE: { label: "Sudden move", description: "A scanned index or commodity moved sharply; the news found for it." },
};

export const KIND_ORDER = Object.keys(KIND_META) as NotificationKind[];
