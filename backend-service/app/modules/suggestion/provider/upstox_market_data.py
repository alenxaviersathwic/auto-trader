from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto.secret_cipher import SecretCipher
from app.modules.suggestion.provider.instrument_resolver import mcx_resolver
from app.modules.suggestion.provider.underlying_config import UnderlyingConfig

BASE = "https://api.upstox.com/v2"


class MarketDataUnavailable(Exception):
    pass


class UpstoxMarketData:
    """Reads candles and option chains from Upstox and cuts them down to a small digest."""

    def __init__(self) -> None:
        self._cipher = SecretCipher()

    async def _token(self, session: AsyncSession) -> str:
        from app.modules.users.entity.upstox_config_entity import (
            UpstoxConfig,  # lazy: read-only token lookup
        )

        res = await session.execute(
            select(UpstoxConfig)
            .where(UpstoxConfig.accessTokenEnc.is_not(None))
            .order_by(UpstoxConfig.lastAuthAt.desc().nulls_last())
            .limit(1)
        )
        cfg = res.scalars().first()
        if not cfg or not cfg.accessTokenEnc:
            raise MarketDataUnavailable("No authenticated Upstox account")
        exp = cfg.tokenExpiresAt
        if exp is not None:
            exp = exp if exp.tzinfo else exp.replace(tzinfo=UTC)
            if exp < datetime.now(UTC):
                raise MarketDataUnavailable(
                    f"Upstox token expired at {exp.astimezone().strftime('%d %b %H:%M')}. "
                    "Log in to Upstox again in Users & Accounts"
                )
        return self._cipher.decrypt(cfg.accessTokenEnc)

    @staticmethod
    async def _get(client: httpx.AsyncClient, url: str, what: str, **kwargs: Any) -> httpx.Response:
        """GET with readable errors, so the tile can say what is wrong instead of a bare status code."""
        r = await client.get(url, **kwargs)
        if r.status_code in (401, 403):
            raise MarketDataUnavailable(
                f"Upstox rejected the access token ({what} {r.status_code}). Log in to Upstox again in Users & Accounts"
            )
        if r.status_code == 429:
            raise MarketDataUnavailable(f"Upstox rate limit hit ({what}); will retry next loop")
        if r.status_code != 200:
            raise MarketDataUnavailable(f"{what} {r.status_code}: {r.text[:120]}")
        return r

    async def fetch(self, cfg: UnderlyingConfig, session: AsyncSession) -> dict[str, Any]:
        key = cfg.instrumentKey
        if not key:  # commodities: nearest MCX futures contract
            try:
                found = await mcx_resolver.resolve(cfg.code)
            except Exception as e:
                raise MarketDataUnavailable(f"{cfg.code}: cannot load MCX instruments ({e})") from e
            if not found:
                raise MarketDataUnavailable(f"{cfg.code}: no running MCX futures contract found")
            key = found["key"]
        token = await self._token(session)
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
            candles = await self._candles(client, key)
            expiries = await self._expiries(client, key)
            chains = []
            for exp in expiries[:2]:  # current and next expiry
                chains.append(await self._chain(client, key, exp))
        spot = chains[0]["spot"] if chains and chains[0].get("spot") else (candles["close"] if candles else 0)
        return {"spot": spot, "candles": candles, "chains": chains, "fetchedAt": datetime.utcnow().isoformat()}

    async def _candles(self, client: httpx.AsyncClient, instrument_key: str) -> dict[str, Any]:
        key = instrument_key.replace("|", "%7C")
        r = await self._get(client, f"{BASE}/historical-candle/intraday/{key}/30minute", "candles")
        rows: list[list[Any]] = r.json().get("data", {}).get("candles", [])  # newest first
        if not rows:
            return {}
        rows = list(reversed(rows))
        closes = [float(x[4]) for x in rows]
        vols = [float(x[5]) if len(x) > 5 and x[5] is not None else 0.0 for x in rows]
        prev = vols[:-1][-8:]  # up to the 8 candles before the latest
        avg = sum(prev) / len(prev) if prev else 0.0
        last_up = float(rows[-1][4]) >= float(rows[-1][1])
        return {
            "open": float(rows[0][1]),
            "high": max(float(x[2]) for x in rows),
            "low": min(float(x[3]) for x in rows),
            "close": closes[-1],
            "trendPct": round((closes[-1] - closes[0]) / closes[0] * 100, 2) if closes[0] else 0.0,
            "last5": closes[-5:],
            "volumeLast": vols[-1],
            "volumeAvg": round(avg, 1),
            "volumeRatio": round(vols[-1] / avg, 2) if avg > 0 else 0.0,  # latest candle vs recent average
            "lastCandleUp": last_up,
        }

    async def _expiries(self, client: httpx.AsyncClient, key: str) -> list[str]:
        r = await self._get(client, f"{BASE}/option/contract", "contracts", params={"instrument_key": key})
        dates = sorted({c.get("expiry") for c in r.json().get("data", []) if c.get("expiry")})
        today = datetime.now().strftime("%Y-%m-%d")
        dates = [d for d in dates if d >= today]
        if not dates:
            raise MarketDataUnavailable("no expiries")
        return dates

    async def _chain(self, client: httpx.AsyncClient, key: str, expiry: str) -> dict[str, Any]:
        r = await self._get(
            client, f"{BASE}/option/chain", "chain", params={"instrument_key": key, "expiry_date": expiry}
        )
        rows = r.json().get("data", [])
        spot = float(rows[0].get("underlying_spot_price", 0)) if rows else 0.0
        strikes = []
        for row in rows:
            leg: dict[str, Any] = {"strike": float(row["strike_price"])}
            for side, k in (("CE", "call_options"), ("PE", "put_options")):
                o = row.get(k) or {}
                md, gk = o.get("market_data") or {}, o.get("option_greeks") or {}
                leg[side] = {
                    "key": o.get("instrument_key"),
                    "ltp": float(md.get("ltp") or 0),
                    "oi": float(md.get("oi") or 0),
                    "volume": float(md.get("volume") or 0),
                    "bid": float(md.get("bid_price") or 0),
                    "ask": float(md.get("ask_price") or 0),
                    "delta": float(gk.get("delta") or 0),
                }
            strikes.append(leg)
        if spot:
            strikes = sorted(strikes, key=lambda s: abs(s["strike"] - spot))[:14]
        call_wall = max((s for s in strikes if s["strike"] >= spot), key=lambda s: s["CE"]["oi"], default=None)
        put_wall = max((s for s in strikes if s["strike"] <= spot), key=lambda s: s["PE"]["oi"], default=None)
        tot_ce = sum(s["CE"]["oi"] for s in strikes) or 1
        tot_pe = sum(s["PE"]["oi"] for s in strikes)
        return {
            "expiry": expiry,
            "spot": spot,
            "pcr": round(tot_pe / tot_ce, 2),
            "resistance": call_wall["strike"] if call_wall else None,
            "support": put_wall["strike"] if put_wall else None,
            "strikes": sorted(strikes, key=lambda s: s["strike"]),
        }


market_data = UpstoxMarketData()
