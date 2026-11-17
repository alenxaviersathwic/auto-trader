import React from "react";
import { Link } from "@tanstack/react-router";
import { Bot } from "lucide-react";
import { AgentAvatar } from "../../sessions/components/agents/AgentAvatar";
import { SessionManagerMeta, TRADER_META } from "../../trade-history/components/traderMeta";
import { TradingSession } from "../../sessions/types/sessions.types";
import { normalizeTraderCodes } from "../../trade-history/components/traderMeta";

interface Props {
  manager: SessionManagerMeta;
  activeSessions: TradingSession[];
  /** Its sub-agents (the autopsy), drawn under it. */
  children?: React.ReactNode;
}

/** One session manager: the trader it hands the session to, and the sessions it runs right now. */
export const SessionManagerCard: React.FC<Props> = ({ manager, activeSessions, children }) => {
  const trader = TRADER_META[manager.traderCode];
  const mine = activeSessions.filter((s) => {
    const t = normalizeTraderCodes(s.traders);
    return t.length === 1 && t[0] === manager.traderCode;
  });
  return (
    <section className="te-panel" aria-label={manager.name}>
      <div className="te-panel__head">
        <span className="te-panel__title">
          <AgentAvatar icon={<Bot size={16} />} tone={mine.length > 0 ? "live" : "idle"}
            label={mine.length > 0 ? "Running sessions" : "Idle"} />
          <span className="ag-panel__id">
            <span className="ag-eyebrow">Session manager agent</span>
            {manager.name}
          </span>
        </span>
        <span className={`badge ${trader.badgeClass} mono`}>{trader.tag}</span>
      </div>
      <p className="micro text-secondary tr-text">
        Runs the session with the <strong>{trader.name}</strong>: {manager.trades}
      </p>
      <ol className="tr-list">
        <li>Takes only its trader&apos;s setups that pass the session&apos;s risk level and learned rules.</li>
        <li>Sizes each one to the free capital and the loss budget left; one position per side across indices.</li>
        <li>Ranks them on expected rupees after charges, then confidence, then reward:risk, and names the best.</li>
        <li>After each exit its autopsy sub-agent reviews the trade and updates this manager&apos;s scorecards.</li>
      </ol>
      <span className="label">Active sessions ({mine.length})</span>
      {mine.length === 0 ? (
        <span className="micro text-muted">None running with this manager.</span>
      ) : (
        mine.map((s) => (
          <Link key={s.id} to="/sessions/$id" params={{ id: String(s.id) }} className="te-row tr-link">
            <span className="te-row__main">
              <span className="te-row__title">{s.name}</span>
              <span className="te-row__sub">
                {s.sessionType.replace("_", " ")} · risk {s.riskLevel ?? "HIGH"} · capital ₹
                {s.capital.toLocaleString("en-IN")}
              </span>
            </span>
          </Link>
        ))
      )}
      {children && <div className="ag-subs">{children}</div>}
    </section>
  );
};
