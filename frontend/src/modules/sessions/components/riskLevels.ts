import { RiskLevel } from "../types/sessions.types";

/** Session risk level = entry strictness. Mirrors backend sessions/service/session_risk.py. */
export const RISK_LEVELS: RiskLevel[] = ["LOW", "MEDIUM", "HIGH"];

export const RISK_META: Record<RiskLevel, { label: string; badgeClass: string; takes: string }> = {
  LOW: {
    label: "LOW",
    badgeClass: "badge--green",
    takes: "Proven setups only, with the trend, reward:risk 1.5 or better",
  },
  MEDIUM: {
    label: "MEDIUM",
    badgeClass: "badge--amber",
    takes: "Any coded setup, with the trend, reward:risk 1.3 or better",
  },
  HIGH: {
    label: "HIGH",
    badgeClass: "badge--red",
    takes: "Everything the engine finds, including against-trend and AI-only picks",
  },
};

export const RISK_NOTE =
  "Risk level changes which setups are accepted. Position size, the loss limit and the one-lot allowance stay the same.";
