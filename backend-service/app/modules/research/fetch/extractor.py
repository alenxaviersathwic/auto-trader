import hashlib
import re
from datetime import datetime, timezone
from typing import Dict, Optional


class ArticleExtractor:
    """
    Cleans raw HTML into normalized article text, metadata, and publish timestamps.
    """

    @staticmethod
    def extract(html: str, fallback_url: str = "") -> Dict[str, Optional[object]]:
        if not html:
            return {
                "title": "",
                "publishedAt": None,
                "canonicalUrl": fallback_url,
                "text": "",
                "wordCount": 0,
                "contentHash": "",
            }

        # 1. Canonical URL
        canonical_match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html, re.I)
        canonical_url = canonical_match.group(1).strip() if canonical_match else fallback_url

        # 2. Title
        title = ""
        og_title = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
        if og_title:
            title = og_title.group(1).strip()
        else:
            title_tag = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.S)
            if title_tag:
                title = re.sub(r'\s+', ' ', title_tag.group(1)).strip()

        # 3. Publish Date
        published_at: Optional[datetime] = None
        date_patterns = [
            r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+name=["\']publish-date["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+name=["\']date["\'][^>]+content=["\']([^"\']+)["\']',
            r'"datePublished":\s*"([^"]+)"',
        ]
        for pat in date_patterns:
            m = re.search(pat, html, re.I)
            if m:
                raw_date = m.group(1).strip()
                try:
                    dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    published_at = dt
                    break
                except Exception:
                    pass

        # 4. Clean body text
        # Remove scripts, styles, noscript, headers, footers, navs
        cleaned = re.sub(r'<(script|style|noscript|nav|header|footer|aside)[^>]*>.*?</\1>', ' ', html, flags=re.I | re.S)
        # Strip all HTML tags
        text = re.sub(r'<[^>]+>', ' ', cleaned)
        # Unescape basic HTML entities
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        words = text.split()
        word_count = len(words)
        content_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()

        return {
            "title": title[:500],
            "publishedAt": published_at,
            "canonicalUrl": canonical_url[:1000],
            "text": text,
            "wordCount": word_count,
            "contentHash": content_hash,
        }
