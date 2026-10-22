from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.entity_status import EntityStatus
from app.core.exception.app_exceptions import NotFoundException
from app.core.pagination.page_result import PageResult
from app.modules.master.entity.master_preference_entity import MasterPreference
from app.modules.master.repository.preference_repository import PreferenceFilter, PreferenceRepository


class PreferenceService:
    def __init__(self, repo: Optional[PreferenceRepository] = None):
        self.repo = repo or PreferenceRepository()

    async def get_by_key(self, session: AsyncSession, key: str) -> MasterPreference:
        pref = await self.repo.get_by_key(session, key)
        if not pref:
            raise NotFoundException(message=f"Preference '{key}' not found")
        return pref

    async def search(self, session: AsyncSession, filter_obj: PreferenceFilter) -> PageResult[MasterPreference]:
        return await self.repo.search(session, filter_obj)

    async def set_key(self, session: AsyncSession, key: str, value: Any) -> MasterPreference:
        pref = await self.repo.get_by_key(session, key)
        if not pref:
            pref = MasterPreference(key=key, value={"value": value} if not isinstance(value, dict) else value)
        else:
            pref.value = {"value": value} if not isinstance(value, dict) else value
            pref.status = EntityStatus.ACTIVE
        return await self.repo.save(session, pref)

    async def delete_key(self, session: AsyncSession, key: str) -> None:
        pref = await self.get_by_key(session, key)
        pref.status = EntityStatus.DELETED
        await self.repo.save(session, pref)
