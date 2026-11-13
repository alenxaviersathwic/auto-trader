"""
Extra entry requirements for the momentum engine from the 12 Nov 2026 institutional research (Indian index options,
last-6-month regime: grinding FII-led bear to mid-Oct, then a violent spot-up / vol-up short-covering reversal).
Each filter only ADDS a requirement -- nothing existing is removed -- and each is switched on separately through
settings.INSTITUTIONAL_FILTERS (comma list) once the real-data replay shows it helps in BOTH halves of the period.

  PE_GAP_UP          no PE (short) momentum on a gap-up day of >= 0.4% (NIFTY 1y: shorting gap-up sessions lost
                     Rs 1.02L over 38 days, one third won -- Quantsapp, vendor evidence)
  PE_VIX_UP_GREEN    no PE momentum while India VIX is rising on a green day (spot-up / vol-up = short squeeze,
                     the 2-6 Nov 2026 pattern that stopped our PE setups)
  NIFTY_NOISE_STRICT NIFTY noise breakout must hold: the last 2 one-minute closes beyond the band by 0.2 sigma
                     (NIFTY ORB-style breakout buying lost Rs 25.8k-70.5k over the year; NIFTY won 30% in our month)
  NIFTY_GAP_GO_CAP   no NIFTY GAP_GO when |gap| > 0.8% (big NIFTY gaps fade; keep it for BANKNIFTY / SENSEX)
  OI_BUILDUP         yesterday's near-month futures build-up must agree: PE only after SHORT_BUILDUP, CE only after
                     LONG_BUILDUP or SHORT_COVERING (Quantsapp daily OI build-up +Rs 2.46L before costs)
  HEAVYWEIGHTS       index breakout needs >= 3 of 5 heavyweights on the same side of their own VWAP; >= 3 against
                     = "divergence trap", skipped (Quantsapp heavyweight divergence trap +Rs 49.3k before costs)
  TREND_5_20         trade momentum only WITH the multi-day trend: CE needs the 5-day AND 20-day close trend UP, PE both
                     DOWN (12 Nov 2026 6-month replay: the single biggest loss cutter -- losses Rs 4.1L -> 0.9L)
  NO_VWAP_PULLBACK   VWAP_PULLBACK not traded (183 trades, -Rs 60k over the 6 months; worst setup on both sides)
  ENTRY_10_1430      new momentum entries only 10:00-14:30 IST (opening noise and the late-day reversal zone out)
  -- v3 (12 Nov 2026 research: index-only strategy review) --
  IB_GATE            before 11:15 only an "open drive" (gap >= 0.4% in the trade direction, still unfilled); from
                     11:15 the price must also be beyond the 09:15-11:15 initial balance high (CE) / low (PE);
                     last entry 14:45 NSE / 14:30 BSE (Zerodha NIFTY ORB 2019-2026: the 09:15-11:15 range is the most
                     reliable reference; NIFTY intraday vol is U-shaped with the 11:00-12:00 lull)
  PE_EXTRA           PE momentum also needs trend efficiency ER10 >= 0.25 or India VIX up on the day (short-side
                     noise-area momentum was negative out of sample in replications)
  FIB_ROOM           no momentum entry when the next Fibonacci level of the last 5 sessions' swing (23.6% ... 161.8%,
                     measured from the low for CE / the high for PE) is within 0.2% ahead of price: no room to run
                     NOT ENABLED: dropping trades after the fact looked better (+69.4k vs +64.5k), but in the full
                     replay a blocked signal re-fires minutes later at a worse price: 52 trades +54.5k (13 Nov 2026)
  DMA50              CE only above the 50-day moving average, PE only below it (Trade Max Academy trend rule; 13 Nov
                     2026 replay: with SIDE_COOLDOWN 30 min, 52 -> 49 trades, +64.5k -> +67.6k, DD 17.2k -> 14.7k)
  LATE_WINDOW_LAST   late-day momentum window moved to the true last 50 minutes (14:50-15:28 on the 15:40 close):
                     most last-half-hour predictability sits in the final minutes (Aalto thesis 2008-2024)
"""
from typing import Any

ALL = ("PE_GAP_UP", "PE_VIX_UP_GREEN", "NIFTY_NOISE_STRICT", "NIFTY_GAP_GO_CAP", "OI_BUILDUP", "HEAVYWEIGHTS",
       "LATE_WINDOW_LAST", "TREND_5_20", "NO_VWAP_PULLBACK", "ENTRY_10_1430", "IB_GATE", "PE_EXTRA", "FIB_ROOM", "DMA50")
OPEN_DRIVE_GAP_PCT = 0.4
PE_MIN_ER = 0.25
FIB_LEVELS = (0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618)
FIB_ROOM_PCT = 0.2
ENTRY_FROM_MIN, ENTRY_TO_MIN = 10 * 60, 14 * 60 + 30
PE_GAP_UP_PCT = 0.4
NIFTY_GAP_GO_MAX = 0.8
NOISE_EXTRA_SIGMA = 0.2
HEAVY_MIN_AGREE = 3
# INSIDE_BAR joined 12 Nov 2026 (price-action study): only as a momentum entry under the same v3 gates
MOMENTUM_SETUPS = ("NOISE_BREAKOUT", "LATE_DAY_MOMENTUM", "RANGE_BREAKOUT", "VWAP_PULLBACK", "GAP_GO", "INSIDE_BAR")
HEAVYWEIGHTS = {
    "NIFTY": ("HDFCBANK", "ICICIBANK", "RELIANCE", "INFY", "BHARTIARTL"),
    "SENSEX": ("HDFCBANK", "ICICIBANK", "RELIANCE", "INFY", "BHARTIARTL"),
    "BANKNIFTY": ("HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK"),
}


def enabled(setting: str | None) -> set[str]:
    return {x.strip().upper() for x in (setting or "").split(",") if x.strip()} & set(ALL)


def buildup_state(price_chg: float | None, oi_chg: float | None) -> str | None:
    if price_chg is None or oi_chg is None or (price_chg == 0 and oi_chg == 0):
        return None
    if price_chg > 0:
        return "LONG_BUILDUP" if oi_chg > 0 else "SHORT_COVERING"
    return "SHORT_BUILDUP" if oi_chg > 0 else "LONG_UNWINDING"


def block(a: dict[str, Any], s: dict[str, Any], code: str, on: set[str]) -> str | None:
    """Why an institutional filter holds this momentum signal back, or None. `a` = analysis dict (levels, vix, bars1,
    noise, spot, oiBuildupDaily, heavyweights); unknown inputs never veto."""
    if not on or s.get("name") not in MOMENTUM_SETUPS:
        return None
    side, name = s["side"], s["name"]
    if "NO_VWAP_PULLBACK" in on and name == "VWAP_PULLBACK":
        return "NO_VWAP_PULLBACK: VWAP pullback entries are switched off"
    if "TREND_5_20" in on:
        td = a.get("trendDays") or {}
        want = "UP" if side == "CE" else "DOWN"
        bad = [f"{n}d {t}" for n, t in sorted(td.items()) if n in (5, 20) and t != want]
        if bad:
            return f"TREND_5_20: {side} against the multi-day trend ({', '.join(bad)})"
    if "ENTRY_10_1430" in on:
        b1 = a.get("bars1") or []
        if b1:
            t = str(b1[-1]["t"])
            m = int(t[11:13]) * 60 + int(t[14:16]) + 1
            if not (ENTRY_FROM_MIN <= m <= ENTRY_TO_MIN):
                return "ENTRY_10_1430: new momentum entries only 10:00-14:30"
    lv = a.get("levels") or {}
    gap = lv.get("gapPct")
    if "IB_GATE" in on:
        b1 = a.get("bars1") or []
        if b1:
            t = str(b1[-1]["t"])
            m = int(t[11:13]) * 60 + int(t[14:16]) + 1
            last = 14 * 60 + (30 if code in ("SENSEX", "BANKEX") else 45)
            px = b1[-1]["c"]
            if m > last:
                return f"IB_GATE: no new entries after {last // 60}:{last % 60:02d}"
            if m < 11 * 60 + 15 and gap is not None:  # unknown inputs never veto
                pdc = lv.get("pdc")
                drive = gap is not None and (gap >= OPEN_DRIVE_GAP_PCT if side == "CE" else gap <= -OPEN_DRIVE_GAP_PCT)
                unfilled = pdc and ((lv.get("dayLow") or 0) > pdc if side == "CE" else (lv.get("dayHigh") or 1e18) < pdc)
                if not (drive and unfilled):
                    return "IB_GATE: before 11:15 only an open-drive day (gap >= 0.4% that day, unfilled)"
            else:
                ib_hi, ib_lo = lv.get("ibHigh"), lv.get("ibLow")
                if ib_hi and ib_lo and not (px > ib_hi if side == "CE" else px < ib_lo):
                    return f"IB_GATE: price inside the 09:15-11:15 range ({ib_lo:.1f}-{ib_hi:.1f})"
    if "PE_EXTRA" in on and side == "PE":
        er = a.get("er10")
        vix_chg = (a.get("vix") or {}).get("changePct")
        if (er is not None or vix_chg is not None) and not ((er is not None and er >= PE_MIN_ER) or (vix_chg is not None and vix_chg > 0)):
            return f"PE_EXTRA: short momentum needs ER10 >= {PE_MIN_ER} (is {er}) or VIX up (is {vix_chg})"
    if "DMA50" in on and a.get("dma50"):
        px = a.get("spot") or ((a.get("bars1") or [{}])[-1].get("c"))
        if px and (px < a["dma50"] if side == "CE" else px > a["dma50"]):
            return f"DMA50: {side} on the wrong side of the 50-day average {a['dma50']:.1f}"
    if "FIB_ROOM" in on and a.get("swing5"):
        hi, lo = a["swing5"].get("high"), a["swing5"].get("low")
        px = a.get("spot") or ((a.get("bars1") or [{}])[-1].get("c"))
        if hi and lo and px and hi > lo:
            sw = hi - lo
            ahead = [lv for lv in ((lo + f * sw) if side == "CE" else (hi - f * sw) for f in FIB_LEVELS)
                     if (lv > px if side == "CE" else lv < px)]
            if ahead:
                nxt = min(ahead) if side == "CE" else max(ahead)
                room = abs(nxt - px) / px * 100
                if room < FIB_ROOM_PCT:
                    return f"FIB_ROOM: next 5-day Fibonacci level {nxt:.1f} only {room:.2f}% ahead (needs {FIB_ROOM_PCT:g}%)"
    if "PE_GAP_UP" in on and side == "PE" and gap is not None and gap >= PE_GAP_UP_PCT:
        return f"PE_GAP_UP: no short momentum on a {gap:+.2f}% gap-up day"
    if "PE_VIX_UP_GREEN" in on and side == "PE":
        vix_chg = (a.get("vix") or {}).get("changePct")
        spot, pdc = a.get("spot") or (a.get("bars1") or [{}])[-1].get("c"), lv.get("pdc")
        if vix_chg is not None and vix_chg > 0 and spot and pdc and spot > pdc:
            return f"PE_VIX_UP_GREEN: India VIX {vix_chg:+.1f}% on a green day (short-squeeze tape)"
    if "NIFTY_GAP_GO_CAP" in on and code == "NIFTY" and name == "GAP_GO" and gap is not None and abs(gap) > NIFTY_GAP_GO_MAX:
        return f"NIFTY_GAP_GO_CAP: {gap:+.2f}% gap is too big for a NIFTY gap-and-go"
    if "NIFTY_NOISE_STRICT" in on and code == "NIFTY" and name == "NOISE_BREAKOUT":
        n = a.get("noise") or {}
        b1 = a.get("bars1") or []
        sig = (n.get("sigmaPct") or 0) / 100
        if n.get("upper") and n.get("lower") and len(b1) >= 2:
            if side == "CE":
                lvl = n["upper"] * (1 + NOISE_EXTRA_SIGMA * sig)
                held = all(b["c"] > lvl for b in b1[-2:])
            else:
                lvl = n["lower"] * (1 - NOISE_EXTRA_SIGMA * sig)
                held = all(b["c"] < lvl for b in b1[-2:])
            if not held:
                return f"NIFTY_NOISE_STRICT: last 2 one-minute closes not beyond {lvl:.1f}"
    if "OI_BUILDUP" in on:
        st = a.get("oiBuildupDaily")
        if st:
            ok = st == "SHORT_BUILDUP" if side == "PE" else st in ("LONG_BUILDUP", "SHORT_COVERING")
            if not ok:
                return f"OI_BUILDUP: yesterday's futures {st} does not support a {side} trade"
    if "HEAVYWEIGHTS" in on:
        hw = a.get("heavyweights") or []
        if len(hw) >= HEAVY_MIN_AGREE:
            up = side == "CE"
            agree = sum(1 for h in hw if h.get("aboveVwap") == up and (h.get("ret") or 0) * (1 if up else -1) > 0)
            against = sum(1 for h in hw if h.get("aboveVwap") is (not up))
            if against >= HEAVY_MIN_AGREE:
                return f"HEAVYWEIGHTS: divergence trap ({against}/{len(hw)} heavyweights against the breakout)"
            if agree < HEAVY_MIN_AGREE:
                return f"HEAVYWEIGHTS: only {agree}/{len(hw)} heavyweights confirm"
    return None


def heavyweight_state(bars_by_stock: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """[{name, aboveVwap, ret}] from each stock's 1-minute bars so far today (oldest first)."""
    out = []
    for name, bars in bars_by_stock.items():
        if not bars:
            continue
        pv = sum((b["h"] + b["l"] + b["c"]) / 3 * (b.get("v") or 1) for b in bars)
        vv = sum((b.get("v") or 1) for b in bars)
        vwap = pv / vv if vv else bars[-1]["c"]
        out.append({"name": name, "aboveVwap": bars[-1]["c"] > vwap, "ret": (bars[-1]["c"] - bars[0]["o"]) / bars[0]["o"]})
    return out
