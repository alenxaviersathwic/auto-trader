"""
Direct Upstox Order Execution client used when a session has `routeThroughUpstox = True`.
Uses the session user's encrypted Upstox access token (with fallback to default active user token).
"""
import asyncio
import time
from collections import deque
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import settings
from app.core.crypto.secret_cipher import SecretCipher
from app.core.db.entity_status import EntityStatus
from app.core.logging.logger import logger

UPSTOX_ORDER_PLACE_URL = "https://api-hft.upstox.com/v2/order/place"
UPSTOX_ORDER_DETAILS_URL = "https://api.upstox.com/v2/order/details"
UPSTOX_ORDER_CANCEL_URL = "https://api-hft.upstox.com/v2/order/cancel"
TICK = 0.05


def limit_price(price: float, side: str, ticks: int) -> float:
    """Marketable LIMIT: `ticks` ticks through the planned price (above for BUY, below for SELL), on the tick grid.
    Caps how far an entry can chase instead of paying whatever the book shows (research gap 5)."""
    raw = float(price) + (ticks * TICK if side.upper() == "BUY" else -ticks * TICK)
    return round(max(TICK, round(raw / TICK) * TICK), 2)


class _RateLimiter:
    """Sliding one-second window; awaits until a slot is free. Single uvicorn worker -> in-process is enough."""

    def __init__(self, per_sec: int) -> None:
        self.per_sec = max(1, per_sec)
        self._sent: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                while self._sent and now - self._sent[0] >= 1.0:
                    self._sent.popleft()
                if len(self._sent) < self.per_sec:
                    self._sent.append(now)
                    return
                await asyncio.sleep(1.0 - (now - self._sent[0]) + 0.001)


class UpstoxOrderClient:
    """Places live BUY and SELL option orders on Upstox when `routeThroughUpstox` is enabled."""

    def __init__(self) -> None:
        self._cipher = SecretCipher()
        self._limiter = _RateLimiter(settings.ORDER_MAX_PER_SEC)

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
        Returns `{ "ok", "orderId", "status", "error", "sentAt", "latencyMs", "requestedPrice" }`.
        Never raises an unhandled exception so the Trader loop can record `brokerError` cleanly.

        MARKET orders always carry `market_protection` (Upstox rejects unprotected API market orders since
        11 Mar 2026, UDAPI1158), every order carries the X-Algo-Name header (SEBI retail-algo framework), and
        sends are rate-limited to ORDER_MAX_PER_SEC.
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
        if order_type in ("MARKET", "SL-M"):
            payload["market_protection"] = settings.UPSTOX_MARKET_PROTECTION
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Algo-Name": settings.UPSTOX_ALGO_NAME,
        }
        meta = {"sentAt": None, "latencyMs": None, "requestedPrice": payload["price"] or float(price or 0)}
        try:
            await self._limiter.acquire()
            meta["sentAt"] = datetime.now(UTC).isoformat()
            t0 = time.perf_counter()
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(UPSTOX_ORDER_PLACE_URL, json=payload, headers=headers)
            meta["latencyMs"] = round((time.perf_counter() - t0) * 1000, 1)
            body = resp.json() if resp.content else {}
            if resp.status_code in (200, 201) and body.get("status") == "success":
                order_id = (body.get("data") or {}).get("order_id")
                logger.info(
                    f"[UPSTOX_ORDER_PLACED] {transaction_type} {quantity}x {instrument_key} {order_type}"
                    f" -> order_id={order_id} ({meta['latencyMs']} ms)"
                )
                return {"ok": True, "orderId": str(order_id) if order_id else None, "status": "PLACED",
                        "error": None, **meta}

            errors = body.get("errors") or []
            err_msg = (
                f"{errors[0].get('message', '')} ({errors[0].get('errorCode', '')})".strip()
                if errors
                else body.get("message") or resp.text[:250]
            )
            logger.warning(f"[UPSTOX_ORDER_REJECTED] {transaction_type} {instrument_key}: {resp.status_code} {err_msg}")
            return {"ok": False, "orderId": None, "status": "REJECTED", "error": err_msg[:450], **meta}
        except Exception as e:  # noqa: BLE001
            logger.error(f"[UPSTOX_ORDER_ERROR] {transaction_type} {instrument_key}: {type(e).__name__}: {e}")
            return {"ok": False, "orderId": None, "status": "ERROR", "error": f"{type(e).__name__}: {e}"[:450], **meta}

    async def wait_for_fill(self, session: AsyncSession, user_id: int, order_id: str | None,
                            timeout_s: float, poll_s: float = 0.5) -> dict[str, Any]:
        """Polls fetch_fill until the order is complete/rejected/cancelled or timeout_s passes; returns the last read."""
        deadline = time.monotonic() + max(0.0, timeout_s)
        last: dict[str, Any] = {"status": None, "averagePrice": None, "filledQty": None}
        while True:
            last = await self.fetch_fill(session, user_id, order_id)
            if (last.get("status") or "").lower() in ("complete", "rejected", "cancelled") or time.monotonic() >= deadline:
                return last
            await asyncio.sleep(poll_s)

    async def cancel_order(self, session: AsyncSession, user_id: int, order_id: str | None) -> bool:
        """Cancels an open order (e.g. an entry LIMIT that did not fill in time). Never raises."""
        if not order_id:
            return False
        token = await self._resolve_token(session, user_id)
        if not token:
            return False
        try:
            await self._limiter.acquire()
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.delete(UPSTOX_ORDER_CANCEL_URL, params={"order_id": order_id},
                                           headers={"Authorization": f"Bearer {token}", "Accept": "application/json",
                                                    "X-Algo-Name": settings.UPSTOX_ALGO_NAME})
            ok = resp.status_code == 200
            logger.info(f"[UPSTOX_ORDER_CANCEL] {order_id} -> {resp.status_code}")
            return ok
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[UPSTOX_ORDER_CANCEL] {order_id}: {type(e).__name__}: {e}")
            return False

    async def fetch_fill(self, session: AsyncSession, user_id: int, order_id: str | None) -> dict[str, Any]:
        """Best-effort fill lookup: `{status, averagePrice, filledQty}` (Nones when unknown). Never raises."""
        empty: dict[str, Any] = {"status": None, "averagePrice": None, "filledQty": None}
        if not order_id:
            return empty
        token = await self._resolve_token(session, user_id)
        if not token:
            return empty
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(UPSTOX_ORDER_DETAILS_URL, params={"order_id": order_id},
                                        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
            d = (resp.json() or {}).get("data") or {}
            avg = d.get("average_price")
            return {"status": d.get("status"), "averagePrice": float(avg) if avg else None,
                    "filledQty": d.get("filled_quantity")}
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[UPSTOX_FILL_LOOKUP] {order_id}: {type(e).__name__}: {e}")
            return empty


upstox_order_client = UpstoxOrderClient()

