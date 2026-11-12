#!/usr/bin/env python3
"""Download a day's REAL 1-minute option candles (+-12 strikes around the ATM, nearest live expiry) so
scripts/backtest_day*.py prices trades from actual premiums. The app also does this automatically every trading day at
16:05 IST (app/modules/backtest/job/option_history_job.py); this is the manual / catch-up version.

  PYTHONPATH=. python scripts/fetch_day_option_candles.py --day 2026-11-11 --codes NIFTY SENSEX BANKNIFTY
  (token: the logged-in Upstox account from the DB, or UPSTOX_ACCESS_TOKEN)
"""
import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.modules.backtest.service import option_history_service as ohs  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--day", default=date.today().isoformat())
    ap.add_argument("--codes", nargs="+", default=list(ohs.DEFAULT_CODES))
    a = ap.parse_args()
    print(asyncio.run(ohs.fetch_day(a.day, a.codes)))
