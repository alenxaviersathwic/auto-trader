"""
How busy the system is, as one percentage: the higher of
  cpuPct  1-minute load average / CPU cores (what the machine is doing; None where the OS has no load average)
  appPct  running work units / SYSTEM_APP_CAPACITY, one unit per session loop, session scanner and trade pilot
          (what this app is doing: many sessions and many locked trades mean high load even on an idle CPU)
Pure arithmetic in usage_pct(); snapshot() reads the live numbers.
"""
import os
from typing import Any

from app.core.config.settings import settings


def usage_pct(load_avg_1m: float | None, cpu_count: int | None, units: int, capacity: int) -> dict[str, Any]:
    cpu = round(min(100.0, load_avg_1m / cpu_count * 100), 1) if load_avg_1m is not None and cpu_count else None
    app = round(min(100.0, units / max(1, capacity) * 100), 1)
    return {"cpuPct": cpu, "appPct": app, "usagePct": max(app, cpu or 0.0)}


def snapshot() -> dict[str, Any]:
    from app.modules.sessions.engine.session_loop_runner import active_counts
    from app.modules.trades.engine.trade_pilot_runner import active_count

    counts = {**active_counts(), "tradePilots": active_count()}
    try:
        load1 = os.getloadavg()[0]
    except (AttributeError, OSError):  # Windows: no load average
        load1 = None
    units = sum(counts.values())
    return {**usage_pct(load1, os.cpu_count(), units, settings.SYSTEM_APP_CAPACITY), **counts, "units": units,
            "capacity": settings.SYSTEM_APP_CAPACITY}
