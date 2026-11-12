#!/usr/bin/env python3
"""Friday 6 Nov 2026 replay — same engine as backtest_day.py, different day's data.

  PYTHONPATH=. python scripts/backtest_day_fri.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import backtest_day as bd  # noqa: E402
import day_data_fri as ddf  # noqa: E402

bd.DAY = "2026-11-06"
# NIFTY weekly still the contract expiring Mon 9 Nov (Tue 10 Nov is a holiday, same shift as before);
# SENSEX weekly next Thursday 12 Nov unchanged; BANKNIFTY monthly 23 Nov unchanged.
bd.EXPIRY = {"NIFTY": "2026-11-09", "SENSEX": "2026-11-12", "BANKNIFTY": "2026-11-23"}
bd.NEXT_EXPIRY = {}  # no series expires on this day
bd.dd.NIFTY = ddf.FRI_NIFTY
bd.dd.SENSEX = ddf.FRI_SENSEX
bd.dd.BANKNIFTY = ddf.FRI_BANKNIFTY
bd.dd.DAILY = ddf.FRI_DAILY

if __name__ == "__main__":
    bd.main()
