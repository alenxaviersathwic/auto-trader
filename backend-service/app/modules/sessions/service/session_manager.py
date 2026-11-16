"""
Session manager: the voice of the session on the trading screen (pure functions, no I/O).

  best_suggestion()  of the open picks, the one to take now and why: expected rupees after charges, what it does to
                     the loss budget and free capital, the session's risk level, and how its setup has actually done
                     (learning scorecard). Ranking is the loop's own (_ranked: expected net, confidence, reward:risk).
  judge_pick()       after the fact, was this pick right, and was the session right to take or skip it
  batch_verdict()    the same for every pick offered in one loop pass (a "batch")

Pick verdicts
  TAKEN_WIN / TAKEN_LOSS / TAKEN_RUNNING   the session entered it; result from the trade itself
  LOCKED_NOT_ENTERED                       locked but never entered
  MISSED_WINNER                            not taken, and the opportunity reached its target
  GOOD_SKIP                                not taken, and it hit its stop
  NO_MOVE                                  not taken, neither target nor stop inside its window
  PENDING                                  window still open or no candles yet
"""
from typing import Any

SUCCESS, FAILURE, MIXED, PENDING, NO_MOVE = "SUCCESS", "FAILURE", "MIXED", "PENDING", "NO_MOVE"


def best_suggestion(ranked: list[Any], cap: Any, risk_level: str, risk_summary: str, view: dict[str, Any] | None,
                    trader_name: Any, active_trades: int, max_parallel: int) -> dict[str, Any] | None:
    """`ranked`: open SessionPick rows, best first. `trader_name(strategy)` -> display name."""
    if not ranked:
        return None
    p = ranked[0]
    setup = p.strategy or "UNCODED"
    budget = float(cap.remainingLossBudget)
    risk = float(p.riskAmount)
    sc = ((view or {}).get("scorecards") or {}).get(setup)
    reasons = [
        f"Best expected result after charges: ₹{float(p.expectedNet):,.0f} on {p.lots} lot{'s' if p.lots != 1 else ''}",
        (f"Risks ₹{risk:,.0f}, {risk / budget * 100:.0f}% of the ₹{budget:,.0f} loss budget left" if budget > 0
         else f"Risks ₹{risk:,.0f}"),
        f"Needs ₹{float(p.capitalRequired):,.0f} of ₹{float(cap.availableCapital):,.0f} free capital",
        f"Passes {risk_level} risk: {risk_summary.lower()}",
        (f"{setup} in the last 14 days: {sc['closedTrades']} trades, ₹{sc['netPnl']:+,.0f}, avg {sc['avgR']:+.2f}R"
         if sc and sc.get("closedTrades") else f"{setup} has no closed trades yet: no track record to lean on"),
    ]
    cautions = [str(x) for x in (p.risks or [])[:2]]
    if sc and sc.get("closedTrades") and sc.get("netPnl", 0) < 0:
        cautions.insert(0, f"{setup} is losing money inside its window")
    if max_parallel - active_trades == 1:
        cautions.append("Last free slot for a parallel trade")
    cautions.append(f"Confidence {p.confidence}% is the model's own figure, not a measured win rate")
    return {
        "pickId": p.id,
        "headline": f"{trader_name(p.strategy)} · {p.underlyingCode} {float(p.strike):g} {p.optionType} · {setup}",
        "reasons": reasons, "cautions": cautions, "alternatives": len(ranked) - 1,
    }


def judge_pick(pick_state: str, opp: dict[str, Any] | None, trade: dict[str, Any] | None) -> dict[str, Any]:
    """`opp`: the opportunity's checked result ({outcome, achievedPct, maxGainPct, hitAt}); `trade`: the trade
    entered from this pick ({tradeState, netPnl, exitReason, verdict}) or None."""
    outcome = (opp or {}).get("outcome") or "PENDING"
    if trade:
        if trade.get("tradeState") == "RUNNING":
            v, note = "TAKEN_RUNNING", "Taken and still running."
        elif float(trade.get("netPnl") or 0) > 0:
            v, note = "TAKEN_WIN", f"Taken: +₹{float(trade['netPnl']):,.0f} ({trade.get('exitReason') or 'exit'})."
        else:
            v, note = "TAKEN_LOSS", f"Taken: ₹{float(trade.get('netPnl') or 0):,.0f} ({trade.get('exitReason') or 'exit'})."
        if trade.get("verdict"):
            note += f" Autopsy: {trade['verdict'].replace('_', ' ').lower()}."
    elif pick_state == "LOCKED":
        v, note = "LOCKED_NOT_ENTERED", "Locked but never entered."
    elif outcome == "TARGET_HIT":
        v, note = "MISSED_WINNER", "Not taken, and it reached its target."
    elif outcome == "STOP_HIT":
        v, note = "GOOD_SKIP", "Not taken, and it hit its stop: skipping it saved money."
    elif outcome == "EXPIRED":
        v, note = "NO_MOVE", "Not taken; it reached neither target nor stop in its window."
    else:
        v, note = "PENDING", "Its window is still open or no candles are available yet."
    return {"managerVerdict": v, "opportunityOutcome": outcome, "note": note,
            "achievedPct": (opp or {}).get("achievedPct"), "maxGainPct": (opp or {}).get("maxGainPct"),
            "hitAt": (opp or {}).get("hitAt"), "candleError": (opp or {}).get("error")}


def batch_verdict(judged: list[dict[str, Any]]) -> dict[str, Any]:
    """Success / failure of one batch: did its picks work, and how did the session do with them."""
    v = [j["managerVerdict"] for j in judged]
    hits = v.count("TAKEN_WIN") + v.count("MISSED_WINNER")
    misses = v.count("TAKEN_LOSS") + v.count("GOOD_SKIP")
    flat = v.count("NO_MOVE")
    taken = v.count("TAKEN_WIN") + v.count("TAKEN_LOSS") + v.count("TAKEN_RUNNING")
    resolved = hits + misses + flat
    if resolved == 0:
        verdict = PENDING
    elif hits > misses:
        verdict = SUCCESS
    elif misses > hits:
        verdict = FAILURE
    elif hits == 0:
        verdict = NO_MOVE
    else:
        verdict = MIXED
    parts = [f"{hits} of {resolved} resolved pick{'s' if resolved != 1 else ''} reached target"] if resolved else \
        ["Nothing resolved yet"]
    if taken:
        parts.append(f"you took {taken}")
    if v.count("MISSED_WINNER"):
        parts.append(f"missed {v.count('MISSED_WINNER')} winner{'s' if v.count('MISSED_WINNER') != 1 else ''}")
    if v.count("GOOD_SKIP"):
        parts.append(f"skipped {v.count('GOOD_SKIP')} loser{'s' if v.count('GOOD_SKIP') != 1 else ''}")
    if v.count("PENDING"):
        parts.append(f"{v.count('PENDING')} still pending")
    return {"verdict": verdict, "note": "; ".join(parts) + ".", "hits": hits, "misses": misses,
            "noMove": flat, "taken": taken, "pending": v.count("PENDING"), "resolved": resolved}
