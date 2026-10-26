import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List
import httpx
from app.core.logging.logger import logger


class RssReader:
    """
    Fetches and parses RSS/Atom XML feeds for agency updates and market news.
    """

    @staticmethod
    async def fetch_feed(feed_url: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(feed_url, headers={"User-Agent": "AutoTraderResearchBot/1.0"})
                if resp.status_code != 200:
                    return items
                xml_text = resp.text

            root = ET.fromstring(xml_text)

            # Standard RSS channel -> items
            for item in root.findall(".//item"):
                title_elem = item.find("title")
                link_elem = item.find("link")
                pub_elem = item.find("pubDate")
                desc_elem = item.find("description")

                title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
                link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""

                pub_dt = None
                if pub_elem is not None and pub_elem.text:
                    try:
                        pub_dt = parsedate_to_datetime(pub_elem.text)
                        if pub_dt.tzinfo is None:
                            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                    except Exception:
                        pass

                if link and title:
                    items.append({
                        "title": title,
                        "url": link,
                        "publishedAt": pub_dt,
                        "summary": desc,
                    })

            # Atom feed entry -> items
            if not items:
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall(".//atom:entry", ns) or root.findall(".//entry"):
                    title_elem = entry.find("atom:title", ns) or entry.find("title")
                    link_elem = entry.find("atom:link", ns) or entry.find("link")
                    pub_elem = entry.find("atom:published", ns) or entry.find("published") or entry.find("atom:updated", ns)

                    title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
                    link = link_elem.get("href", "") if link_elem is not None else ""
                    if not link and link_elem is not None and link_elem.text:
                        link = link_elem.text.strip()

                    pub_dt = None
                    if pub_elem is not None and pub_elem.text:
                        try:
                            pub_dt = datetime.fromisoformat(pub_elem.text.replace("Z", "+00:00"))
                        except Exception:
                            pass

                    if link and title:
                        items.append({
                            "title": title,
                            "url": link,
                            "publishedAt": pub_dt,
                            "summary": "",
                        })

        except Exception as e:
            logger.debug(f"RSS feed parse error for {feed_url}: {e}")

        return items
