import React from "react";

export type AgentTone = "live" | "ready" | "alert" | "idle";

interface Props {
  icon: React.ReactNode;
  tone: AgentTone;
  size?: "md" | "sm";
  label: string;
}

/** Round agent badge with a status dot; the dot pulses while the agent is working (respects reduced motion). */
export const AgentAvatar: React.FC<Props> = ({ icon, tone, size = "md", label }) => (
  <span className={`ag-avatar ag-avatar--${size} ag-avatar--${tone}`} role="img" aria-label={label}>
    {icon}
    <span className="ag-avatar__dot" aria-hidden="true" />
  </span>
);
