import asyncio
import time
import urllib.robotparser
from typing import Dict, Optional
import httpx
from app.core.logging.logger import logger


class RobotsCache:
    """
    In-memory cache for robots.txt rules per domain, ensuring polite web crawling.
    """

    def __init__(self, cache_ttl_seconds: int = 86400):
        self._parsers: Dict[str, urllib.robotparser.RobotFileParser] = {}
        self._timestamps: Dict[str, float] = {}
        self._ttl = cache_ttl_seconds
        self._lock = asyncio.Lock()

    async def can_fetch(self, url: str, user_agent: str = "AutoTraderResearchBot/1.0") -> bool:
        try:
            parsed = httpx.URL(url)
            domain = parsed.host
            if not domain:
                return True

            robots_url = f"{parsed.scheme}://{domain}/robots.txt"

            async with self._lock:
                now = time.time()
                parser = self._parsers.get(domain)
                cached_at = self._timestamps.get(domain, 0.0)

                if parser and (now - cached_at) < self._ttl:
                    return parser.can_fetch(user_agent, str(parsed))

            # Fetch robots.txt with short timeout
            parser = urllib.robotparser.RobotFileParser()
            try:
                async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
                    resp = await client.get(robots_url, headers={"User-Agent": user_agent})
                    if resp.status_code == 200:
                        parser.parse(resp.text.splitlines())
                    elif resp.status_code in [401, 403]:
                        # Disallow all if explicitly forbidden
                        parser.disallow_all = True
                    else:
                        parser.allow_all = True
            except Exception:
                parser.allow_all = True

            async with self._lock:
                self._parsers[domain] = parser
                self._timestamps[domain] = time.time()

            return parser.can_fetch(user_agent, str(parsed))
        except Exception as e:
            logger.debug(f"robots.txt check warning for {url}: {e}")
            return True


robots_cache = RobotsCache()
