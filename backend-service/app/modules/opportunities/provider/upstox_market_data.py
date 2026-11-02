import asyncio
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto.secret_cipher import SecretCipher
from app.core.db.entity_status import EntityStatus
from app.core.logging.logger import logger
from app.modules.opportunities.provider.instrument_catalog import OptionContract, instrument_catalog
from app.modules.opportunities.provider.underlying_config import UnderlyingConfig

BASE = "https://api.upstox.com"
VIX_KEY = "NSE_INDEX|India VIX"
_IST = ZoneInfo("Asia/Kolkata")
CHAIN_STRIKES = 14  # strikes kept per expiry around spot (index and MCX)
MCX_STRIKES_FETCHED = 20  # 20 strikes x CE/PE = 40 keys: inside the 50-key option-greek limit


class MarketDataUnavailable(Exception):
    pass


class TokenRejected(MarketDataUnavailable):
    """Upstox answered 401/403: the stored token was revoked (e.g. a newer login with the same API key)."""


def _bars(rows: list[list[Any]]) -> list[dict[str, Any]]:
    """Upstox candle rows [ts, o, h, l, c, volume, oi] (newest first) -> oldest-first dicts."""
    out = []
    for x in reversed(rows or []):
        try:
            out.append({
                "t": str(x[0]), "o": float(x[1]), "h": float(x[2]), "l": float(x[3]), "c": float(x[4]),
                "v": float(x[5]) if len(x) > 5 and x[5] is not None else 0.0,
                "oi": float(x[6]) if len(x) > 6 and x[6] is not None else 0.0,
            })
        except (TypeError, ValueError, IndexError):
            continue
    return out


class UpstoxMarketData:
    """
    One fetch per card per loop:
      spotBars1m   1-minute candles of the price the options follow (index spot / MCX futures)
      futBars1m    1-minute candles of the near-month FUTURE (volume, VWAP, OI buildup; index spot has none)
      daily        last ~25 daily candles (previous-day levels, CPR history, ATR)  -- cached per day
      chains       current + next expiry (index: /v2/option/chain; MCX: built from catalogue + quotes)
      vix          India VIX level and % change (indices only)                       -- cached 60 s
    """

    def __init__(self) -> None:
        self._cipher = SecretCipher()
        self._daily_cache: dict[str, tuple[str, list[dict[str, Any]]]] = {}
        self._expiry_cache: dict[str, tuple[str, list[str]]] = {}
        self._vix_cache: tuple[float, dict[str, Any]] | None = None

    async def _token(self, session: AsyncSession) -> str:
        from app.modules.users.entity.upstox_config_entity import UpstoxConfig  # lazy: read-only token lookup
        from app.modules.users.entity.user_entity import User

        res = await session.execute(
            select(UpstoxConfig)
            .join(User, User.id == UpstoxConfig.userId)
            .where(UpstoxConfig.accessTokenEnc.is_not(None))
            .where(UpstoxConfig.status == EntityStatus.ACTIVE, User.status == EntityStatus.ACTIVE)
            .order_by(User.isDefault.desc(), UpstoxConfig.lastAuthAt.desc().nulls_last())
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
        """GET with readable errors, so the card can say what is wrong instead of a bare status code."""
        r = await client.get(url, **kwargs)
        if r.status_code in (401, 403):
            logger.warning(f"[UPSTOX_TOKEN_REJECTED] {what} {r.status_code}: {r.text[:300]}")
            raise TokenRejected(
                f"Upstox rejected the access token ({what} {r.status_code}). Log in to Upstox again in Users & Accounts"
            )
        if r.status_code == 429:
            raise MarketDataUnavailable(f"Upstox rate limit hit ({what}); will retry next loop")
        if r.status_code != 200:
            raise MarketDataUnavailable(f"{what} {r.status_code}: {r.text[:120]}")
        return r

    async def _with_token(self, session: AsyncSession, fn):
        token = await self._token(session)
        try:
            return await fn(token)
        except TokenRejected:
            from app.modules.users.service.user_service import UserService  # lazy: avoid import cycle

            if not await UserService().reauth_default_after_rejection():
                raise
            session.expire_all()
            return await fn(await self._token(session))

    @staticmethod
    def _client(token: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=15.0, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})

    # ───────────────────────── public ─────────────────────────
    async def fetch(self, cfg: UnderlyingConfig, session: AsyncSession) -> dict[str, Any]:
        if cfg.type == "COMMODITY":
            return await self._with_token(session, lambda t: self._fetch_mcx(cfg, t))
        return await self._with_token(session, lambda t: self._fetch_index(cfg, t))

    async def ltp(self, keys: list[str], session: AsyncSession) -> dict[str, float]:
        """Light re-price of a few instruments (used after a slow AI step)."""
        keys = [k for k in dict.fromkeys(keys) if k]
        if not keys:
            return {}

        async def run(token: str) -> dict[str, float]:
            async with self._client(token) as c:
                data = await self._quotes(c, keys, "ltp")
            return {k: float(v.get("last_price") or 0) for k, v in data.items() if v.get("last_price")}

        return await self._with_token(session, run)

    # ───────────────────────── index ─────────────────────────
    async def _fetch_index(self, cfg: UnderlyingConfig, token: str) -> dict[str, Any]:
        spot_key = cfg.instrumentKey
        if not spot_key:
            raise MarketDataUnavailable(f"{cfg.code}: no index instrument key configured")
        fut = None
        try:
            fut = await instrument_catalog.near_future(cfg.exchange, cfg.code)
        except Exception as e:  # futures data improves the analysis but the chain alone still works
            logger.warning(f"[NO_INDEX_FUTURE] {cfg.code}: {type(e).__name__}: {e}")
        async with self._client(token) as c:
            expiries = await self._index_expiries(c, cfg.code, spot_key)
            results = await asyncio.gather(
                self._intraday(c, spot_key),
                self._intraday(c, fut.key) if fut else _none(),
                self._daily(c, spot_key),
                self._vix(c),
                *(self._index_chain(c, spot_key, exp) for exp in expiries[:2]),
                return_exceptions=True,
            )
        for r in results:
            if isinstance(r, TokenRejected):
                raise r
        spot_bars, fut_bars, daily, vix = (None if isinstance(r, BaseException) else r for r in results[:4])
        chains = []
        for r in results[4:]:
            if isinstance(r, BaseException):
                logger.warning(f"[CHAIN_FAILED] {cfg.code}: {type(r).__name__}: {r}")
            elif r["strikes"]:
                chains.append(r)
        spot = (chains[0]["spot"] if chains and chains[0]["spot"] else 0) or (spot_bars[-1]["c"] if spot_bars else 0)
        if not spot:
            raise MarketDataUnavailable(f"{cfg.code}: no spot price from Upstox")
        logger.info(f"[MARKET] {cfg.code} spot={spot} fut={fut.key if fut else None} bars1m={len(spot_bars or [])} "
                    f"futBars={len(fut_bars or [])} chains={[len(ch['strikes']) for ch in chains]}")
        return self._pack(spot, spot_bars, fut_bars, daily, vix, chains, fut.key if fut else None,
                          await _lot(cfg))

    async def _index_expiries(self, c: httpx.AsyncClient, code: str, key: str) -> list[str]:
        today = datetime.now(_IST).strftime("%Y-%m-%d")
        cached = self._expiry_cache.get(key)
        if cached and cached[0] == today:
            return cached[1]
        r = await self._get(c, f"{BASE}/v2/option/contract", "contracts", params={"instrument_key": key})
        dates = sorted({x.get("expiry") for x in r.json().get("data", []) if x.get("expiry") and x["expiry"] >= today})
        if not dates:
            raise MarketDataUnavailable(f"{code}: no live option expiries from Upstox")
        self._expiry_cache[key] = (today, dates)
        return dates

    async def _index_chain(self, c: httpx.AsyncClient, key: str, expiry: str) -> dict[str, Any]:
        r = await self._get(c, f"{BASE}/v2/option/chain", "chain", params={"instrument_key": key, "expiry_date": expiry})
        rows = r.json().get("data", []) or []
        spot = float(rows[0].get("underlying_spot_price", 0)) if rows else 0.0
        strikes = []
        for row in rows:
            leg: dict[str, Any] = {"strike": float(row["strike_price"])}
            for side, k in (("CE", "call_options"), ("PE", "put_options")):
                o = row.get(k) or {}
                md, gk = o.get("market_data") or {}, o.get("option_greeks") or {}
                leg[side] = _leg(o.get("instrument_key"), md.get("ltp"), md.get("oi"), md.get("volume"),
                                 md.get("bid_price"), md.get("ask_price"), gk.get("delta"), gk.get("iv"))
            strikes.append(leg)
        return _chain(expiry, spot, strikes)

    # ───────────────────────── MCX ─────────────────────────
    async def _fetch_mcx(self, cfg: UnderlyingConfig, token: str) -> dict[str, Any]:
        try:
            contracts = await instrument_catalog.options("MCX", cfg.code)
        except Exception as e:
            raise MarketDataUnavailable(f"{cfg.code}: cannot load the MCX instrument file ({e})") from e
        if not contracts:
            raise MarketDataUnavailable(f"{cfg.code}: no live MCX option contracts in the instrument file")
        expiries = sorted({x.expiry for x in contracts})[:2]
        by_exp = {e: [x for x in contracts if x.expiry == e] for e in expiries}
        # The futures each expiry's options are written on (they differ across expiries).
        fut_key = by_exp[expiries[0]][0].underlyingKey
        async with self._client(token) as c:
            results = await asyncio.gather(
                self._intraday(c, fut_key),
                self._daily(c, fut_key),
                *(self._mcx_chain(c, e, by_exp[e]) for e in expiries),
                return_exceptions=True,
            )
        for r in results:
            if isinstance(r, TokenRejected):
                raise r
        fut_bars, daily = (None if isinstance(r, BaseException) else r for r in results[:2])
        chains = []
        for e, r in zip(expiries, results[2:], strict=True):
            if isinstance(r, BaseException):
                logger.warning(f"[MCX_CHAIN_FAILED] {cfg.code} {e}: {type(r).__name__}: {r}")
            elif r["strikes"]:
                chains.append(r)
            else:
                logger.info(f"[MCX_CHAIN_EMPTY] {cfg.code} {e}: no strike with a live two-sided quote")
        spot = (chains[0]["spot"] if chains else 0) or (fut_bars[-1]["c"] if fut_bars else 0)
        if not spot:
            raise MarketDataUnavailable(f"{cfg.code}: no futures price from Upstox")
        logger.info(f"[MARKET] {cfg.code} fut={fut_key} spot={spot} bars1m={len(fut_bars or [])} "
                    f"chains={[len(ch['strikes']) for ch in chains]}")
        # For MCX the options follow the futures price: spot bars ARE the futures bars.
        return self._pack(spot, fut_bars, fut_bars, daily, None, chains, fut_key, by_exp[expiries[0]][0].lotUnits)

    async def _mcx_chain(self, c: httpx.AsyncClient, expiry: str, contracts: list[OptionContract]) -> dict[str, Any]:
        """Upstox has no MCX option chain: build it from the catalogue + full quotes + v3 option greeks."""
        ukey = contracts[0].underlyingKey
        fq = await self._quotes(c, [ukey], "quotes")
        spot = float((fq.get(ukey) or {}).get("last_price") or 0)
        if spot <= 0:
            return _chain(expiry, 0.0, [])
        by_strike: dict[float, dict[str, OptionContract]] = {}
        for x in contracts:
            if x.underlyingKey == ukey:
                by_strike.setdefault(x.strike, {})[x.side] = x
        near = sorted(by_strike, key=lambda s: abs(s - spot))[:MCX_STRIKES_FETCHED]
        keys = [by_strike[s][side].key for s in near for side in ("CE", "PE") if side in by_strike[s]]
        quotes, greeks = await asyncio.gather(self._quotes(c, keys, "quotes"), self._greeks(c, keys))
        strikes = []
        for s in sorted(near):
            leg: dict[str, Any] = {"strike": s}
            for side in ("CE", "PE"):
                con = by_strike[s].get(side)
                q = quotes.get(con.key) if con else None
                g = greeks.get(con.key) if con else None
                if not con or not q:
                    leg[side] = _leg(con.key if con else None, 0, 0, 0, 0, 0, 0, 0)
                    continue
                depth = q.get("depth") or {}
                bid = ((depth.get("buy") or [{}])[0] or {}).get("price")
                ask = ((depth.get("sell") or [{}])[0] or {}).get("price")
                leg[side] = _leg(con.key, q.get("last_price"), q.get("oi"), q.get("volume"), bid, ask,
                                 (g or {}).get("delta"), (g or {}).get("iv"))
            strikes.append(leg)
        return _chain(expiry, spot, strikes)

    # ───────────────────────── building blocks ─────────────────────────
    async def _quotes(self, c: httpx.AsyncClient, keys: list[str], kind: str) -> dict[str, dict[str, Any]]:
        """Market quotes keyed by instrument key. kind = 'quotes' (full: depth/oi/volume) or 'ltp'."""
        out: dict[str, dict[str, Any]] = {}
        for i in range(0, len(keys), 450):  # API limit 500 keys per request
            chunk = keys[i:i + 450]
            r = await self._get(c, f"{BASE}/v2/market-quote/{kind}", kind, params={"instrument_key": ",".join(chunk)})
            for v in (r.json().get("data") or {}).values():
                k = v.get("instrument_token") or v.get("instrument_key")
                if k:
                    out[k] = v
        return out

    async def _greeks(self, c: httpx.AsyncClient, keys: list[str]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for i in range(0, len(keys), 50):  # option-greek limit: 50 keys
            try:
                r = await self._get(c, f"{BASE}/v3/market-quote/option-greek", "greeks",
                                    params={"instrument_key": ",".join(keys[i:i + 50])})
            except TokenRejected:
                raise
            except MarketDataUnavailable as e:  # greeks are optional: the menu assumes delta 0.5 without them
                logger.warning(f"[GREEKS_UNAVAILABLE] {e}")
                continue
            for v in (r.json().get("data") or {}).values():
                k = v.get("instrument_token") or v.get("instrument_key")
                if k:
                    out[k] = v
        return out

    async def _intraday(self, c: httpx.AsyncClient, key: str) -> list[dict[str, Any]]:
        """Today's 1-minute candles (v2 intraday: '1minute'); 5/15-minute bars are resampled from these."""
        k = key.replace("|", "%7C")
        r = await self._get(c, f"{BASE}/v2/historical-candle/intraday/{k}/1minute", "candles")
        return _bars((r.json().get("data") or {}).get("candles", []))

    async def _daily(self, c: httpx.AsyncClient, key: str) -> list[dict[str, Any]]:
        today = datetime.now(_IST).date()
        cached = self._daily_cache.get(key)
        if cached and cached[0] == today.isoformat():
            return cached[1]
        k = key.replace("|", "%7C")
        frm = (today - timedelta(days=45)).isoformat()
        r = await self._get(c, f"{BASE}/v3/historical-candle/{k}/days/1/{today.isoformat()}/{frm}", "daily candles")
        bars = [b for b in _bars((r.json().get("data") or {}).get("candles", [])) if b["t"][:10] < today.isoformat()]
        self._daily_cache[key] = (today.isoformat(), bars)
        return bars

    async def _vix(self, c: httpx.AsyncClient) -> dict[str, Any] | None:
        if self._vix_cache and time.monotonic() - self._vix_cache[0] < 60:
            return self._vix_cache[1]
        q = (await self._quotes(c, [VIX_KEY], "quotes")).get(VIX_KEY)
        if not q or not q.get("last_price"):
            return None
        last = float(q["last_price"])
        prev = float((q.get("ohlc") or {}).get("close") or 0)
        net = q.get("net_change")
        if net is not None and last - float(net) > 0:
            prev = last - float(net)
        vix = {"value": round(last, 2), "changePct": round((last - prev) / prev * 100, 2) if prev else 0.0}
        self._vix_cache = (time.monotonic(), vix)
        return vix

    @staticmethod
    def _pack(spot, spot_bars, fut_bars, daily, vix, chains, fut_key, lot) -> dict[str, Any]:
        return {
            "spot": spot,
            "spotBars1m": spot_bars or [],
            "futBars1m": fut_bars or [],
            "daily": daily or [],
            "vix": vix,
            "chains": chains,
            "futuresKey": fut_key,
            "lotUnits": lot,
            "fetchedAt": datetime.utcnow().isoformat(),
        }


async def _none() -> None:
    return None


async def _lot(cfg: UnderlyingConfig) -> int:
    try:
        return await instrument_catalog.lot_units(cfg.exchange, cfg.code) or cfg.lotSize
    except Exception:
        return cfg.lotSize


def _f(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _leg(key, ltp, oi, volume, bid, ask, delta, iv) -> dict[str, Any]:
    return {"key": key, "ltp": _f(ltp), "oi": _f(oi), "volume": _f(volume), "bid": _f(bid), "ask": _f(ask),
            "delta": _f(delta), "iv": _f(iv)}


def _chain(expiry: str, spot: float, strikes: list[dict[str, Any]]) -> dict[str, Any]:
    if spot:
        strikes = sorted(strikes, key=lambda s: abs(s["strike"] - spot))[:CHAIN_STRIKES]
    call_wall = max((s for s in strikes if s["strike"] >= spot), key=lambda s: s["CE"]["oi"], default=None)
    put_wall = max((s for s in strikes if s["strike"] <= spot), key=lambda s: s["PE"]["oi"], default=None)
    tot_ce = sum(s["CE"]["oi"] for s in strikes) or 1
    tot_pe = sum(s["PE"]["oi"] for s in strikes)
    atm = min(strikes, key=lambda s: abs(s["strike"] - spot), default=None)
    straddle = (atm["CE"]["ltp"] + atm["PE"]["ltp"]) if atm and atm["CE"]["ltp"] and atm["PE"]["ltp"] else 0.0
    return {
        "expiry": expiry,
        "spot": spot,
        "pcr": round(tot_pe / tot_ce, 2),
        "resistance": call_wall["strike"] if call_wall and call_wall["CE"]["oi"] > 0 else None,
        "support": put_wall["strike"] if put_wall and put_wall["PE"]["oi"] > 0 else None,
        "atmStraddle": round(straddle, 2),
        "strikes": sorted(strikes, key=lambda s: s["strike"]),
    }


market_data = UpstoxMarketData()
