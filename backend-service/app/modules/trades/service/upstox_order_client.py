"""
Direct Upstox Order Execution client used when a session has `routeThroughUpstox = True`.
Uses the session user's encrypted Upstox access token (with fallback to default active user token).
"""
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto.secret_cipher import SecretCipher
from app.core.db.entity_status import EntityStatus
from app.core.logging.logger import logger

UPSTOX_ORDER_PLACE_URL = "https://api-hft.upstox.com/v2/order/place"


class UpstoxOrderClient:
    """Places live BUY and SELL option orders on Upstox when `routeThroughUpstox` is enabled."""

    def __init__(self) -> None:
        self._cipher = SecretCipher()

    async def _resolve_token(self, session: AsyncSession, user_id: int) -> str | None:
        from app.modules.users.entity.upstox_config_entity import UpstoxConfig
        from app.modules.users.entity.user_entity import User

        # Prefer the session's userId token first, then fall back to the default active user
        res = await session.execute(
            select(UpstoxConfig)
            .join(User, User.id == UpstoxConfig.userId)
            .where(UpstoxConfig.accessTokenEnc.is_not(None))
            .where(UpstoxConfig.status == EntityStatus.ACTIVE, User.status == EntityStatus.ACTIVE)
            .order_by(
                (UpstoxConfig.userId == user_id).desc(),
                User.isDefault.desc(),
                UpstoxConfig.lastAuthAt.desc().nulls_last(),
            )
            .limit(1)
        )
        cfg = res.scalars().first()
        if not cfg or not cfg.accessTokenEnc:
            return None
        exp = cfg.tokenExpiresAt
        if exp is not None:
            exp = exp if exp.tzinfo else exp.replace(tzinfo=UTC)
            if exp < datetime.now(UTC):
                return None
        return self._cipher.decrypt(cfg.accessTokenEnc)

    async def place_order(
        self,
        session: AsyncSession,
        user_id: int,
        instrument_key: str | None,
        quantity: int,
        transaction_type: str,
        order_type: str = "MARKET",
        price: float = 0.0,
        tag: str = "auto-trader",
    ) -> dict[str, Any]:
        """
        Places an intraday ('I') order on Upstox.
        Returns `{ "ok": bool, "orderId": str | None, "status": str, "error": str | None }`.
        Never raises an unhandled exception so the Trader loop can record `brokerError` cleanly.
        """
        if not instrument_key:
            return {
                "ok": False,
                "orderId": None,
                "status": "ERROR",
                "error": "Missing instrumentKey for Upstox order placement",
            }
        token = await self._resolve_token(session, user_id)
        if not token:
            return {
                "ok": False,
                "orderId": None,
                "status": "ERROR",
                "error": "No valid Upstox access token found for user",
            }

        payload = {
            "quantity": int(quantity),
            "product": "I",
            "validity": "DAY",
            "price": round(float(price), 2) if order_type == "LIMIT" else 0.0,
            "tag": tag[:20],
            "instrument_token": instrument_key,
            "order_type": order_type,
            "transaction_type": transaction_type.upper(),
            "disclosed_quantity": 0,
            "trigger_price": 0.0,
            "is_amo": False,
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(UPSTOX_ORDER_PLACE_URL, json=payload, headers=headers)
            body = resp.json() if resp.content else {}
            if resp.status_code in (200, 201) and body.get("status") == "success":
                order_id = (body.get("data") or {}).get("order_id")
                logger.info(
                    f"[UPSTOX_ORDER_PLACED] {transaction_type} {quantity}x {instrument_key} -> order_id={order_id}"
                )
                return {"ok": True, "orderId": str(order_id) if order_id else None, "status": "PLACED", "error": None}

            errors = body.get("errors") or []
            err_msg = (
                f"{errors[0].get('message', '')} ({errors[0].get('errorCode', '')})".strip()
                if errors
                else body.get("message") or resp.text[:250]
            )
            logger.warning(f"[UPSTOX_ORDER_REJECTED] {transaction_type} {instrument_key}: {resp.status_code} {err_msg}")
            return {"ok": False, "orderId": None, "status": "REJECTED", "error": err_msg[:450]}
        except Exception as e:  # noqa: BLE001
            logger.error(f"[UPSTOX_ORDER_ERROR] {transaction_type} {instrument_key}: {type(e).__name__}: {e}")
            return {"ok": False, "orderId": None, "status": "ERROR", "error": f"{type(e).__name__}: {e}"[:450]}


upstox_order_client = UpstoxOrderClient()

