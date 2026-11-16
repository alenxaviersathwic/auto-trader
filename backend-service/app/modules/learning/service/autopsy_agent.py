"""
Autopsy agent: what happened in one finished trade and what it teaches (pure functions, no I/O).

Measured in R, where R = entry - initial stop (option premium). Nothing here is estimated: every number comes from
the trade's own fill, stop, peak, trough and exit.

  rMultiple    (exit - entry) / R           the result in risk units
  mfeR         (peak - entry) / R           best the trade ever got (maximum favourable excursion)
  maeR         (entry - trough) / R         worst it ever got (maximum adverse excursion)
  givebackPct  share of the peak gain handed back before the exit

Verdicts
  RAN_TO_TARGET      win of 2R or more, or the target was hit
  PROTECTED_PROFIT   win, the trail kept most of the move
  WON_BUT_GAVE_BACK  win, but more than half of a >= 1R peak was given back
  FEES_ATE_PROFIT    the price move was positive but charges made it a loss
  GAVE_BACK_WINNER   was 1R or more up, then closed at a loss
  CUT_EARLY          closed by hand before the stop
  NEVER_WORKED       never got 0.3R in favour: the entry idea was wrong
  STOPPED_OUT        an ordinary stop-out

Failure tags (what the learning loop counts per setup; learning_rules.py turns repeats into guards)
  AGAINST_TREND     a loss on a pick the engine had marked as against the trend
  LATE_ENTRY        a loss entered in the last hour of the session (LATE_DAY_MOMENTUM excluded: that is its window)
  GAVE_BACK         reached 1R or more and then lost, or gave back more than 60% of the peak
  FEES_ATE_PROFIT   positive price move, negative after charges
  NEVER_WORKED      a loss that never reached 0.3R in favour
"""
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

_IST = ZoneInfo("Asia/Kolkata")
LATE_ENTRY_MINUTES = 60
NEVER_WORKED_MFE_R = 0.3
GAVE_BACK_MFE_R = 1.0
GIVEBACK_WIN_PCT = 50.0
GIVEBACK_TAG_PCT = 60.0
SESSION_CLOSE_HHMM = {"NSE": "15:30", "BSE": "15:30", "MCX": "23:30"}

LESSONS: dict[str, str] = {
    "AGAINST_TREND": "Counter-trend entries on this setup lose; take it only with the trend.",
    "LATE_ENTRY": "Entries in the last hour on this setup lose; stop taking it late in the day.",
    "GAVE_BACK": "Open profit was handed back; move the stop to breakeven sooner.",
    "FEES_ATE_PROFIT": "The move was too small to pay the charges; ask for a bigger target.",
    "NEVER_WORKED": "The entry idea did not work at all; if this repeats the setup gets paused by its scorecard.",
}


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def minutes_to_close(entered_at: datetime | None, exchange: str | None) -> int | None:
    if entered_at is None:
        return None
    ist = (entered_at if entered_at.tzinfo else entered_at.replace(tzinfo=ZoneInfo("UTC"))).astimezone(_IST)
    hh, mm = SESSION_CLOSE_HHMM.get((exchange or "NSE").upper(), "15:30").split(":")
    return int(hh) * 60 + int(mm) - (ist.hour * 60 + ist.minute)


def autopsy(t: dict[str, Any]) -> dict[str, Any]:
    """`t`: entryAt, initialStop, initialTarget, exitPrice, peakPrice, troughPrice, grossPnl, netPnl, charges,
    exitReason, strategy, enteredAt (datetime), exitedAt (datetime), exchange, pickRisks (list), traderCode."""
    entry, stop0, target0 = _f(t.get("entryAt")), _f(t.get("initialStop")), _f(t.get("initialTarget"))
    exit_px = _f(t.get("exitPrice"), entry)
    peak = max(_f(t.get("peakPrice"), entry), entry, exit_px)
    trough = min(_f(t.get("troughPrice"), entry), entry, exit_px)
    gross, net = _f(t.get("grossPnl")), _f(t.get("netPnl"))
    reason = (t.get("exitReason") or "").upper()
    setup = t.get("strategy") or "UNKNOWN"
    r = max(0.05, entry - stop0)
    r_mult = round((exit_px - entry) / r, 2)
    mfe_r = round((peak - entry) / r, 2)
    mae_r = round((entry - trough) / r, 2)
    giveback = round((peak - exit_px) / (peak - entry) * 100, 1) if peak > entry else None
    mins_left = minutes_to_close(t.get("enteredAt"), t.get("exchange"))
    against = any(str(x).strip().lower().startswith("against the") for x in (t.get("pickRisks") or []))
    held = None
    if t.get("enteredAt") and t.get("exitedAt"):
        held = round((t["exitedAt"] - t["enteredAt"]).total_seconds() / 60, 1)

    win = net > 0
    if win:
        if reason == "TARGET_HIT" or r_mult >= 2:
            verdict = "RAN_TO_TARGET"
        elif giveback is not None and giveback > GIVEBACK_WIN_PCT and mfe_r >= GAVE_BACK_MFE_R:
            verdict = "WON_BUT_GAVE_BACK"
        else:
            verdict = "PROTECTED_PROFIT"
    elif gross > 0:
        verdict = "FEES_ATE_PROFIT"
    elif mfe_r >= GAVE_BACK_MFE_R:
        verdict = "GAVE_BACK_WINNER"
    elif reason.startswith("MANUAL") and r_mult > -0.8:
        verdict = "CUT_EARLY"
    elif mfe_r < NEVER_WORKED_MFE_R:
        verdict = "NEVER_WORKED"
    else:
        verdict = "STOPPED_OUT"

    tags: list[str] = []
    if not win:
        if against:
            tags.append("AGAINST_TREND")
        if mins_left is not None and mins_left < LATE_ENTRY_MINUTES and setup != "LATE_DAY_MOMENTUM":
            tags.append("LATE_ENTRY")
        if gross > 0:
            tags.append("FEES_ATE_PROFIT")
        if mfe_r < NEVER_WORKED_MFE_R:
            tags.append("NEVER_WORKED")
    if mfe_r >= GAVE_BACK_MFE_R and (not win or (giveback or 0) > GIVEBACK_TAG_PCT):
        tags.append("GAVE_BACK")

    right: list[str] = []
    wrong: list[str] = []
    if mfe_r >= 1:
        right.append(f"The idea worked: price ran {mfe_r:.1f}R in favour (peak ₹{peak:.2f}).")
    if win and (giveback is None or giveback <= GIVEBACK_WIN_PCT):
        right.append(f"Kept most of the move: closed at {r_mult:+.1f}R.")
    if mae_r < 0.5:
        right.append(f"Entry timing was clean: worst point only {mae_r:.1f}R against.")
    if not win and r_mult >= -1.05:
        right.append("The stop held the loss to about 1R.")
    if mfe_r < NEVER_WORKED_MFE_R and not win:
        wrong.append(f"Never moved in favour (best {mfe_r:.1f}R): the setup read was wrong.")
    if giveback is not None and giveback > GIVEBACK_WIN_PCT and mfe_r >= GAVE_BACK_MFE_R:
        wrong.append(f"Gave back {giveback:.0f}% of a {mfe_r:.1f}R peak before the exit.")
    if "FEES_ATE_PROFIT" in tags:
        wrong.append(f"Gross ₹{gross:,.2f} but net ₹{net:,.2f}: charges ate the move.")
    if "AGAINST_TREND" in tags:
        wrong.append("Taken against the trend.")
    if "LATE_ENTRY" in tags:
        wrong.append(f"Entered with only {mins_left} minutes of the session left.")
    if r_mult < -1.2:
        wrong.append(f"Lost {abs(r_mult):.1f}R, more than the planned 1R (slippage or a gap through the stop).")
    if reason == "SESSION_CLOSE":
        (right if win else wrong).append("Closed by the session end, not by the plan.")

    return {
        "setup": setup, "traderCode": t.get("traderCode"), "outcome": "WIN" if win else "LOSS",
        "verdict": verdict, "rMultiple": r_mult, "mfeR": mfe_r, "maeR": mae_r, "givebackPct": giveback,
        "riskPerUnit": round(r, 2), "plannedR": round((target0 - entry) / r, 2) if target0 > entry else None,
        "minutesToCloseAtEntry": mins_left, "heldMinutes": held, "exitReason": reason or None,
        "grossPnl": round(gross, 2), "netPnl": round(net, 2), "tags": tags,
        "wentRight": right, "wentWrong": wrong, "lessons": [LESSONS[x] for x in tags if x in LESSONS],
    }
