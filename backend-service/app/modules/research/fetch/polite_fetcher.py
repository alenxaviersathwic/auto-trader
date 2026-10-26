import asyncio
import time
from typing import Dict, Tuple
import httpx
from app.core.logging.logger import logger
from app.modules.research.fetch.robots_cache import robots_cache

USER_AGENT = "AutoTraderResearchBot/1.0 (+https://autotrader.local/research)"
MAX_PAGE_SIZE = 2 * 1024 * 1024  # 2 MB cap
FETCH_TIMEOUT = 15.0  # 15s time cap
MIN_DOMAIN_INTERVAL = 2.0  # 1 req per 2s per domain


class PoliteFetcher:
    """
    HTTP web fetcher adhering to strict rate limiting, robots.txt, paywall detection, and size caps.
    """

    def __init__(self):
        self._domain_last_request: Dict[str, float] = {}
        self._domain_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()

    async def _get_semaphore(self, domain: str) -> asyncio.Semaphore:
        async with self._lock:
            if domain not in self._domain_semaphores:
                self._domain_semaphores[domain] = asyncio.Semaphore(2)  # max 2 concurrent per domain
            return self._domain_semaphores[domain]

    async def _throttle_domain(self, domain: str) -> None:
        async with self._lock:
            last_req = self._domain_last_request.get(domain, 0.0)
            now = time.time()
            elapsed = now - last_req
            delay = MIN_DOMAIN_INTERVAL - elapsed

        if delay > 0:
            await asyncio.sleep(delay)

        async with self._lock:
            self._domain_last_request[domain] = time.time()

    async def fetch(self, url: str) -> Tuple[str, str, str]:
        """
        Fetches an article HTML with politeness guarantees.
        Returns: (status: "OK" | "BLOCKED" | "PAYWALL" | "ERROR", html: str, final_url: str)
        """
        try:
            parsed = httpx.URL(url)
            domain = parsed.host or "unknown"

            # 1. Check robots.txt
            allowed = await robots_cache.can_fetch(url, USER_AGENT)
            if not allowed:
                return "BLOCKED", "", url

            # 2. Acquire domain semaphore & rate limit
            sem = await self._get_semaphore(domain)
            async with sem:
                await self._throttle_domain(domain)

                headers = {
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                }

                async with httpx.AsyncClient(timeout=FETCH_TIMEOUT, follow_redirects=True) as client:
                    resp = await client.get(url, headers=headers)
                    final_url = str(resp.url)

                    if resp.status_code != 200:
                        return "ERROR", "", final_url

                    # Check size cap
                    content = resp.content
                    if len(content) > MAX_PAGE_SIZE:
                        content = content[:MAX_PAGE_SIZE]

                    html = content.decode("utf-8", errors="replace")

                    # Paywall teaser detection
                    lower_html = html.lower()
                    paywall_markers = [
                        "subscribe to continue reading",
                        "this article is for subscribers only",
                        "to read the full story, subscribe",
                        "premium story - subscribe now",
                        "already a subscriber? log in",
                        "subscribe now for full access",
                    ]
                    if any(marker in lower_html for marker in paywall_markers) and len(html) < 4000:
                        return "PAYWALL", "", final_url

                    return "OK", html, final_url

        except httpx.TimeoutException:
            logger.debug(f"Fetch timeout for {url}")
            return "ERROR", "", url
        except Exception as e:
            logger.debug(f"Fetch error for {url}: {e}")
            return "ERROR", "", url


polite_fetcher = PoliteFetcher()
