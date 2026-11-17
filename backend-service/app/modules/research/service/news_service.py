"""
Research read-outs for other modules (the Commodity Desk and its news sub-agent), through this module's service.

  latest_view(session, code)      the Research Engine's newest read of one underlying: direction, news status, score,
                                  thesis and its newest headlines -- or None when no run covered it
  recent_headlines(code, hours)   fresh RSS headlines that NAME the underlying (whole-word match on cleaned text,
                                  research/service/text_clean.py), newest first. Feeds are the research sources for
                                  that underlying type, each cached for FEED_TTL_S so a burst of moves does not
                                  re-download them. Only real feed items: nothing is made up when nothing matches.
"""
from __future__ import annotations

import asyncio
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging.logger import logger
from app.modules.research.entity.research_entity import ResearchCandidate
from app.modules.research.fetch.rss_reader import RssReader
from app.modules.research.graph.nodes.research_nodes import DEFAULT_SOURCES, DEFAULT_UNDERLYINGS
from app.modules.research.service.text_clean import mentions, strip_furniture

FEED_TTL_S = 180.0
_feed_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def underlying_info(code: str) -> dict[str, Any]:
    return next((u for u in DEFAULT_UNDERLYINGS if u["code"] == code.upper()),
                {"code": code.upper(), "name": code.upper(), "underlyingType": "INDEX", "aliases": [code]})


async def latest_view(session: AsyncSession, code: str) -> dict[str, Any] | None:
    row = (await session.execute(
        select(ResearchCandidate).where(ResearchCandidate.status == 1, ResearchCandidate.underlyingCode == code.upper())
        .order_by(ResearchCandidate.id.desc()).limit(1))).scalar_one_or_none()
    if not row:
        return None
    news = sorted(row.latestNews or [], key=lambda n: str(n.get("publishedAt") or ""), reverse=True)
    return {"direction": row.direction, "newsStatus": row.newsStatus,
            "score": float(row.score) if row.score is not None else None, "thesis": row.thesis,
            "headlines": [{k: n.get(k) for k in ("title", "url", "publishedAt", "domain")} for n in news[:5]],
            "asOf": row.createdAt.isoformat() if row.createdAt else None}


async def _feed(url: str) -> list[dict[str, Any]]:
    hit = _feed_cache.get(url)
    if hit and time.monotonic() - hit[0] < FEED_TTL_S:
        return hit[1]
    try:
        items = await RssReader.fetch_feed(url)
    except Exception as e:  # noqa: BLE001 -- one dead feed must not stop the others
        logger.warning(f"[NEWS] feed {url}: {type(e).__name__}: {e}")
        items = []
    _feed_cache[url] = (time.monotonic(), items)
    return items


async def recent_headlines(code: str, hours: float = 4.0, limit: int = 10) -> list[dict[str, Any]]:
    info = underlying_info(code)
    names = [a.lower() for a in info.get("aliases", [])] + [info["code"].lower()]
    feeds = [s for s in DEFAULT_SOURCES if s.get("feedUrl") and info["underlyingType"] in s.get("appliesToTypes", [])]
    results = await asyncio.gather(*(_feed(s["feedUrl"]) for s in feeds))
    since = datetime.now(UTC) - timedelta(hours=hours)
    out, seen = [], set()
    for src, items in zip(feeds, results, strict=True):
        for it in items:
            title = (it.get("title") or "").strip()
            pub = it.get("publishedAt")
            if not title or title.lower() in seen:
                continue
            if isinstance(pub, datetime) and (pub if pub.tzinfo else pub.replace(tzinfo=UTC)) < since:
                continue
            text = f"{title} {it.get('summary') or ''}"
            if not mentions(text, names):
                continue
            seen.add(title.lower())
            out.append({"title": title, "summary": strip_furniture(re.sub(r"<[^>]+>", " ", it.get("summary") or ""))[:300],
                        "url": it.get("url"), "source": src["name"],
                        "publishedAt": pub.isoformat() if isinstance(pub, datetime) else None})
    out.sort(key=lambda h: h.get("publishedAt") or "", reverse=True)
    return out[:limit]
