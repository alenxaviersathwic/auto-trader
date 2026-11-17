"""
Risk sub-agent: the code gate. It runs BEFORE the head trader (so the LLM only sees setups that may be taken) and
again on its answer -- the head trader can decline anything, but it can never take what this gate refuses.

A candidate is refused when:
  * the session clock says BLOCK (last 30 min of MCX, or a scheduled release in <= 10 min)
  * the option chain is unusable for that side (spread / no sellers)
  * reward:risk < 1.5 (structure_agent already enforces it; checked again here)
  * the price structure points hard the other way (score <= -2 for a CE, >= +2 for a PE)
  * the 5- / 15-minute charts do not confirm it for the situation (opportunity_finder setups.tf_agreement)
"""
from __future__ import annotations

from typing import Any

from app.modules.commodity_desk.service.agents import options_agent

MIN_RR = 1.5


def check(c: dict[str, Any], reports: dict[str, dict[str, Any]], front_spot: float) -> tuple[bool, list[str], list[str]]:
    """(allowed, refusals, warnings) for one candidate."""
    refuse, warn = [], []
    clock, opts, struct = reports.get("clock") or {}, reports.get("options") or {}, reports.get("structure") or {}
    if clock.get("stance") == "BLOCK":
        refuse.append(clock.get("summary") or "session clock blocks new entries")
    elif clock.get("stance") == "CAUTION":
        warn.append(clock.get("summary") or "scheduled release nearby")
    if opts and not options_agent.liquid(opts, c["side"]):
        refuse.append(f"ATM {c['side']} not liquid enough to trade")
    if c.get("tfBlock"):
        refuse.append(c["tfBlock"])
    if float(c.get("rr") or 0) < MIN_RR:
        refuse.append(f"reward:risk {c.get('rr')} below {MIN_RR}")
    s = int(struct.get("score") or 0)
    if (c["side"] == "CE" and s <= -2) or (c["side"] == "PE" and s >= 2):
        refuse.append(f"price structure points the other way (score {s:+d})")
    if opts:
        note = options_agent.path_note(c, opts, front_spot)
        if note:
            warn.append(note)
    return (not refuse), refuse, warn
