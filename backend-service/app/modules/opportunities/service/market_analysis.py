"""
Turns raw candles + option chain into the facts intraday traders actually look at.

Pure functions (no I/O) so every number can be unit-tested:
  timeframes   15-minute = trend, 5-minute = setup, 1-minute = trigger
  levels       previous-day high/low/close, CPR (pivot, BC, TC, width), R1/S1, opening range, day high/low
  VWAP         on the FUTURE (index spot has no volume)
  indicators   EMA 9/20/21, ATR(14) 5-minute and daily, ADX(14) 5-minute
  volume       latest completed 5-minute futures bar vs the previous 12
  OI buildup   futures price change vs OI change over the last 3 completed 5-minute bars
  regime       TREND / RANGE / MIXED / VOLATILE
  session      time window + hard no-entry windows (first 5 minutes, 12:00-13:00 chop, last 20 minutes)
               NSE 1-minute NIFTY data (Singh & Gangwar, MPRA 89689): 11:00-13:00 is the quiet stretch and
               13:00-14:00 is MORE volatile than 10:00-11:00, so the lunch block ends at 13:00, not 13:30.
"""

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.modules.opportunities.service import day_type

_IST = ZoneInfo("Asia/Kolkata")
OPENING_RANGE_MINUTES = 15
NO_ENTRY_AFTER_OPEN_MIN = 5
CHOP_BLOCK_START = 12 * 60  # equity-hours lunch lull: no new entries 12:00-13:00 IST
CHOP_BLOCK_END = 13 * 60
NO_ENTRY_BEFORE_CLOSE_MIN = 20  # entries until 15:10 on a 15:30 close: the last half hour often carries the day's push


# ───────────────────────── helpers ─────────────────────────
def _mins(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _bar_min(t: str) -> int:
    """Minute of day (IST) of an Upstox timestamp like 2026-11-02T09:15:00+05:30."""
    try:
        dt = datetime.fromisoformat(t)
        if dt.tzinfo:
            dt = dt.astimezone(_IST)
        return dt.hour * 60 + dt.minute
    except ValueError:
        return 0


def resample(bars: list[dict[str, Any]], n: int, open_hhmm: str, now_min: int | None = None) -> list[dict[str, Any]]:
    """1-minute bars -> n-minute bars aligned to the session open. Adds `done` (bucket closed)."""
    o = _mins(open_hhmm)
    out: list[dict[str, Any]] = []
    cur_bucket = None
    for b in bars:
        m = _bar_min(b["t"])
        if m < o:
            continue
        bucket = (m - o) // n
        if bucket != cur_bucket:
            out.append({"t": b["t"], "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"], "v": b["v"], "oi": b["oi"],
                        "start": o + bucket * n, "count": 1})
            cur_bucket = bucket
        else:
            x = out[-1]
            x["h"], x["l"], x["c"] = max(x["h"], b["h"]), min(x["l"], b["l"]), b["c"]
            x["v"] += b["v"]
            x["oi"] = b["oi"] or x["oi"]
            x["count"] += 1
    for x in out:
        end = x["start"] + n
        x["done"] = x["count"] >= n or (now_min is not None and now_min >= end)
    if out and now_min is None:
        out[-1]["done"] = out[-1]["count"] >= n
    return out


def ema(values: list[float], n: int) -> list[float]:
    if not values:
        return []
    k = 2 / (n + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def atr(bars: list[dict[str, Any]], n: int = 14) -> float:
    if len(bars) < 2:
        return (bars[0]["h"] - bars[0]["l"]) if bars else 0.0
    trs = [max(b["h"] - b["l"], abs(b["h"] - p["c"]), abs(b["l"] - p["c"])) for p, b in zip(bars, bars[1:])]
    trs = trs[-n:]
    return sum(trs) / len(trs)


def adx(bars: list[dict[str, Any]], n: int = 14) -> float | None:
    """Wilder ADX. None until there are enough bars (2n)."""
    if len(bars) < 2 * n:
        return None
    tr, pdm, ndm = [], [], []
    for p, b in zip(bars, bars[1:]):
        up, dn = b["h"] - p["h"], p["l"] - b["l"]
        pdm.append(up if up > dn and up > 0 else 0.0)
        ndm.append(dn if dn > up and dn > 0 else 0.0)
        tr.append(max(b["h"] - b["l"], abs(b["h"] - p["c"]), abs(b["l"] - p["c"])))

    def wilder(xs: list[float]) -> list[float]:
        s = [sum(xs[:n])]
        for x in xs[n:]:
            s.append(s[-1] - s[-1] / n + x)
        return s

    atr_s, p_s, n_s = wilder(tr), wilder(pdm), wilder(ndm)
    dx = []
    for a, p, m in zip(atr_s, p_s, n_s):
        if a <= 0:
            dx.append(0.0)
            continue
        pdi, ndi = 100 * p / a, 100 * m / a
        dx.append(100 * abs(pdi - ndi) / (pdi + ndi) if pdi + ndi else 0.0)
    if len(dx) < n:
        return None
    a = sum(dx[:n]) / n
    for d in dx[n:]:
        a = (a * (n - 1) + d) / n
    return round(a, 1)


def vwap(bars: list[dict[str, Any]]) -> float | None:
    pv = sum((b["h"] + b["l"] + b["c"]) / 3 * b["v"] for b in bars)
    vol = sum(b["v"] for b in bars)
    return pv / vol if vol > 0 else None


def vwap_sd(bars: list[dict[str, Any]], vw: float) -> float:
    """Volume-weighted standard deviation of the typical price around VWAP (for the +/- 2 SD bands)."""
    vol = sum(b["v"] for b in bars)
    if vol <= 0:
        return 0.0
    var = sum(b["v"] * ((b["h"] + b["l"] + b["c"]) / 3 - vw) ** 2 for b in bars) / vol
    return var ** 0.5


def vwap_series(bars: list[dict[str, Any]]) -> list[float | None]:
    """Running (session-cumulative) VWAP as of each bar's close -- not the single current value `vwap()`
    returns, but what VWAP stood at, at that point in time. Needed to test how many of the bars so far
    closed on one side of VWAP as it actually was then, not against today's final VWAP."""
    out: list[float | None] = []
    cum_pv = cum_vol = 0.0
    for b in bars:
        if b["v"] > 0:
            cum_pv += (b["h"] + b["l"] + b["c"]) / 3 * b["v"]
            cum_vol += b["v"]
        out.append(cum_pv / cum_vol if cum_vol > 0 else None)
    return out


def cpr(h: float, l: float, c: float) -> dict[str, float]:
    p = (h + l + c) / 3
    bc = (h + l) / 2
    tc = 2 * p - bc
    lo, hi = min(bc, tc), max(bc, tc)
    return {"pivot": p, "bc": lo, "tc": hi, "r1": 2 * p - l, "s1": 2 * p - h,
            "widthPct": (hi - lo) / p * 100 if p else 0.0}


def supertrend(bars: list[dict[str, Any]], n: int = 10, mult: float = 3.0) -> dict[str, Any] | None:
    """Supertrend(n, mult) on completed bars. Returns {dir, line, flipIdx, barsSinceFlip} or None (too few bars)."""
    if len(bars) < n + 2:
        return None
    trs = [bars[0]["h"] - bars[0]["l"]] + [
        max(b["h"] - b["l"], abs(b["h"] - p["c"]), abs(b["l"] - p["c"])) for p, b in zip(bars, bars[1:])
    ]
    atrs: list[float] = []
    for i in range(len(bars)):
        w = trs[max(0, i - n + 1): i + 1]
        atrs.append(sum(w) / len(w))
    fu = fl = 0.0
    direction = 1
    flip_idx = 0
    line = 0.0
    for i, b in enumerate(bars):
        mid = (b["h"] + b["l"]) / 2
        bu, bl = mid + mult * atrs[i], mid - mult * atrs[i]
        if i == 0:
            fu, fl = bu, bl
            line = fl
            continue
        pc = bars[i - 1]["c"]
        fu = bu if (bu < fu or pc > fu) else fu
        fl = bl if (bl > fl or pc < fl) else fl
        prev_dir = direction
        if direction == 1 and b["c"] < fl:
            direction = -1
        elif direction == -1 and b["c"] > fu:
            direction = 1
        if direction != prev_dir:
            flip_idx = i
        line = fl if direction == 1 else fu
    return {"dir": "UP" if direction == 1 else "DOWN", "line": line, "flipIdx": flip_idx,
            "barsSinceFlip": len(bars) - 1 - flip_idx}


def oi_shift(prev: dict[str, float] | None, cur: dict[str, float] | None) -> dict[str, Any] | None:
    """Option-chain OI change between two snapshots {pcr, ceOi, peOi}: PCR drift and which side is being written."""
    if not prev or not cur or not prev.get("ceOi") or not prev.get("peOi"):
        return None
    ce = (cur["ceOi"] - prev["ceOi"]) / prev["ceOi"] * 100
    pe = (cur["peOi"] - prev["peOi"]) / prev["peOi"] * 100
    return {"pcrChg": round(cur["pcr"] - prev["pcr"], 3), "ceOiChgPct": round(ce, 2), "peOiChgPct": round(pe, 2),
            "pcr": cur["pcr"]}


# ───────────────────────── session ─────────────────────────
def session_info(open_hhmm: str, close_hhmm: str, now: datetime | None = None) -> dict[str, Any]:
    now = (now or datetime.now(_IST)).astimezone(_IST)
    m = now.hour * 60 + now.minute
    since, to_close = m - _mins(open_hhmm), _mins(close_hhmm) - m
    if since < 30:
        window = "OPENING"
    elif to_close <= 60:
        window = "CLOSING"
    elif 11 * 60 + 30 <= m < 13 * 60 and _mins(close_hhmm) <= 16 * 60:
        window = "MIDDAY_CHOP"  # equity indices: the lunch lull, option buyers lose to theta here
    else:
        window = "ACTIVE"
    blocked = None
    if since < NO_ENTRY_AFTER_OPEN_MIN:
        blocked = f"no new entries in the first {NO_ENTRY_AFTER_OPEN_MIN} minutes (opening noise)"
    elif to_close < NO_ENTRY_BEFORE_CLOSE_MIN:
        blocked = f"no new entries in the last {NO_ENTRY_BEFORE_CLOSE_MIN} minutes"
    elif CHOP_BLOCK_START <= m < CHOP_BLOCK_END and _mins(close_hhmm) <= 16 * 60:
        blocked = "no new entries in the 12:00-13:00 midday chop"
    return {"nowMin": m, "minutesSinceOpen": since, "minutesToClose": to_close, "window": window, "blocked": blocked}


# ───────────────────────── main ─────────────────────────
def analyze(cfg: Any, market: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Everything the brief, setups and validation need, from one market fetch."""
    close = cfg.close_today(now) if hasattr(cfg, "close_today") else cfg.close
    sess = session_info(cfg.open, close, now)
    now_min = sess["nowMin"]
    spot = market["spot"]
    p1 = market.get("spotBars1m") or []
    f1 = market.get("futBars1m") or []
    p5 = resample(p1, 5, cfg.open, now_min)
    p15 = resample(p1, 15, cfg.open, now_min)
    f5 = resample(f1, 5, cfg.open, now_min)
    p5d = [b for b in p5 if b["done"]]
    f5d = [b for b in f5 if b["done"]]
    p15d = [b for b in p15 if b["done"]]
    daily = market.get("daily") or []

    # completed 1-minute bars (the minute still forming is excluded): the entry-timing timeframe
    p1d = [b for b in p1 if _bar_min(b["t"]) < now_min]
    out: dict[str, Any] = {"session": sess, "bars5": p5d, "futBars5": f5d, "bars1": p1d, "bars15": p15d,
                           "code": getattr(cfg, "code", None)}

    # levels
    lv: dict[str, Any] = {}
    if daily:
        pd = daily[-1]
        lv.update({"pdh": pd["h"], "pdl": pd["l"], "pdc": pd["c"]})
        c = cpr(pd["h"], pd["l"], pd["c"])
        lv.update({"pivot": c["pivot"], "bc": c["bc"], "tc": c["tc"], "r1": c["r1"], "s1": c["s1"],
                   "cprWidthPct": round(c["widthPct"], 3)})
        hist = [cpr(d["h"], d["l"], d["c"])["widthPct"] for d in daily[-21:-1]]
        if len(hist) >= 10:
            rank = sum(1 for w in hist if w < c["widthPct"]) / len(hist)
            lv["cprNarrow"] = rank <= 0.3  # narrowest 30% of the last 20 days: trend-day candidate
            lv["cprWide"] = rank >= 0.7  # widest 30%: range-day candidate
        out["dailyAtr"] = atr(daily, 14)
        closes = [d["c"] for d in daily]
        out["trendDays"] = {n: ("UP" if closes[-1] > closes[-1 - n] else "DOWN")
                            for n in (5, 20) if len(closes) > n}
        if len(closes) > 10:  # Kaufman efficiency ratio over 10 sessions: trend >= 0.35, range <= 0.20
            path = sum(abs(closes[i] - closes[i - 1]) for i in range(len(closes) - 10, len(closes)))
            out["er10"] = round(abs(closes[-1] - closes[-11]) / path, 3) if path else None
    if p1:
        day_o = p1[0]["o"]
        lv.update({"dayOpen": day_o, "dayHigh": max(b["h"] for b in p1), "dayLow": min(b["l"] for b in p1)})
        ib = [b for b in p1 if _bar_min(b["t"]) < _mins(cfg.open) + 120]  # initial balance 09:15-11:15
        if ib:
            lv.update({"ibHigh": max(b["h"] for b in ib), "ibLow": min(b["l"] for b in ib),
                       "ibDone": now_min >= _mins(cfg.open) + 120})
        if "pdc" in lv and lv["pdc"]:
            lv["gapPct"] = round((day_o - lv["pdc"]) / lv["pdc"] * 100, 2)
        or_bars = [b for b in p1 if _bar_min(b["t"]) < _mins(cfg.open) + OPENING_RANGE_MINUTES]
        if or_bars and sess["minutesSinceOpen"] >= OPENING_RANGE_MINUTES:
            lv.update({"orHigh": max(b["h"] for b in or_bars), "orLow": min(b["l"] for b in or_bars)})
    out["levels"] = lv

    # trend / indicators (price series the options follow)
    closes5 = [b["c"] for b in p5d]
    if closes5:
        e9, e20, e21 = ema(closes5, 9)[-1], ema(closes5, 20)[-1], ema(closes5, 21)[-1]
        out["ema5"] = {"ema9": e9, "ema20": e20, "ema21": e21}
    if len(closes5) >= 4:
        e9s, e21s = ema(closes5, 9), ema(closes5, 21)
        out["emaSeries5"] = {"e9": e9s[-14:], "e21": e21s[-14:]}
    out["supertrend5"] = supertrend(p5d)
    out["atr5"] = atr(p5d, 14) if p5d else 0.0
    out["adx5"] = adx(p5d, 14)
    closes15 = [b["c"] for b in p15d]
    if len(closes15) >= 3:
        f9, f21 = ema(closes15, 9)[-1], ema(closes15, 21)[-1]
        last = closes15[-1]
        out["trend15"] = "UP" if last > f9 > f21 else "DOWN" if last < f9 < f21 else "FLAT"
        out["trend15Source"] = "15m"
    elif len(closes5) >= 9:
        # first ~45 minutes: fewer than 3 closed 15-minute bars, so use the 5-minute 9/21 EMAs as the proxy
        f9, f21, last = ema(closes5, 9)[-1], ema(closes5, 21)[-1], closes5[-1]
        out["trend15"] = "UP" if last > f9 > f21 else "DOWN" if last < f9 < f21 else "FLAT"
        out["trend15Source"] = "5m-proxy"
    else:
        out["trend15"] = "FLAT"

    # VWAP (futures)
    fv = vwap([b for b in f1 if b["v"] > 0])
    if fv and f1:
        fl = f1[-1]["c"]
        out["vwap"] = {"value": fv, "futLast": fl, "above": fl > fv, "distPct": round((fl - fv) / fv * 100, 3),
                       "sd": vwap_sd([b for b in f1 if b["v"] > 0], fv)}
    if f5d:
        out["vwapSeries5"] = vwap_series(f5d)
        vs = [v for v in out["vwapSeries5"] if v is not None]
        if len(vs) >= 7 and fv:
            # VWAP drift over the last 30 minutes: near zero = a balanced (range) day, VWAP fades are valid
            out["vwap"] = {**out.get("vwap", {}), "slopePct": round((vs[-1] - vs[-7]) / vs[-7] * 100, 3)}

    # volume (futures, completed 5-minute bars)
    if len(f5d) >= 4 and any(b["v"] for b in f5d):
        prev = [b["v"] for b in f5d[-13:-1]]
        avg = sum(prev) / len(prev) if prev else 0.0
        last = f5d[-1]
        ratio = round(last["v"] / avg, 2) if avg > 0 else 0.0
        out["volume"] = {"ratio5m": ratio, "spike": ratio >= 1.5, "dry": 0 < ratio < 0.6, "lastBarUp": last["c"] >= last["o"]}

    # OI buildup (futures)
    if len(f5d) >= 4 and f5d[-1]["oi"] and f5d[-4]["oi"]:
        a, b = f5d[-4], f5d[-1]
        dp = (b["c"] - a["c"]) / a["c"] * 100
        doi = (b["oi"] - a["oi"]) / a["oi"] * 100
        if abs(doi) < 0.05 or abs(dp) < 0.02:
            state = "NEUTRAL"
        elif dp > 0:
            state = "LONG_BUILDUP" if doi > 0 else "SHORT_COVERING"
        else:
            state = "SHORT_BUILDUP" if doi > 0 else "LONG_UNWINDING"
        out["buildup"] = {"state": state, "priceChgPct": round(dp, 3), "oiChgPct": round(doi, 3)}

    # option chain context
    chains = market.get("chains") or []
    if chains:
        ch = chains[0]
        out["oi"] = {"resistance": ch.get("resistance"), "support": ch.get("support"), "pcr": ch.get("pcr"),
                     "ceOi": ch.get("ceOi"), "peOi": ch.get("peOi")}
        if ch.get("atmStraddle") and spot:
            out["expectedMovePct"] = round(ch["atmStraddle"] / spot * 100, 2)
    vix = market.get("vix")
    if vix:
        out["vix"] = vix

    # regime
    a5 = out["adx5"]
    day_range = (lv.get("dayHigh", 0) - lv.get("dayLow", 0)) if p1 else 0
    datr = out.get("dailyAtr") or 0
    out["rangeUsedPct"] = round(day_range / datr * 100) if datr else None
    if vix and vix.get("changePct", 0) >= 8:
        regime = "VOLATILE"
    elif (a5 is not None and a5 >= 23) or (datr and day_range >= 0.8 * datr and out["trend15"] != "FLAT"):
        regime = "TREND"
    elif a5 is not None and a5 < 18 and out["trend15"] == "FLAT":
        regime = "RANGE"
    else:
        regime = "MIXED"
    out["regime"] = regime

    _day_type(out, cfg, market, spot, p1, p5d, sess, now)

    # key levels sorted: candidate targets / stops for setups
    keys = {k: lv.get(k) for k in ("pdh", "pdl", "pdc", "r1", "s1", "tc", "bc", "orHigh", "orLow", "dayHigh", "dayLow")}
    if chains:
        keys["oiResistance"], keys["oiSupport"] = chains[0].get("resistance"), chains[0].get("support")
    out["keyLevels"] = sorted(((k, float(v)) for k, v in keys.items() if v), key=lambda x: x[1])
    return out


def _day_type(out: dict[str, Any], cfg: Any, market: dict[str, Any], spot: float, p1: list[dict[str, Any]],
              p5d: list[dict[str, Any]], sess: dict[str, Any], now: datetime | None) -> None:
    """Noise area, round numbers, days to expiry, first-half-hour return and the day type (service/day_type.py)."""
    lv = out["levels"]
    out["spot"] = spot
    step = getattr(cfg, "strikeStep", 0) or 0
    if spot and step:
        lv["roundBelow"], lv["roundAbove"] = day_type.round_levels(spot, 100.0 if step <= 50 else 500.0)
    chains = market.get("chains") or []
    if chains and chains[0].get("expiry"):
        today = (now or datetime.now(_IST)).astimezone(_IST).date()
        try:
            out["dte"] = (date.fromisoformat(chains[0]["expiry"]) - today).days
        except ValueError:
            pass
    day_o, pdc = lv.get("dayOpen"), lv.get("pdc")
    open_m = _mins(cfg.open)
    if p1 and pdc:
        half = [b for b in p1 if _bar_min(b["t"]) < open_m + 30]
        if half and sess["minutesSinceOpen"] >= 30:
            out["firstHalfHourRetPct"] = round((half[-1]["c"] - pdc) / pdc * 100, 3)
    if not day_o or not p5d:
        out["dayType"] = day_type.classify(out)
        return
    slot = (p5d[-1]["start"] - open_m) // 5
    sigma, source = day_type.noise_sigma(market.get("sessions5") or [], slot), "history"
    if sigma is None:
        close_m = _mins(cfg.close_today(now) if hasattr(cfg, "close_today") else cfg.close)
        sigma = day_type.noise_proxy(out.get("dailyAtr") or 0, pdc or day_o, p5d[-1]["start"] + 5 - open_m, close_m - open_m)
        source = "atr-proxy"
    if sigma:
        out["noise"] = {**day_type.noise_area(day_o, pdc, sigma, p5d[-1]["c"]), "source": source}
        if len(p5d) >= 2:
            out["noise"]["prevState"] = day_type.noise_area(day_o, pdc, sigma, p5d[-2]["c"])["state"]
    out["dayType"] = day_type.classify(out)


def next_level(analysis: dict[str, Any], price: float, up: bool, min_gap: float) -> tuple[str, float] | None:
    """Nearest key level beyond price (in the trade direction) at least `min_gap` away."""
    lv = analysis.get("keyLevels") or []
    if up:
        c = [x for x in lv if x[1] >= price + min_gap]
        return min(c, key=lambda x: x[1]) if c else None
    c = [x for x in lv if x[1] <= price - min_gap]
    return max(c, key=lambda x: x[1]) if c else None
