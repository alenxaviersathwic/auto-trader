"""
Opportunity finders (`opportunity_finders` table): the editable profile of every finder, above all `optionTypes`.

Sessions are offered only the finders whose optionTypes include their scope, and the scan runs a finder only on
underlyings of those types (opportunity_finder/graph/nodes.py). The scan is synchronous code inside the graph, so the
optionTypes are also kept in an in-process cache: filled from the code presets on first use, refreshed from the table at
most every CACHE_TTL_S seconds (refresh()) and immediately after an update. One uvicorn worker, so one cache.
"""
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception.app_exceptions import BadRequestException, NotFoundException
from app.core.logging.logger import logger
from app.core.pagination.page_result import PageResult
from app.modules.opportunity_finder.entity.opportunity_finder_entity import OpportunityFinder
from app.modules.opportunity_finder.repository.opportunity_finder_repository import opportunity_finder_repository as repo
from app.modules.opportunity_finder.schema.opportunity_finder_schema import (
    OPTION_TYPES,
    OpportunityFinderResponse,
    OpportunityFinderSearchFilter,
    OpportunityFinderUpdateRequest,
)

CACHE_TTL_S = 60.0


def _preset_types() -> dict[str, list[str]]:
    from app.modules.trade_history.service.trader_presets import TRADER_PRESETS

    return {p["code"]: list(p["optionTypes"]) for p in TRADER_PRESETS}


class OpportunityFinderService:
    def __init__(self) -> None:
        # filled lazily from the code presets (importing trader_presets at import time would be circular)
        self._types: dict[str, list[str]] = {}
        self._enabled: dict[str, bool] = {}
        self._loaded_at = 0.0

    def _ensure(self) -> None:
        if not self._types:
            self._types = _preset_types()

    # ───────────── cache read by the scan and the session loop (sync) ─────────────
    def option_types(self, code: str | None) -> list[str]:
        from app.modules.trade_history.service.trader_presets import default_option_types, normalize_trader_code

        self._ensure()
        c = normalize_trader_code(code) or ""
        return list(self._types.get(c) or default_option_types(c))

    def covers(self, code: str | None, option_type: str | None) -> bool:
        """Whether finder `code` works on `option_type` (INDEX / COMMODITY) and is enabled."""
        from app.modules.trade_history.service.trader_presets import normalize_trader_code

        c = normalize_trader_code(code) or ""
        return self._enabled.get(c, True) and (option_type or "").upper() in self.option_types(c)

    def codes_for(self, option_type: str | None) -> list[str]:
        """Enabled finder codes that cover `option_type`, in display order."""
        from app.modules.trade_history.service.trader_presets import ALL_PRESET_TRADER_CODES

        return [c for c in ALL_PRESET_TRADER_CODES if self.covers(c, option_type)]

    def _remember(self, rows: list[OpportunityFinder]) -> None:
        self._ensure()
        for r in rows:
            self._types[r.code] = list(r.optionTypes or [])
            self._enabled[r.code] = bool(r.enabled)
        self._loaded_at = time.monotonic()

    async def refresh(self, force: bool = False) -> None:
        """Reload the cache from the table (throttled). Never raises: the scan keeps the last known values."""
        if not force and time.monotonic() - self._loaded_at < CACHE_TTL_S:
            return
        try:
            from app.core.db.session import async_session_factory

            async with async_session_factory() as session:
                self._remember(await repo.list_active(session))
        except Exception as e:  # noqa: BLE001
            self._loaded_at = time.monotonic()  # do not hammer a broken DB every scan
            logger.warning(f"[FINDERS] cache refresh failed, keeping last values: {type(e).__name__}: {e}")

    # ───────────── API ─────────────
    @staticmethod
    def to_response(row: OpportunityFinder) -> OpportunityFinderResponse:
        return OpportunityFinderResponse.model_validate(row)

    async def list_for(self, session: AsyncSession, option_type: str | None = None) -> list[OpportunityFinderResponse]:
        if option_type and option_type.upper() not in OPTION_TYPES:
            raise BadRequestException(message=f"optionType must be one of {list(OPTION_TYPES)}")
        rows = await repo.list_active(session)
        self._remember(rows)
        if option_type:
            rows = [r for r in rows if option_type.upper() in (r.optionTypes or [])]
        return [self.to_response(r) for r in rows]

    async def search(self, session: AsyncSession, f: OpportunityFinderSearchFilter) -> PageResult[OpportunityFinderResponse]:
        if f.optionType and f.optionType.upper() not in OPTION_TYPES:
            raise BadRequestException(message=f"optionType must be one of {list(OPTION_TYPES)}")
        page = await repo.search(session, f)
        return PageResult(list=[self.to_response(r) for r in page.list], page=page.page, limit=page.limit,
                          totalPages=page.totalPages, totalItems=page.totalItems)

    async def get(self, session: AsyncSession, code: str) -> OpportunityFinderResponse:
        row = await repo.get_by_code(session, code)
        if not row:
            raise NotFoundException(message=f"Opportunity finder {code} not found")
        return self.to_response(row)

    async def update(self, session: AsyncSession, code: str, req: OpportunityFinderUpdateRequest) -> OpportunityFinderResponse:
        row = await repo.get_by_code(session, code)
        if not row:
            raise NotFoundException(message=f"Opportunity finder {code} not found")
        data = req.model_dump(exclude_unset=True)
        for field in ("optionTypes", "enabled", "name"):
            if data.get(field) is not None:
                setattr(row, field, data[field])
        saved = await repo.save(session, row)
        await session.commit()
        self._remember(await repo.list_active(session))  # the scan sees the change on its next pass
        return self.to_response(saved)

    async def check_session_finders(self, session: AsyncSession, scope: str, codes: list[str]) -> list[str]:
        """The finders a session of `scope` will use: `codes` (normalized) when given, else every enabled finder that
        covers the scope. Raises when a chosen finder does not cover the scope or none is left."""
        from app.modules.trade_history.service.trader_presets import ALL_PRESET_TRADER_CODES, normalize_trader_code

        try:
            self._remember(await repo.list_active(session))
        except Exception as e:  # noqa: BLE001 -- table not migrated yet / test double: the cached values decide
            logger.warning(f"[FINDERS] using cached optionTypes: {type(e).__name__}: {e}")
        scope = (scope or "").upper()
        if codes:
            wanted = {normalize_trader_code(c) for c in codes}
            if None in wanted:
                raise BadRequestException(message=f"finders must be finder codes: {list(ALL_PRESET_TRADER_CODES)}")
            bad = [c for c in ALL_PRESET_TRADER_CODES if c in wanted and not self.covers(c, scope)]
            if bad:
                raise BadRequestException(
                    message=f"{', '.join(bad)} does not work on {scope} (its optionTypes); pick finders for {scope}")
            out = [c for c in ALL_PRESET_TRADER_CODES if c in wanted]
        else:
            out = self.codes_for(scope)
        if not out:
            raise BadRequestException(message=f"No opportunity finder works on {scope}: set optionTypes on a finder")
        return out


opportunity_finder_service = OpportunityFinderService()
