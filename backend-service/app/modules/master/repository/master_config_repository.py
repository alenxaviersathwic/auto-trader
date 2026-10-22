from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.entity_status import EntityStatus
from app.modules.master.entity.master_config_entity import MasterConfig

DEFAULT_MASTER_CONFIG: Dict[str, Any] = {
    "llm.provider": "ollama",
    "llm.model": "qwen3:8b",
    "llm.temperature": 0.0,
    "llm.contextBudgetTokens": 6000,
    "proposalMode": "CONFIRM_ALWAYS",  # or AUTO_DRAFT_WHEN_CLEAN
    "proposalTtlMinutes": 120,
    "maxToolIterations": 12,
    "maxClarificationRounds": 3,
    "maxRepairs": 2,
    "toolTierCap": "PROPOSE",
    "redactSecrets": True,
    "similarity.duplicateThresholdPct": 90,
    "similarity.overlapThresholdPct": 60,
}


class MasterConfigRepository:
    async def get_all_config(self, session: AsyncSession) -> Dict[str, Any]:
        stmt = select(MasterConfig).where(MasterConfig.status == EntityStatus.ACTIVE)
        res = await session.execute(stmt)
        stored = {item.configKey: item.configValue for item in res.scalars().all()}
        # Merge with defaults
        config = dict(DEFAULT_MASTER_CONFIG)
        config.update(stored)
        return config

    async def get_key(self, session: AsyncSession, key: str) -> Any:
        stmt = select(MasterConfig).where(MasterConfig.configKey == key, MasterConfig.status == EntityStatus.ACTIVE)
        res = await session.execute(stmt)
        item = res.scalar_one_or_none()
        if item:
            return item.configValue
        return DEFAULT_MASTER_CONFIG.get(key)

    async def set_key(self, session: AsyncSession, key: str, value: Any) -> MasterConfig:
        stmt = select(MasterConfig).where(MasterConfig.configKey == key, MasterConfig.status == EntityStatus.ACTIVE)
        res = await session.execute(stmt)
        item = res.scalar_one_or_none()
        if not item:
            item = MasterConfig(configKey=key, configValue=value)
        else:
            item.configValue = value
        session.add(item)
        await session.flush()
        await session.refresh(item)
        return item
