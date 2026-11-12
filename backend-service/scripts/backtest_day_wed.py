#!/usr/bin/env python3
"""Wednesday 11 Nov 2026 replay — same engine as backtest_day.py, today's data.

  PYTHONPATH=. python scripts/backtest_day_wed.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import backtest_day as bd  # noqa: E402
import day_data_wed as ddw  # noqa: E402

bd.DAY = "2026-11-11"
# NIFTY weekly = Tue 17 Nov; SENSEX weekly = Thu 12 Nov (tomorrow); BANKNIFTY monthly = Mon 23 Nov (24 Nov Gurpurb holiday)
bd.EXPIRY = {"NIFTY": "2026-11-17", "SENSEX": "2026-11-12", "BANKNIFTY": "2026-11-23"}
bd.NEXT_EXPIRY = {}  # no series expires on this day
bd.dd.NIFTY = ddw.WED_NIFTY
bd.dd.SENSEX = ddw.WED_SENSEX
bd.dd.BANKNIFTY = ddw.WED_BANKNIFTY
bd.dd.DAILY = ddw.WED_DAILY

if __name__ == "__main__":
    bd.main()
