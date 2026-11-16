import { AutopsyVerdict } from "./learning.types";

/** Display copy for autopsy verdicts. Tone maps to the te-pill colour classes. */
export const VERDICT_META: Record<AutopsyVerdict, { label: string; tone: "green" | "red" | "amber" | "cyan" }> = {
  RAN_TO_TARGET: { label: "RAN TO TARGET", tone: "green" },
  PROTECTED_PROFIT: { label: "PROTECTED PROFIT", tone: "green" },
  WON_BUT_GAVE_BACK: { label: "WON, GAVE BACK", tone: "amber" },
  FEES_ATE_PROFIT: { label: "FEES ATE PROFIT", tone: "amber" },
  GAVE_BACK_WINNER: { label: "GAVE BACK WINNER", tone: "red" },
  CUT_EARLY: { label: "CUT EARLY", tone: "cyan" },
  NEVER_WORKED: { label: "NEVER WORKED", tone: "red" },
  STOPPED_OUT: { label: "STOPPED OUT", tone: "red" },
};

export const TAG_LABEL: Record<string, string> = {
  AGAINST_TREND: "against trend",
  LATE_ENTRY: "late entry",
  GAVE_BACK: "gave back",
  FEES_ATE_PROFIT: "fees ate profit",
  NEVER_WORKED: "never worked",
};
