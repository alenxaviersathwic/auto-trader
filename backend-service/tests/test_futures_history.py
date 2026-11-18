"""fetch_futures_day writes the front future (volume + OI) and the spot, once per day, skipping existing files."""
import asyncio
from types import SimpleNamespace

from app.modules.backtest.service import option_history_service as ohs


def test_writes_futures_and_spot_once(tmp_path, monkeypatch):
    calls: list[str] = []

    async def token():
        return "t"

    async def data(_c, url, **_kw):
        calls.append(url)
        return {"candles": [["2026-11-18T09:15:00+05:30", 1, 2, 0.5, 1.5, 1000, 50000]]}

    class Cat:
        async def near_future(self, _ex, sym):
            return SimpleNamespace(key=f"NSE_FO|{sym}FUT")

    import sys

    # the provider package re-exports the instance under the module's own name, so fetch the module itself
    ic = sys.modules["app.modules.opportunity_finder.provider.instrument_catalog"]

    monkeypatch.setattr(ohs, "DATA_DIR", tmp_path)
    monkeypatch.setattr(ohs, "_token", token)
    monkeypatch.setattr(ohs, "_data", data)
    monkeypatch.setattr(ic, "instrument_catalog", Cat())
    out = asyncio.run(ohs.fetch_futures_day("2026-11-17", ["NIFTY"]))
    assert out == {"NIFTY": 2}
    fut = (tmp_path / "futures" / "2026-11-17" / "NIFTY.csv").read_text().splitlines()
    assert fut[0] == "ts,open,high,low,close,volume,oi" and fut[1].endswith(",1000,50000")
    assert (tmp_path / "spot" / "2026-11-17" / "NIFTY.csv").exists()
    assert any("NIFTYFUT" in u for u in calls) and all("/intraday/" not in u for u in calls)  # past day: dated API
    calls.clear()
    assert asyncio.run(ohs.fetch_futures_day("2026-11-17", ["NIFTY"])) == {"NIFTY": 0} and not calls  # resumable
