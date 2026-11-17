import React from "react";
import { Bot } from "lucide-react";
import { AgentAvatar } from "../../sessions/components/agents/AgentAvatar";
import { SessionManagerMeta, TRADER_META } from "../../trade-history/components/traderMeta";

interface Props {
  manager: SessionManagerMeta;
  /** Its sub-agents (the autopsy), drawn under it. */
  children?: React.ReactNode;
}

/** One reusable session manager: each new session invokes this manager for its chosen strategy profile. */
export const SessionManagerCard: React.FC<Props> = ({ manager, children }) => {
  const trader = TRADER_META[manager.traderCode];
  return (
    <section className="te-panel" aria-label={manager.name}>
      <div className="te-panel__head">
        <span className="te-panel__title">
          <AgentAvatar icon={<Bot size={16} />} tone="idle" label={manager.name} />
          <span className="ag-panel__id">
            <span className="ag-eyebrow">Reusable session manager</span>
            {manager.name}
          </span>
        </span>
        <span className={`badge ${trader.badgeClass} mono`}>{trader.tag}</span>
      </div>
      <p className="micro text-secondary tr-text">
        Runs any session assigned to the <strong>{trader.name}</strong>: {manager.trades}
      </p>
      <ol className="tr-list">
        <li>Takes only its trader&apos;s setups that pass the session&apos;s risk level and learned rules.</li>
        <li>Sizes each one to the free capital and the loss budget left; one position per side across indices.</li>
        <li>Ranks them on expected rupees after charges, then confidence, then reward:risk, and names the best.</li>
        <li>After each exit its autopsy sub-agent reviews the trade and updates this manager&apos;s scorecards.</li>
      </ol>
      {children && <div className="ag-subs">{children}</div>}
    </section>
  );
};
