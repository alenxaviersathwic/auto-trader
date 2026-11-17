import React, { useState } from "react";
import { BarChart3, Brain, ChevronDown, ChevronRight, Clock3, Layers, Newspaper, ShieldCheck } from "lucide-react";
import { AgentReport, AgentStance, DeskCandidate, DeskDecision } from "../types/commodityDesk.types";

const hhmm = (iso: string): string =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });
const ago = (iso: string): string => {
  const m = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  return m < 1 ? "just now" : m < 60 ? `${m}m ago` : `${Math.floor(m / 60)}h ${m % 60}m ago`;
};
const px = (v?: number | null) => (v == null ? "--" : v.toLocaleString("en-IN", { maximumFractionDigits: 2 }));

const STANCE_BADGE: Record<AgentStance, string> = {
  BULLISH: "badge--green",
  BEARISH: "badge--red",
  NEUTRAL: "badge--slate",
  CAUTION: "badge--amber",
  BLOCK: "badge--red",
};

const AGENTS: { key: keyof DeskDecision["agents"]; icon: React.ReactNode }[] = [
  { key: "clock", icon: <Clock3 size={13} /> },
  { key: "structure", icon: <BarChart3 size={13} /> },
  { key: "options", icon: <Layers size={13} /> },
  { key: "news", icon: <Newspaper size={13} /> },
];

const PHASE: Record<string, string> = {
  ASIA: "ASIA HOURS",
  EUROPE: "EUROPE",
  US_OPEN: "US OPEN",
  US_LATE: "US LATE",
  CLOSING: "CLOSING",
};

const AgentRow: React.FC<{ r: AgentReport; icon: React.ReactNode }> = ({ r, icon }) => {
  const [open, setOpen] = useState(false);
  return (
    <li className={`dk-agent ${open ? "dk-agent--open" : ""}`}>
      <button type="button" className="dk-agent__head" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span className="dk-agent__icon">{icon}</span>
        <span className="dk-agent__name">{r.name}</span>
        <span className={`badge ${STANCE_BADGE[r.stance] ?? "badge--slate"}`}>{r.stance}</span>
        <span className="dk-agent__summary">{r.summary}</span>
        {open ? <ChevronDown size={13} className="text-muted" /> : <ChevronRight size={13} className="text-muted" />}
      </button>
      {open && (
        <ul className="dk-agent__facts">
          {r.facts.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      )}
    </li>
  );
};

const SetupLine: React.FC<{ c: DeskCandidate; chosen?: boolean }> = ({ c, chosen }) => (
  <li className={`dk-setup ${chosen ? "dk-setup--chosen" : ""} ${c.refusals?.length ? "dk-setup--refused" : ""}`}>
    <span className={`badge ${c.side === "CE" ? "badge--green" : "badge--red"}`}>{c.side}</span>
    <span className="dk-setup__name">{c.name.replace(/^DESK_/, "").replace(/_/g, " ").toLowerCase()}</span>
    <span className="mono dk-setup__levels">
      {px(c.entry)} → {px(c.target)} · stop {px(c.stop)} · {c.rr}R
    </span>
    {c.refusals?.length ? (
      <span className="dk-setup__why text-red">{c.refusals.join("; ")}</span>
    ) : c.warnings?.length ? (
      <span className="dk-setup__why text-amber">{c.warnings.join("; ")}</span>
    ) : null}
  </li>
);

/** One commodity's newest desk decision: the sub-agents' reports, the head trader's reasoning, the setups. */
export const DeskCommodityView: React.FC<{ d: DeskDecision }> = ({ d }) => {
  const others = d.candidates.filter((c) => !d.chosen || c.id !== d.chosen.id);
  return (
    <div className="dk-view">
      <div className="dk-view__head">
        <span className="ticker dk-view__code">{d.underlyingCode}</span>
        <span className="mono text-secondary">{px(d.spot)}</span>
        <span className="badge badge--slate">{PHASE[d.phase] ?? d.phase}</span>
        <span className="dk-view__right">
          <span className={`badge ${d.decision === "TAKE" ? "badge--green" : "badge--slate"}`}>{d.decision}</span>
          <span className={`badge ${d.source === "LLM" ? "badge--cyan" : "badge--amber"}`}
                title={d.source === "LLM" ? "decided by the local LLM head trader" : "model unavailable: code rule decided"}>
            {d.source === "LLM" ? "LLM" : "CODE RULE"}
          </span>
          {d.decision === "TAKE" && <span className="mono micro text-secondary">conviction {d.conviction}</span>}
          <span className="mono micro text-muted" title={hhmm(d.decidedAt)}>{ago(d.decidedAt)}</span>
        </span>
      </div>

      <ul className="dk-agents" aria-label="Sub-agents">
        {AGENTS.map((a) => (d.agents[a.key] ? <AgentRow key={a.key} r={d.agents[a.key]} icon={a.icon} /> : null))}
      </ul>

      <div className="dk-head">
        <span className="dk-head__title">
          <Brain size={13} /> Head trader
        </span>
        <p className="dk-head__thinking">{d.thinking || "No reasoning recorded."}</p>
        {d.watchFor && (
          <span className="micro text-secondary">
            <strong>Watching for:</strong> {d.watchFor}
          </span>
        )}
      </div>

      {(d.chosen || others.length > 0) && (
        <div className="dk-setups">
          <span className="label">
            <ShieldCheck size={12} /> Setups on the table
          </span>
          <ul>
            {d.chosen && <SetupLine c={d.chosen} chosen />}
            {others.map((c) => (
              <SetupLine key={c.id} c={c} />
            ))}
          </ul>
          {d.outcome && <span className="micro text-muted">Taken setup: {d.outcome}</span>}
        </div>
      )}
    </div>
  );
};
