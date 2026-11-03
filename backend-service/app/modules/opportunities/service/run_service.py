import asyncio
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import async_session_factory
from app.core.exception.app_exceptions import ConflictException, NotFoundException
from app.core.logging.logger import logger
from app.modules.opportunities.entity.opportunity_entity import OpportunityIteration, OpportunityMaster, TradeOpportunity
from app.modules.opportunities.graph.builder import underlying_graph
from app.modules.opportunities.provider.instrument_catalog import instrument_catalog
from app.modules.opportunities.provider.underlying_config import get_config
from app.modules.opportunities.provider.upstox_market_data import market_data
from app.modules.opportunities.repository.opportunity_repository import (
    make_ref,
    opportunity_iteration_repository as iteration_repo,
    opportunity_master_repository as master_repo,
    opportunity_repository,
    risk_level,
)
from app.modules.opportunities.schema.opportunity_schema import StartOpportunityRequest
from app.modules.opportunities.service import memory_service
from app.modules.opportunities.service.selector import select_underlyings
from app.modules.research.service.run_service import run_service as research_run_service

_IST = ZoneInfo("Asia/Kolkata")
ALL_IN_RESEARCH = 12  # select_underlyings count large enough to return every researched underlying


def _today() -> str:
    return datetime.now(_IST).strftime("%Y-%m-%d")


class OpportunityRunService:
    """
    Card-session model (replaces the old server-side loop):

      Start          -> one new opportunity_masters row per card (sessionNo = Nth start of the day)
      Iterate(id)    -> ONE pass for that card: gather -> menu -> AI -> validate -> save to
                        trade_opportunities, then the master's counters are updated
      Stop(id)/all   -> state = STOPPED; later iterate calls are no-ops

    The frontend drives the loop: it calls iterate on every RUNNING master one by one, waits
    loopGapSeconds, and repeats. A per-master lock stops two tabs iterating the same card at once.
    """

    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = {}

    async def research_has_data(self, session: AsyncSession) -> bool:
        for utype in ("INDEX", "COMMODITY"):
            data = await research_run_service.get_latest_results(utype, session)
            if data.get("run"):
                return True
        return False

    # ───────────────────────── start / stop ─────────────────────────
    async def start(self, req: StartOpportunityRequest, session: AsyncSession) -> dict[str, Any]:
        """New master row per card. A card already RUNNING today is stopped and replaced by the new session."""
        if not await self.research_has_data(session):
            return {"started": False, "reason": "NO_RESEARCH_DATA",
                    "message": "Research Engine has no data yet. Run the Research Engine first.", "masters": []}
        today, now = _today(), datetime.now(UTC)
        await master_repo.close_stale_days(session, today, now)
        if req.underlyings:
            sel = await select_underlyings(session, ALL_IN_RESEARCH, ALL_IN_RESEARCH, req.underlyings)
            found = {c["underlyingCode"]: c for c in sel["items"]}
            # A card the user asked for that is missing from Research still gets a session (shown as missing).
            items = [found.get(code.upper()) or self._missing(code.upper()) for code in req.underlyings
                     if get_config(code.upper())]
        else:
            sel = await select_underlyings(session, req.indexCount, req.commodityCount)
            items = sel["items"]
        if not items:
            return {"started": False, "reason": "NO_UNDERLYINGS", "message": "No matching underlyings in Research.",
                    "masters": []}
        codes = [c["underlyingCode"] for c in items]
        for old in await master_repo.running(session, today, codes):
            old.state, old.stopReason, old.stoppedAt = "STOPPED", "REPLACED_BY_NEW_START", now
        params = req.model_dump(exclude={"underlyings"})
        created: list[OpportunityMaster] = []
        for c in items:
            code = c["underlyingCode"]
            m = OpportunityMaster(
                tradeDate=today, sessionNo=await master_repo.next_session_no(session, today, code),
                underlyingCode=code, underlyingType=c["underlyingType"], state="RUNNING", params=params,
                researchRunId=sel["runId"], researchScore=c.get("opportunityScore") or c.get("score"),
                direction=(c.get("direction") or "").upper() or None, newsStatus=c.get("newsStatus"),
                inResearch=not c.get("_missing", False), startedAt=now,
                lastNote=None if not c.get("_missing") else "Not in the latest Research run",
            )
            created.append(await master_repo.save(session, m))
        await session.commit()
        return {"started": True, "masters": [self.master_dict(m) for m in created]}

    async def stop(self, session: AsyncSession, master_id: int) -> dict[str, Any]:
        m = await master_repo.get(session, master_id)
        if m is None:
            raise NotFoundException(f"Opportunity master {master_id} not found")
        if m.state == "RUNNING":
            m.state, m.stopReason, m.stoppedAt = "STOPPED", "STOPPED_BY_USER", datetime.now(UTC)
            await session.commit()
        return self.master_dict(m)

    async def stop_all(self, session: AsyncSession) -> dict[str, Any]:
        now = datetime.now(UTC)
        rows = await master_repo.running(session)
        for m in rows:
            m.state, m.stopReason, m.stoppedAt = "STOPPED", "STOPPED_BY_USER", now
        await session.commit()
        return {"stopped": len(rows), "masters": [self.master_dict(m) for m in rows]}

    # ───────────────────────── one iteration ─────────────────────────
    async def iterate(self, master_id: int) -> dict[str, Any]:
        lock = self._locks.setdefault(master_id, asyncio.Lock())
        if lock.locked():
            raise ConflictException("This card is already iterating", error={"code": "ITERATION_IN_PROGRESS"})
        async with lock:
            return await self._iterate(master_id)

    async def _iterate(self, master_id: int) -> dict[str, Any]:
        t0, now = time.monotonic(), datetime.now(UTC)
        async with async_session_factory() as s:
            m = await master_repo.get(s, master_id)
            if m is None:
                raise NotFoundException(f"Opportunity master {master_id} not found")
            if m.state == "RUNNING" and m.tradeDate != _today():
                m.state, m.stopReason, m.stoppedAt = "STOPPED", "DAY_ENDED", now
                await s.commit()
            if m.state != "RUNNING":
                return {"master": self.master_dict(m), "ran": False, "saved": 0}
            m.lastStartedAt = now
            code, params, iteration = m.underlyingCode, dict(m.params or {}), m.iterationsCompleted + 1
            sel = await select_underlyings(s, ALL_IN_RESEARCH, ALL_IN_RESEARCH, [code])
            research = sel["items"][0] if sel["items"] else None
            await s.commit()

        picks: list[dict[str, Any]] = []
        prices: dict[str, float] = {}
        note, error = "", None
        diag: dict[str, Any] = {}
        try:
            if research is None:
                note = "Not in the latest Research run -- nothing to analyse until Research covers it again"
                diag = {"result": "NOT_IN_RESEARCH", "reason": note}
            else:
                out = await underlying_graph.ainvoke(
                    {"masterId": master_id, "params": params, "research": research, "code": code}
                )
                note = out.get("error") or out.get("note") or ""
                diag = dict(out.get("diag") or {})
                if "result" not in diag:
                    diag["result"] = self._classify_error(out.get("error"))
                    diag.setdefault("reason", note)
                ranked = sorted(out.get("candidates", []), key=lambda c: (c.get("edge", 0), c["confidence"]),
                                reverse=True)
                picks = ranked[: params.get("maxPerUnderlying", 2)]
                for i, c in enumerate(picks, 1):
                    c["rank"] = i
                for ch in (out.get("market") or {}).get("chains", []):
                    for row in ch["strikes"]:
                        for side in ("CE", "PE"):
                            if row[side]["key"]:
                                prices[row[side]["key"]] = row[side]["ltp"]
        except Exception as e:  # one bad iteration must not kill the card
            logger.error(f"opportunities iterate master={master_id} {code} failed: {type(e).__name__}: {e}")
            error = f"{type(e).__name__}: {e}"
            diag = {"result": "ERROR", "reason": error[:500]}

        async with async_session_factory() as s:
            m = await master_repo.get(s, master_id)
            assert m is not None
            saved = 0
            if error is None:
                saved = await self._save(s, m, iteration, picks, params)
                await memory_service.resolve_outcomes(s, prices)
                m.iterationsCompleted = iteration
                m.lastCompletedAt = datetime.now(UTC)
                m.lastNote, m.lastError = note or None, None
                m.lastOpportunityCount = saved
                m.opportunitiesTotal += saved
                m.topConfidence = max([m.topConfidence] + [c["confidence"] for c in picks])
                m.inResearch = research is not None
                if research is not None:
                    m.researchScore = research.get("opportunityScore") or research.get("score")
                    m.direction = (research.get("direction") or "").upper() or None
                    m.newsStatus = research.get("newsStatus")
            else:
                m.iterationsFailed += 1
                m.lastError = error[:2000]
            m.lastDurationMs = int((time.monotonic() - t0) * 1000)
            await self._record_iteration(s, m, iteration, diag, note or error, saved)
            await s.commit()
            return {"master": self.master_dict(m), "ran": True, "saved": saved}

    @staticmethod
    def _classify_error(err: str | None) -> str:
        e = (err or "").lower()
        if e.startswith("market closed"):
            return "MARKET_CLOSED"
        if e.startswith("market data") or "no option chain" in e or "no strikes" in e:
            return "DATA_ERROR"
        if "futures-only" in e:
            return "NO_CONTRACT"
        return "NO_SETUP"

    @staticmethod
    async def _record_iteration(s: AsyncSession, m: OpportunityMaster, iteration: int, diag: dict[str, Any],
                                summary: str | None, saved: int) -> None:
        """One diagnostics row per batch -- including empty ones, which have no trade_opportunities rows."""
        result = str(diag.get("result") or ("SAVED" if saved else "NO_SETUP"))
        await iteration_repo.save(s, OpportunityIteration(
            masterId=m.id, iterationNo=iteration, underlyingCode=m.underlyingCode, result=result[:20],
            summary=(summary or "")[:2000] or None, savedCount=saved, details=diag,
            durationMs=m.lastDurationMs,
        ))

    async def _save(self, s: AsyncSession, m: OpportunityMaster, iteration: int,
                    picks: list[dict[str, Any]], params: dict[str, Any]) -> int:
        """This iteration's picks become the card's 'latest' set (an empty set clears the old one)."""
        now = datetime.now(UTC)
        valid_until = now + timedelta(minutes=params.get("validMinutes", 15))
        rows = [
            TradeOpportunity(
                masterId=m.id, iterationNo=iteration, ref=make_ref(m.underlyingCode, m, iteration, c["rank"]),
                underlyingCode=m.underlyingCode, underlyingType=m.underlyingType, contractId=c["id"],
                instrumentKey=c.get("instrumentKey"), optionType=c["side"], spot=c.get("spot", 0),
                strike=c["strike"], expiry=c["expiry"], entry=c["entry"], stop=c["stop"], target=c["target"],
                profitMarginPct=c["marginPct"], rewardRisk=c["rewardRisk"], confidence=c["confidence"],
                riskLevel=risk_level(c["confidence"], c["rewardRisk"], c.get("spreadPct", 0)), rank=c["rank"],
                strategy=c.get("strategy"), reasons=c.get("reasons", []), risks=c.get("risks", []),
                source=c["source"], validUntil=valid_until, isLatest=True,
            )
            for c in picks
        ]
        await opportunity_repository.replace_latest(s, m.underlyingCode, rows)
        for row, c in zip(rows, picks, strict=True):
            await memory_service.remember_pending(s, row, c.get("bias", "NEUTRAL"), "UNKNOWN")
        return len(rows)

    # ───────────────────────── reads ─────────────────────────
    async def research_top(self, session: AsyncSession) -> dict[str, Any]:
        """API 1 for the page: best underlyings from the Research Engine (top 5 INDEX + top 3 COMMODITY)."""
        sel = await select_underlyings(session, 5, 3)
        return {
            "hasResearch": sel["runId"] is not None,
            "researchRunId": sel["runId"],
            "list": [
                {
                    "code": c["underlyingCode"],
                    "type": c["underlyingType"],
                    "direction": (c.get("direction") or "").upper() or None,
                    "newsStatus": c.get("newsStatus"),
                    "score": c.get("opportunityScore") or c.get("score"),
                }
                for c in sel["items"]
            ],
        }

    async def today(self, session: AsyncSession) -> dict[str, Any]:
        """
        API 2 for the page: today's newest session (master) per underlying, with its live opportunity
        counts. The page merges this with research_top(): a card with a master shows the master,
        a card without one shows the Research item and a Start button.
        """
        today = _today()
        if await master_repo.close_stale_days(session, today, datetime.now(UTC)):
            await session.commit()
        masters = await master_repo.latest_for_day(session, today)
        latest = await opportunity_repository.latest(session, list(masters)) if masters else []
        now = datetime.now(UTC)
        stats: dict[str, dict[str, int]] = {}
        for op_row in latest:
            if op_row.validUntil < now:
                continue
            d = stats.setdefault(op_row.underlyingCode, {"count": 0, "top": 0, "ce": 0, "pe": 0})
            d["count"] += 1
            d["ce" if op_row.optionType == "CE" else "pe"] += 1
            d["top"] = max(d["top"], op_row.confidence)
        items = []
        for code, m in masters.items():
            st = stats.get(code, {})
            items.append({
                **self.master_dict(m),
                "liveCount": st.get("count", 0), "callCount": st.get("ce", 0), "putCount": st.get("pe", 0),
                "liveTopConfidence": st.get("top", 0),
            })
        return {"tradeDate": today, "list": items}

    async def latest(self, session: AsyncSession, code: str | None = None) -> dict[str, Any]:
        rows = await opportunity_repository.latest(session, [code] if code else None)
        now = datetime.now(UTC)
        items = [self.to_dict(r, now) for r in rows]
        return {"list": items, "generatedAt": max((i["createdAt"] for i in items), default=None)}

    # ───────────────────────── batch / contract outcome verification ─────────────────────────
    async def check_opportunity(self, session: AsyncSession, opportunity_id: int) -> dict[str, Any]:
        """Evaluates ONE opportunity over its entry -> validUntil window using Upstox 1-minute candles."""
        row = await opportunity_repository.get(session, opportunity_id)
        if row is None:
            raise NotFoundException(f"Opportunity {opportunity_id} not found")
        results = await self._evaluate_opportunities(session, [row])
        await session.commit()
        return results[0]

    async def check_batch(
        self, session: AsyncSession, master_id: int, iteration_no: int | None = None
    ) -> dict[str, Any]:
        """Evaluates every opportunity in a master session (or a specific batch) over its entry -> validUntil
        window using Upstox 1-minute candles (+ live LTP if still inside the window) and returns the
        target achievement percentage:
          * +100% if target was hit within the window (before stop)
          * negative % (or actual return / target progress %) if stop was hit or the window ended below entry
          * proportional % toward target if positive but below target."""
        m = await master_repo.get(session, master_id)
        if m is None:
            raise NotFoundException(f"Opportunity master {master_id} not found")
        rows = await opportunity_repository.for_master(session, master_id, iteration_no)
        results = await self._evaluate_opportunities(session, rows)
        await session.commit()
        by_batch: dict[int, list[dict[str, Any]]] = {}
        for r in results:
            by_batch.setdefault(r["iterationNo"], []).append(r)
        batch_summaries: dict[int, dict[str, Any]] = {}
        for it_no, items in by_batch.items():
            avg_pct = round(sum(x["achievedPct"] for x in items) / len(items), 1) if items else 0.0
            best_pct = round(max((x["achievedPct"] for x in items), default=0.0), 1)
            hits = sum(1 for x in items if x["targetAchieved"])
            batch_summaries[it_no] = {
                "iterationNo": it_no,
                "total": len(items),
                "targetHits": hits,
                "avgAchievedPct": avg_pct,
                "bestAchievedPct": best_pct,
                "items": items,
            }
        return {
            "masterId": master_id,
            "iterationNo": iteration_no,
            "checkedAt": datetime.now(UTC).isoformat(),
            "results": results,
            "batches": batch_summaries,
        }

    async def _evaluate_opportunities(
        self, session: AsyncSession, rows: list[TradeOpportunity]
    ) -> list[dict[str, Any]]:
        if not rows:
            return []
        now = datetime.now(UTC)
        # Resolve missing instrumentKey from catalogue if possible
        for r in rows:
            if not r.instrumentKey:
                cfg = get_config(r.underlyingCode)
                if cfg:
                    try:
                        opts = await instrument_catalog.options(cfg.exchange, cfg.code)
                        for o in opts:
                            if o.expiry == r.expiry and abs(o.strike - float(r.strike)) < 0.01 and o.side == r.optionType:
                                r.instrumentKey = o.key
                                break
                    except Exception:
                        pass

        # Fetch live LTP for all distinct instrument keys as fallback / current mark
        keys = [r.instrumentKey for r in rows if r.instrumentKey]
        live_ltps: dict[str, float] = {}
        if keys:
            try:
                live_ltps = await market_data.ltp(keys, session)
            except Exception as e:
                logger.warning(f"[CHECK_LTP_UNAVAILABLE] {e}")

        # Cache 1m candles per (instrumentKey, from_date, to_date)
        candle_cache: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        out: list[dict[str, Any]] = []

        for r in rows:
            entry = float(r.entry)
            target = float(r.target)
            stop = float(r.stop)
            target_move = max(target - entry, 0.01)
            start_dt = r.createdAt if r.createdAt.tzinfo else r.createdAt.replace(tzinfo=UTC)
            end_dt = r.validUntil if r.validUntil.tzinfo else r.validUntil.replace(tzinfo=UTC)
            from_ist = start_dt.astimezone(_IST).strftime("%Y-%m-%d")
            to_ist = end_dt.astimezone(_IST).strftime("%Y-%m-%d")

            bars: list[dict[str, Any]] = []
            if r.instrumentKey:
                ck = (r.instrumentKey, from_ist, to_ist)
                if ck not in candle_cache:
                    try:
                        candle_cache[ck] = await market_data.candles_1m_range(
                            r.instrumentKey, from_ist, to_ist, session
                        )
                    except Exception as e:
                        logger.warning(f"[CHECK_CANDLES_FAILED] {r.instrumentKey}: {e}")
                        candle_cache[ck] = []
                bars = candle_cache[ck]

            # Filter bars in [start_dt - 60s, end_dt]
            win_bars = []
            for b in bars:
                try:
                    bt = datetime.fromisoformat(b["t"])
                    if not bt.tzinfo:
                        bt = bt.replace(tzinfo=_IST)
                    if (start_dt - timedelta(seconds=60)) <= bt <= (end_dt + timedelta(seconds=60)):
                        win_bars.append((bt, b))
                except ValueError:
                    continue

            status_res = "PENDING" if now < end_dt else "EXPIRED"
            hit_time: str | None = None
            peak_price = entry
            trough_price = entry
            exit_price = live_ltps.get(r.instrumentKey or "", entry)

            if win_bars:
                peak_price = max(b["h"] for _, b in win_bars)
                trough_price = min(b["l"] for _, b in win_bars)
                exit_price = win_bars[-1][1]["c"]
                for bt, b in win_bars:
                    if b["h"] >= target:
                        status_res = "TARGET_HIT"
                        exit_price = target
                        hit_time = bt.isoformat()
                        break
                    if b["l"] <= stop:
                        status_res = "STOP_HIT"
                        exit_price = stop
                        hit_time = bt.isoformat()
                        break
            else:
                # Fallback to already-resolved outcome or live LTP
                ltp = live_ltps.get(r.instrumentKey or "")
                if r.outcome == "TARGET_HIT" or (ltp is not None and ltp >= target):
                    status_res = "TARGET_HIT"
                    exit_price = target
                    peak_price = max(entry, ltp or target)
                elif r.outcome == "STOP_HIT" or (ltp is not None and ltp <= stop):
                    status_res = "STOP_HIT"
                    exit_price = stop
                    trough_price = min(entry, ltp or stop)
                elif ltp is not None:
                    exit_price = ltp
                    peak_price = max(entry, ltp)
                    trough_price = min(entry, ltp)

            pnl_points = round(exit_price - entry, 2)
            pnl_pct = round((exit_price - entry) / entry * 100, 2) if entry > 0 else 0.0
            max_gain_pct = round((peak_price - entry) / entry * 100, 2) if entry > 0 else 0.0

            if status_res == "TARGET_HIT":
                achieved_pct = 100.0
            elif exit_price >= entry:
                # Positive progress toward target (0% to 100%)
                achieved_pct = round(min(100.0, (exit_price - entry) / target_move * 100), 1)
            else:
                # Negative progress: show % towards stop or raw negative progress relative to target_move
                achieved_pct = round((exit_price - entry) / target_move * 100, 1)

            # Persist resolved outcome if it newly resolved
            if status_res in ("TARGET_HIT", "STOP_HIT") and r.outcome == "PENDING":
                r.outcome = status_res
                r.resolvedAt = now
            elif status_res == "EXPIRED" and r.outcome == "PENDING" and now >= end_dt:
                r.outcome = "EXPIRED"
                r.resolvedAt = now

            out.append({
                "opportunityId": r.id,
                "masterId": r.masterId,
                "iterationNo": r.iterationNo,
                "ref": r.ref,
                "strike": float(r.strike),
                "optionType": r.optionType,
                "expiry": r.expiry,
                "createdAt": start_dt.isoformat(),
                "validUntil": end_dt.isoformat(),
                "entry": entry,
                "stop": stop,
                "target": target,
                "exitPrice": round(exit_price, 2),
                "peakPrice": round(peak_price, 2),
                "troughPrice": round(trough_price, 2),
                "pnlPoints": pnl_points,
                "pnlPct": pnl_pct,
                "maxGainPct": max_gain_pct,
                "achievedPct": achieved_pct,
                "targetAchieved": status_res == "TARGET_HIT",
                "outcome": status_res,
                "hitAt": hit_time,
                "candlesChecked": len(win_bars),
                "windowEnded": now >= end_dt,
                "series": [
                    {
                        "t": bt.isoformat(),
                        "o": round(b["o"], 2),
                        "h": round(b["h"], 2),
                        "l": round(b["l"], 2),
                        "c": round(b["c"], 2),
                    }
                    for bt, b in win_bars
                ],
            })
        return out

    @staticmethod
    def _missing(code: str) -> dict[str, Any]:
        cfg = get_config(code)
        return {"underlyingCode": code, "underlyingType": cfg.type if cfg else "INDEX", "_missing": True}

    @staticmethod
    def master_dict(m: OpportunityMaster) -> dict[str, Any]:
        iso = lambda d: d.isoformat() if d else None  # noqa: E731
        return {
            "id": m.id, "tradeDate": m.tradeDate, "sessionNo": m.sessionNo, "underlyingCode": m.underlyingCode,
            "underlyingType": m.underlyingType, "state": m.state, "stopReason": m.stopReason,
            "params": m.params, "researchRunId": m.researchRunId,
            "researchScore": float(m.researchScore) if m.researchScore is not None else None,
            "direction": m.direction, "newsStatus": m.newsStatus, "inResearch": m.inResearch,
            "iterationsCompleted": m.iterationsCompleted, "iterationsFailed": m.iterationsFailed,
            "opportunitiesTotal": m.opportunitiesTotal, "lastOpportunityCount": m.lastOpportunityCount,
            "topConfidence": m.topConfidence, "lastNote": m.lastNote, "lastError": m.lastError,
            "lastDurationMs": m.lastDurationMs, "startedAt": iso(m.startedAt), "lastStartedAt": iso(m.lastStartedAt),
            "lastCompletedAt": iso(m.lastCompletedAt), "stoppedAt": iso(m.stoppedAt),
            "createdAt": iso(m.createdAt),
        }

    @staticmethod
    def iteration_dict(i: OpportunityIteration) -> dict[str, Any]:
        return {"id": i.id, "masterId": i.masterId, "iterationNo": i.iterationNo, "underlyingCode": i.underlyingCode,
                "result": i.result, "summary": i.summary, "savedCount": i.savedCount, "details": i.details,
                "durationMs": i.durationMs, "createdAt": i.createdAt.isoformat()}

    @staticmethod
    def to_dict(s: TradeOpportunity, now: datetime) -> dict[str, Any]:
        return {
            "id": s.id, "ref": s.ref, "masterId": s.masterId, "iterationNo": s.iterationNo, "spot": float(s.spot),
            "riskLevel": s.riskLevel, "underlyingCode": s.underlyingCode, "underlyingType": s.underlyingType,
            "contractId": s.contractId, "optionType": s.optionType, "strike": float(s.strike), "expiry": s.expiry,
            "entry": float(s.entry), "stop": float(s.stop), "target": float(s.target),
            "profitMarginPct": float(s.profitMarginPct), "rewardRisk": float(s.rewardRisk),
            "confidence": s.confidence, "rank": s.rank, "strategy": s.strategy, "reasons": s.reasons,
            "risks": s.risks, "source": s.source, "validUntil": s.validUntil.isoformat(),
            "ageSeconds": int((now - s.createdAt).total_seconds()),
            "expired": s.validUntil < now, "outcome": s.outcome, "isLatest": s.isLatest,
            "createdAt": s.createdAt.isoformat(),
        }


opportunity_run_service = OpportunityRunService()

