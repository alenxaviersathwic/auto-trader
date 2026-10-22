import React from "react";
import { Bot, Wrench, Zap } from "lucide-react";
import { SseEventType } from "../types/master.types";

interface Props {
  event?: SseEventType;
  label?: string;
}

export const ThinkingIndicator: React.FC<Props> = ({ event, label }) => {
  const icon = event === "tool_call" ? <Wrench size={14} className="thinking-icon" />
    : event === "thinking" ? <Zap size={14} className="thinking-icon" />
    : <Bot size={14} className="thinking-icon" />;

  return (
    <div className="thinking-indicator">
      <div className="thinking-avatar">{icon}</div>
      <div className="thinking-bubble">
        <span className="thinking-label">{label || "Master is thinking…"}</span>
        <span className="thinking-dots">
          <span />
          <span />
          <span />
        </span>
      </div>
    </div>
  );
};
