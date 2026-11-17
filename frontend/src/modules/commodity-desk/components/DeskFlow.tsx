import React, { useEffect, useState } from "react";
import { BarChart3, Brain, Clock3, Layers, Newspaper, Send, ShieldCheck } from "lucide-react";
import { AgentStance, DeskLiveItem, NewsCheck } from "../types/commodityDesk.types";

const STALE_S = 60;

function useNow(ms = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), ms);
    return () => window.clearInterval(t);
  }, [ms]);
  return now;
}

const secs = (iso: string | null, now: number): number | null => (iso ? Math.max(0, (now - Date.parse(iso)) / 1000) : null);
const agoTxt = (s: number | null): string =>
  s == null ? "--" : s < 60 ? `${Math.round(s)}s ago` : s < 3600 ? `${Math.round(s / 60)}m ago` : `${Math.round(s / 3600)}h ago`;

const TONE: Record<AgentStance, string> = {
  BULLISH: "green",
  BEARISH: "red",
  NEUTRAL: "slate",
  CAUTION: "amber",
  BLOCK: "red",
};

const AGENTS: { key: "clock" | "structure" | "options" | "news"; label: string; icon: React.ReactNode }[] = [
  { key: "clock", label: "Clock", icon: <Clock3 size={13} /> },
  { key: "structure", label: "Structure", icon: <BarChart3 size={13} /> },
  { key: "options", label: "Chain", icon: <Layers size={13} /> },
  { key: "news", label: "News", icon: <Newspaper size={13} /> },
];

const NEWS_STEP: Record<NewsCheck["step"], string> = {
  SAVING: "recording the move",
  READING_HEADLINES: "reading the news feeds",
  EXPLAINING: "LLM explaining the move",
  NO_HEADLINES: "no headline found",
};

interface Props {
  code: string;
  item?: DeskLiveItem;
  newsCheck?: NewsCheck;
}

/**
 * The desk's working flow, live: every scan replays as a wave through the sub-agents into the risk gate, the head
 * trader and the decision. The wave is keyed on the real pass number, the head trader pulses only while the model is
 * actually thinking (thinkingSince), and a desk with no recent scan is drawn idle. Nothing is animated for show.
 */
export const DeskFlow: React.FC<Props> = ({ code, item, newsCheck }) => {
  const now = useNow();
  const since = secs(item?.passAt ?? null, now);
  const live = since != null && since < STALE_S;
  const thinking = secs(item?.thinkingSince ?? null, now);
  const sent = secs(item?.sentAt ?? null, now);
  const decided = secs(item?.decidedAt ?? null, now);
  const fresh = sent != null && sent < 30;

  return (
    <div className={`df ${live ? "df--live" : "df--idle"}`} aria-label={`${code} desk working flow`}>
      <div className="df__status" aria-live="polite">
        <span className={`df__beacon ${live ? "df__beacon--on" : ""}`} />
        {live ? (
          <span>
            <strong>Live</strong> · pass #{item?.passNo} {agoTxt(since)} · sub-agents ran in {item?.passMs ?? 0} ms
          </span>
        ) : item?.passAt ? (
          <span className="text-muted">Idle · last scan {agoTxt(since)} (MCX closed or the scanner stopped)</span>
        ) : (
          <span className="text-muted">Waiting for the first commodity scan</span>
        )}
      </div>

      {/* key = pass number: each new real pass restarts the wave */}
      <div className="df__lane" key={item?.passNo ?? 0}>
        <div className="df__agents">
          {AGENTS.map((a, i) => {
            const st = item?.stances?.[a.key];
            return (
              <span key={a.key} className={`df-node df-node--agent ${live ? "df-node--wave" : ""}`}
                    style={{ animationDelay: `${i * 140}ms` }} title={st ? `${a.label}: ${st}` : a.label}>
                <span className="df-node__icon">{a.icon}</span>
                <span className="df-node__label">{a.label}</span>
                {st && <span className={`df-dot df-dot--${TONE[st]}`} />}
                {a.key === "news" && newsCheck && <span className="df-spin" aria-hidden="true" />}
              </span>
            );
          })}
        </div>
        <span className={`df-link ${live ? "df-link--flow" : ""}`} />
        <span className={`df-node ${live ? "df-node--wave" : ""}`} style={{ animationDelay: "620ms" }}
              title="code risk gate: refuses unsafe setups">
          <span className="df-node__icon"><ShieldCheck size={13} /></span>
          <span className="df-node__label">Risk gate</span>
          <span className="mono micro">
            <span className="text-green">{item?.allowed ?? 0}✓</span> <span className="text-red">{item?.refused ?? 0}✗</span>
          </span>
        </span>
        <span className={`df-link ${live ? "df-link--flow" : ""}`} />
        <span className={`df-node df-node--head ${thinking != null ? "df-node--thinking" : ""}`}
              title="LLM head trader">
          <span className="df-node__icon"><Brain size={13} /></span>
          <span className="df-node__label">Head trader</span>
          {thinking != null ? (
            <span className="mono micro text-cyan">
              thinking {Math.round(thinking)}s
              <span className="df-dots" aria-hidden="true"><i /><i /><i /></span>
            </span>
          ) : (
            <span className="mono micro text-muted">{decided != null ? `decided ${agoTxt(decided)}` : "idle"}</span>
          )}
        </span>
        <span className={`df-link ${thinking == null && item?.lastDecision ? "df-link--flow" : ""}`} />
        <span className={`df-node df-node--out ${fresh ? "df-node--sent" : ""}`}>
          <span className="df-node__icon"><Send size={13} /></span>
          <span className="df-node__label">Decision</span>
          {item?.lastDecision ? (
            <span className={`badge ${item.lastDecision === "TAKE" ? "badge--green" : "badge--slate"}`}>{item.lastDecision}</span>
          ) : (
            <span className="mono micro text-muted">--</span>
          )}
        </span>
      </div>

      {newsCheck && (
        <div className="df__news" aria-live="polite">
          <span className="df-spin" aria-hidden="true" />
          <Newspaper size={12} /> News sub-agent on {newsCheck.code} ({newsCheck.direction === "UP" ? "+" : ""}
          {newsCheck.pct.toFixed(2)}%): {NEWS_STEP[newsCheck.step]}
          {newsCheck.headlines != null ? ` · ${newsCheck.headlines} headline(s)` : ""} · {agoTxt(secs(newsCheck.since, now))}
        </div>
      )}
    </div>
  );
};
