#!/usr/bin/env python3
"""
Archive strategy records that never drive a trade (11 Nov 2026 research review, gap 3: one source of truth).

Entries come from the CODED setups (app/modules/opportunities/service/setups.py); DB strategies only reach the
(now shadow) LLM as summaries and the against-trend name check. DRAFT and SUSPENDED rows are dead weight that make the
registry look like ~50 strategies are being tested when none has a real trade record. ACTIVE rows are kept (the
against-trend check reads their names); demotion of those is handled by the statistical kill rule in guardrails.

Goes through StrategyService.update_lifecycle (same transition rules as the UI: ARCHIVED -> DRAFT is the way back).
A JSON file of every row's previous status is written first so the change is reviewable.

  PYTHONPATH=. python scripts/archive_unused_strategies.py            # dry run: prints what would change
  PYTHONPATH=. python scripts/archive_unused_strategies.py --apply    # archives them
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select  # noqa: E402

from app.core.db.entity_status import EntityStatus  # noqa: E402
from app.core.db.session import async_session_factory  # noqa: E402
from app.modules.strategies.entity.strategy_entity import Strategy  # noqa: E402
from app.modules.strategies.schema.strategy_schema import StrategyLifecycleUpdate  # noqa: E402
from app.modules.strategies.service.strategy_service import StrategyService  # noqa: E402

ARCHIVE_FROM = ("DRAFT", "SUSPENDED")
KEEP_PREFIX = "INST_"


async def run(apply: bool) -> None:
    svc = StrategyService()
    async with async_session_factory() as s:
        rows = (await s.execute(select(Strategy).where(Strategy.status == EntityStatus.ACTIVE)
                                .order_by(Strategy.id))).scalars().all()
        # INST_* = the Nov-2026 institutional registry (seed_service): DRAFT on purpose while paper-trading
        targets = [r for r in rows if r.lifecycleStatus in ARCHIVE_FROM and not r.code.startswith(KEEP_PREFIX)]
        keep = [r for r in rows if r not in targets]
        print(f"{len(rows)} strategies: archive {len(targets)} ({'/'.join(ARCHIVE_FROM)}), keep {len(keep)}")
        for r in targets:
            print(f"  archive  #{r.id:<3} {r.code:<34} {r.lifecycleStatus:<10} {r.health}")
        for r in keep:
            print(f"  keep     #{r.id:<3} {r.code:<34} {r.lifecycleStatus:<10} {r.health}")
        if not apply:
            print("\ndry run -- re-run with --apply to archive")
            return
        out = Path(__file__).resolve().parents[1] / "backtest_out" / f"strategy_archive_{datetime.now():%Y%m%d_%H%M%S}.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps([{"id": r.id, "code": r.code, "from": r.lifecycleStatus} for r in targets], indent=1))
        for r in targets:
            await svc.update_lifecycle(s, r.id, StrategyLifecycleUpdate(to="ARCHIVED",
                                                                         reason="unused: entries come from coded setups"))
        await s.commit()
        print(f"\narchived {len(targets)}; previous statuses saved to {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    asyncio.run(run(ap.parse_args().apply))
