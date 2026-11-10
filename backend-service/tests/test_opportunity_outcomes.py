"""Outcome verdicts come only from candles after the signal; ties count as stops; repeat contracts are skipped."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.modules.opportunities.service import run_service as rs
from app.modules.opportunities.service.run_service import DEDUPE_MINUTES, opportunity_run_service as svc

CREATED = datetime(2026, 11, 5, 5, 34, 5, tzinfo=UTC)  # 11:04:05 IST
ENTRY, STOP, TARGET = 100.0, 97.0, 106.0


def _bar(minute_offset, o, h, lo, c):
    t = (CREATED.replace(second=0) + timedelta(minutes=minute_offset)).astimezone(rs._IST)
    return {"t": t.isoformat(), "o": o, "h": h, "l": lo, "c": c}


def _row(outcome="PENDING"):
    return SimpleNamespace(
        id=1, masterId=1, iterationNo=1, ref="R", underlyingCode="NIFTY", underlyingType="INDEX", spot=24000,
        strike=24300, optionType="CE", expiry="2026-11-09", contractId="NIFTY-2026-11-09-24300-CE", confidence=70, rewardRisk=2, rank=1, riskLevel="MEDIUM",
        strategy="VWAP_PULLBACK", reasons=[], risks=[], createdAt=CREATED, validUntil=CREATED + timedelta(minutes=15),
        entry=ENTRY, stop=STOP, target=TARGET, instrumentKey="K", outcome=outcome, resolvedAt=None, timeMachine=None,
    )


class _Md:
    def __init__(self, bars):
        self.bars = bars

    async def ltp(self, keys, session):
        return {"K": ENTRY}

    async def candles_1m_range(self, key, a, b, session):
        return self.bars


@pytest.fixture
def run(monkeypatch):
    synced = []

    async def sync(session, opp):
        synced.append(opp.outcome)

    monkeypatch.setattr(rs.memory_service, "sync_outcome", sync)

    async def go(bars, row=None, rewrite=False):
        monkeypatch.setattr(rs, "market_data", _Md(bars))
        row = row or _row()
        res = (await svc._evaluate_opportunities(object(), [row], rewrite=rewrite))[0]
        return row, res, synced

    return go


@pytest.mark.asyncio
async def test_bar_containing_the_signal_is_ignored(run):
    # minute 0 (11:04) dipped to the stop BEFORE the signal at 11:04:05 -> must not count; later bars hit target
    row, res, _ = await run([_bar(0, 100, 100, 96, 100), _bar(1, 100, 107, 99, 106)])
    assert res["outcome"] == "TARGET_HIT" and res["candlesChecked"] == 1
    assert row.outcome == "TARGET_HIT"


@pytest.mark.asyncio
async def test_bar_touching_both_stop_and_target_is_a_stop(run):
    row, res, _ = await run([_bar(1, 100, 107, 96, 100)])
    assert res["outcome"] == "STOP_HIT" and res["exitPrice"] == STOP


@pytest.mark.asyncio
async def test_stop_before_target_in_later_bars(run):
    _, res, _ = await run([_bar(1, 100, 101, 99, 100), _bar(2, 100, 101, 96.5, 97), _bar(3, 97, 110, 97, 109)])
    assert res["outcome"] == "STOP_HIT"


@pytest.mark.asyncio
async def test_bar_after_window_end_is_ignored(run):
    _, res, _ = await run([_bar(1, 100, 101, 99, 100), _bar(16, 100, 120, 99, 110)])
    assert res["outcome"] != "TARGET_HIT"


@pytest.mark.asyncio
async def test_automatic_pass_never_overwrites_a_resolved_row(run):
    row, res, synced = await run([_bar(1, 100, 101, 96, 97)], row=_row("TARGET_HIT"))
    assert res["outcome"] == "STOP_HIT" and row.outcome == "TARGET_HIT" and synced == []


@pytest.mark.asyncio
async def test_manual_check_corrects_a_snapshot_verdict(run):
    row, _, synced = await run([_bar(1, 100, 101, 96, 97)], row=_row("TARGET_HIT"), rewrite=True)
    assert row.outcome == "STOP_HIT" and synced == ["STOP_HIT"]


@pytest.mark.asyncio
async def test_snapshot_verdict_without_candle_support_goes_back_to_pending(run, monkeypatch):
    monkeypatch.setattr(rs, "datetime", SimpleNamespace(now=lambda tz=None: CREATED + timedelta(minutes=3),
                                                        fromisoformat=datetime.fromisoformat))
    row, res, _ = await run([_bar(1, 100, 101, 99.5, 100)], row=_row("TARGET_HIT"), rewrite=True)
    assert res["outcome"] == "PENDING" and row.outcome == "PENDING"


# ---------------------------------------------------------------- dedupe
def _cand(cid, rank):
    return {"id": cid, "rank": rank, "side": "CE", "strike": 24300, "expiry": "2026-11-09", "entry": 100, "stop": 97,
            "target": 106, "marginPct": 6, "rewardRisk": 2, "confidence": 70, "strategy": "VWAP_PULLBACK",
            "source": "T", "instrumentKey": "K", "spot": 24000}


@pytest.mark.asyncio
async def test_repeat_contract_is_skipped_and_live_row_stays_latest(monkeypatch):
    live = SimpleNamespace(id=7, isLatest=True, outcome="PENDING", validUntil=datetime.now(UTC) + timedelta(minutes=5))
    done = SimpleNamespace(id=8, isLatest=False, outcome="STOP_HIT", validUntil=datetime.now(UTC) - timedelta(minutes=1))
    seen = {}

    async def recent(s, code, since):
        seen["window"] = datetime.now(UTC) - since
        return {"LIVE": live, "DONE": done}

    async def replace(s, code, rows, keep_ids=()):
        seen["rows"], seen["keep"] = rows, set(keep_ids)

    async def remember(*a, **k):
        return None

    monkeypatch.setattr(rs.opportunity_repository, "recent_contracts", recent)
    monkeypatch.setattr(rs.opportunity_repository, "replace_latest", replace)
    monkeypatch.setattr(rs.memory_service, "remember_pending", remember)
    m = SimpleNamespace(id=1, underlyingCode="NIFTY", underlyingType="INDEX", tradeDate="2026-11-05", sessionNo=1)
    picks = [_cand("LIVE", 1), _cand("DONE", 2), _cand("NEW", 3)]
    count, rows = await svc._save(object(), m, 5, picks, {})
    assert count == 1 and [r.contractId for r in rows] == ["NEW"]
    assert seen["keep"] == {7}  # the live duplicate stays latest; the stopped one is not resurrected
    assert timedelta(minutes=DEDUPE_MINUTES - 1) < seen["window"] < timedelta(minutes=DEDUPE_MINUTES + 1)
