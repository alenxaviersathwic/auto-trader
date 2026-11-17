"""
Daily institutional positioning overlay from NSE participant-wise open interest (11 Nov 2026 institutional review,
Strategy 4). A FILTER, never an entry: vendor stand-alone versions lost (FII L/S extreme -65.5k, client vs FII -92.6k),
while 10 years of participant OI show NIFTY returns after FII net-long days far above those after net-short days.

  Source  https://archives.nseindia.com/content/nsccl/fao_participant_oi_DDMMYYYY.csv  (EOD, ~18:00-19:00 IST)
          rows Client / DII / FII / Pro / TOTAL x index futures long/short, index call/put long/short, ...
  Feature FII index-futures long ratio = long / (long + short), smoothed over SMOOTH_DAYS
  Bias    +1 when the smoothed ratio is rising and above BULL_RATIO, or FII flips to net long;
          -1 when it is falling and below BEAR_RATIO; else 0
  Also    the CLIENT index-option book -> gamma_regime.participant_signs() (dealers assumed opposite of clients)

Files: backtest_data/participant_oi/<YYYY-MM-DD>.csv (raw, as published). positioning_job fetches after the close.
"""
import csv
import io
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

from app.core.logging.logger import logger

URL = "https://archives.nseindia.com/content/nsccl/fao_participant_oi_{d:%d%m%Y}.csv"
DIR = Path(__file__).resolve().parents[4] / "backtest_data" / "participant_oi"
SMOOTH_DAYS = 5
BULL_RATIO = 0.25
BEAR_RATIO = 0.15
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/126.0 Safari/537.36", "Accept": "text/csv,*/*", "Referer": "https://www.nseindia.com/"}
_COLS = {
    "future index long": "futLong", "future index short": "futShort",
    "option index call long": "callLong", "option index put long": "putLong",
    "option index call short": "callShort", "option index put short": "putShort",
}


def parse(text: str) -> dict[str, dict[str, float]]:
    """{participant: {futLong, futShort, callLong, putLong, callShort, putShort}} from the published CSV."""
    rows = [r for r in csv.reader(io.StringIO(text)) if r and any(x.strip() for x in r)]
    hdr_i = next((i for i, r in enumerate(rows) if r[0].strip().lower() == "client type"), None)
    if hdr_i is None:
        raise ValueError("participant OI file: header row not found")
    hdr = [h.strip().lower() for h in rows[hdr_i]]
    out: dict[str, dict[str, float]] = {}
    for r in rows[hdr_i + 1:]:
        name = r[0].strip()
        if not name:
            continue
        rec: dict[str, float] = {}
        for i, h in enumerate(hdr):
            key = _COLS.get(h)
            if key and i < len(r):
                try:
                    rec[key] = float(r[i].strip().replace(",", "") or 0)
                except ValueError:
                    rec[key] = 0.0
        out[name.upper()] = rec
    return out


def fii_long_ratio(p: dict[str, dict[str, float]]) -> float | None:
    f = p.get("FII") or {}
    tot = f.get("futLong", 0) + f.get("futShort", 0)
    return round(f["futLong"] / tot, 4) if tot else None


def bias(ratios: list[float], fii_net: list[float] | None = None) -> int:
    """+1 / 0 / -1 from FII long ratios (oldest first, one per day) and, optionally, FII net futures (long - short)."""
    if len(ratios) < SMOOTH_DAYS + 1:
        return 0
    now = sum(ratios[-SMOOTH_DAYS:]) / SMOOTH_DAYS
    before = sum(ratios[-SMOOTH_DAYS - 1:-1]) / SMOOTH_DAYS
    if fii_net and len(fii_net) >= 2 and fii_net[-2] <= 0 < fii_net[-1]:
        return 1  # flip to net long: the documented "hedge unwind" signal
    if now > before and now > BULL_RATIO:
        return 1
    if now < before and now < BEAR_RATIO:
        return -1
    return 0


def _file(d: date) -> Path:
    return DIR / f"{d.isoformat()}.csv"


async def fetch(d: date) -> dict[str, dict[str, float]] | None:
    """Downloads (or reads the saved copy of) day `d`; None when NSE has no file (holiday / not yet published)."""
    f = _file(d)
    if f.exists():
        return parse(f.read_text())
    try:
        async with httpx.AsyncClient(timeout=20.0, headers=_HEADERS, follow_redirects=True) as c:
            r = await c.get(URL.format(d=d))
        if r.status_code != 200 or "client type" not in r.text.lower():
            return None
        DIR.mkdir(parents=True, exist_ok=True)
        f.write_text(r.text)
        return parse(r.text)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[POSITIONING] {d}: {type(e).__name__}: {e}")
        return None


def load_saved(days: int = 30, until: date | None = None) -> list[tuple[date, dict[str, dict[str, float]]]]:
    """Saved files for the last `days` calendar days up to `until` (oldest first)."""
    until = until or date.today()
    out = []
    for i in range(days, -1, -1):
        d = until - timedelta(days=i)
        f = _file(d)
        if f.exists():
            try:
                out.append((d, parse(f.read_text())))
            except ValueError:
                continue
    return out


def snapshot(until: date | None = None) -> dict[str, Any]:
    """Latest overlay state from saved files: {asOf, fiiLongRatio, ratio5, bias, client} (empty when no data)."""
    hist = load_saved(40, until)
    if not hist:
        return {}
    ratios = [r for _, p in hist if (r := fii_long_ratio(p)) is not None]
    nets = [p["FII"]["futLong"] - p["FII"]["futShort"] for _, p in hist if "FII" in p]
    last_d, last = hist[-1]
    return {"asOf": last_d.isoformat(), "fiiLongRatio": ratios[-1] if ratios else None,
            "ratio5": round(sum(ratios[-SMOOTH_DAYS:]) / min(SMOOTH_DAYS, len(ratios)), 4) if ratios else None,
            "bias": bias(ratios, nets), "client": last.get("CLIENT")}
