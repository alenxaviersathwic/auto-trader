#!/usr/bin/env python3
"""Backfill REAL 1-minute option candles of EXPIRED series (Upstox Plus "Expired Instruments" API), +-10 strikes
around the ATM at expiry, last 7 sessions of each contract. The app also runs this every Saturday 10:15 IST.

  PYTHONPATH=. python scripts/backfill_expired_options.py --codes NIFTY SENSEX BANKNIFTY --expiries 8
  (1-minute history reaches back ~1 month; --interval 30minute / day go back a year)
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.modules.backtest.service import option_history_service as ohs  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--codes", nargs="+", default=list(ohs.DEFAULT_CODES))
    ap.add_argument("--expiries", type=int, default=8)
    ap.add_argument("--interval", default="1minute", choices=["1minute", "30minute", "day"])
    a = ap.parse_args()
    print(asyncio.run(ohs.backfill_expired(a.codes, a.expiries, a.interval)))
