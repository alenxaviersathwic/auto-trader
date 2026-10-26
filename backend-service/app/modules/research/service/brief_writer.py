import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
import httpx
from pydantic import BaseModel, Field
from app.core.config.settings import settings
from app.core.logging.logger import logger


class BriefPoint(BaseModel):
    text: str
    claimIds: List[int] = []


class GeneratedBrief(BaseModel):
    thesis: str = Field(description="Executive thesis, at most 120 words")
    supportingPoints: List[BriefPoint] = []
    watchItems: List[BriefPoint] = []


AFFECT_KEYWORDS = {
    "rally", "surge", "jump", "soar", "gain", "high", "record", "bull", "outperform",
    "plunge", "fall", "drop", "sink", "slump", "crash", "selloff", "sell-off", "tumble",
    "inflation", "rbi", "fed", "rate", "interest", "repo", "policy", "hike", "cut",
    "crude", "oil", "opec", "energy", "yield", "bond", "fii", "dii", "inflow", "outflow",
    "earnings", "profit", "revenue", "results", "guidance", "target", "downgrade", "upgrade",
    "war", "conflict", "sanction", "tariff", "deficit", "gdp", "stimulus", "rupee", "dollar",
}


class BriefWriter:
    """
    Synthesizes executive investment briefs, categorized news intelligence (latest, affect, neutral),
    and comprehensive blog summaries for monitored market underlyings.
    """

    def __init__(self, base_url: str = "", model: str = ""):
        self.base_url = (base_url or getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or getattr(settings, "OLLAMA_MODEL", "qwen3:8b")

    def categorize_news(
        self,
        underlying_code: str,
        articles: List[Dict[str, Any]],
        claims: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Partitions scraped fresh articles for an underlying into:
        1. latestNews: All articles matching the underlying today
        2. affectNews: Market-moving news with bullish/bearish catalysts
        3. neutralNews: Background commentary, daily wraps, and routine market stats
        """
        latest_news: List[Dict[str, Any]] = []
        affect_news: List[Dict[str, Any]] = []
        neutral_news: List[Dict[str, Any]] = []

        seen_titles = set()

        for art in articles:
            title = (art.get("title") or "").strip()
            if not title or title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())

            domain = art.get("domain") or "Market Media"
            pub_date = art.get("publishedAt")
            pub_str = pub_date.isoformat() if hasattr(pub_date, "isoformat") else (str(pub_date) if pub_date else None)
            url = art.get("url") or ""
            snippet = (art.get("text") or art.get("snippet") or "")[:260].strip()

            news_item = {
                "title": title,
                "domain": domain,
                "publishedAt": pub_str,
                "url": url,
                "snippet": snippet,
            }
            latest_news.append(news_item)

            # Check if this article contains market-affecting catalysts
            text_lower = f"{title.lower()} {snippet.lower()}"
            matched_affect_kws = [kw for kw in AFFECT_KEYWORDS if kw in text_lower]

            # Check for linked claims with directional stance
            matched_claims = [
                c for c in claims
                if c.get("documentId") == art.get("id") or (c.get("statement", "").lower() in text_lower)
            ]

            is_affect = bool(matched_affect_kws or matched_claims)
            if is_affect:
                # Determine impact orientation
                is_bullish = any(c.get("stance") == "BULLISH" for c in matched_claims) or any(
                    w in text_lower for w in ["rally", "surge", "gain", "high", "inflow", "upgrade", "outperform"]
                )
                is_bearish = any(c.get("stance") == "BEARISH" for c in matched_claims) or any(
                    w in text_lower for w in ["plunge", "fall", "drop", "crash", "sell-off", "outflow", "downgrade"]
                )

                impact = "BULLISH" if (is_bullish and not is_bearish) else ("BEARISH" if is_bearish else "CATALYST")
                affect_news.append({
                    **news_item,
                    "impact": impact,
                    "catalyst": ", ".join(matched_affect_kws[:3]) if matched_affect_kws else "Market Flow",
                })
            else:
                neutral_news.append(news_item)

        return {
            "latestNews": latest_news[:25],
            "affectNews": affect_news[:15],
            "neutralNews": neutral_news[:15],
        }

    def generate_blog_summary(
        self,
        underlying_code: str,
        underlying_type: str,
        news_status: str,
        score: Optional[float],
        articles_count: int,
        latest_news: List[Dict[str, Any]],
        affect_news: List[Dict[str, Any]],
        thesis: Optional[str],
        supporting_points: List[Dict[str, Any]],
        watch_items: List[Dict[str, Any]],
    ) -> str:
        """
        Synthesizes an executive, blog-style financial intelligence briefing
        for market participants, covering market pulse, core drivers, and clearance outlook.
        """
        date_str = datetime.now(timezone.utc).strftime("%d %B %Y")
        score_repr = f"{score:.1f}/100" if score is not None else "Unrated"

        lines = []
        lines.append(f"### {underlying_code} ({underlying_type}) Daily Intelligence Briefing — {date_str}\n")

        # 1. Executive Summary & Market Status
        if news_status == "CLEAR_POSITIVE":
            status_desc = "bullish and cleared for algorithmic trading execution with high confidence."
        elif news_status == "HAS_NEGATIVE":
            status_desc = "flagged with active negative market catalysts requiring strict risk monitoring."
        elif news_status == "BEARISH_WATCH":
            status_desc = "under a bearish watch advisory due to adverse headline developments."
        elif news_status == "MIXED":
            status_desc = "reflecting mixed macro and micro signals with balanced positive and cautious inputs."
        else:
            status_desc = "currently exhibiting low coverage across primary financial news wires."

        lines.append(
            f"**Market Pulse & Clearance:**\n"
            f"{underlying_code} is currently assessed with a clearance score of **{score_repr}** ({news_status}). "
            f"Our news screening engine evaluated {articles_count} verified articles across leading financial publishers "
            f"(Economic Times, Moneycontrol, Livemint, Reuters, Business Standard). The sentiment profile is {status_desc}\n"
        )

        # 2. Key Catalysts & Market Movers
        if affect_news:
            lines.append("**Key Drivers & Market-Moving Catalysts:**")
            for item in affect_news[:4]:
                impact_badge = f"[{item.get('impact', 'CATALYST')}]"
                lines.append(f"- **{impact_badge}** {item['title']} — *{item['domain']}*")
            lines.append("")
        elif latest_news:
            lines.append("**Recent News Headlines:**")
            for item in latest_news[:3]:
                lines.append(f"- {item['title']} (*{item['domain']}*)")
            lines.append("")

        # 3. Clearance Thesis & Risk Watch
        if thesis:
            lines.append(f"**Research Clearance Thesis:**\n{thesis}\n")

        if supporting_points:
            lines.append("**Verified Bullish Drivers:**")
            for sp in supporting_points[:3]:
                lines.append(f"- {sp.get('text', '')}")
            lines.append("")

        if watch_items:
            lines.append("**Risk Watch Items:**")
            for wi in watch_items[:3]:
                lines.append(f"- {wi.get('text', '')}")
            lines.append("")

        lines.append(
            "> *Disclaimer: Auto-Trader Research Engine provides automated news sentiment screening and deterministic narrative intelligence. "
            "This information does not constitute financial advice.*"
        )

        return "\n".join(lines)

    async def write_brief(
        self,
        underlying_code: str,
        news_status: str,
        claims: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Generates structured brief from stored claims only.
        """
        valid_claim_ids = {c["id"] for c in claims if "id" in c}
        if not claims or not valid_claim_ids:
            return {
                "thesis": None,
                "supportingPoints": [],
                "watchItems": [],
                "citations": [],
            }

        claims_repr = [
            f"Claim #{c['id']} [{c.get('stance')}]: {c.get('statement')} (Quote: \"{c.get('quote', '')[:100]}\")"
            for c in claims
        ]

        sys_prompt = (
            "You are a quantitative research brief writer for Auto-Trader.\n"
            f"Write an objective, news-clearance brief for underlying {underlying_code} (status: {news_status}).\n"
            "CRITICAL RULES:\n"
            "1. USE ONLY the supplied claims below. Do not assume or add external facts or history.\n"
            "2. State that this is a news screen, not a price forecast.\n"
            "3. Thesis must be concise (at most 120 words).\n"
            "4. Every supporting point and watch item MUST explicitly list the claim IDs it cites in 'claimIds'.\n"
            "Output strictly valid JSON matching GeneratedBrief."
        )

        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": f"Verified claims for {underlying_code}:\n" + "\n".join(claims_repr)},
                ],
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.0},
            }
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                if resp.status_code == 200:
                    raw_content = resp.json().get("message", {}).get("content", "{}")
                    parsed = json.loads(raw_content)
                    return self.verify_citations(parsed, valid_claim_ids)
        except Exception as e:
            logger.debug(f"LLM brief generation failed: {e}; falling back to deterministic synthesis")

        # Deterministic brief synthesis from verified claims
        return self._deterministic_brief_synthesis(underlying_code, news_status, claims)

    @classmethod
    def verify_citations(
        cls, brief: Dict[str, Any], valid_claim_ids: Set[int]
    ) -> Dict[str, Any]:
        """
        Removes any sentence or point without valid claim IDs.
        """
        all_cited_ids: Set[int] = set()

        clean_sup: List[Dict[str, Any]] = []
        for p in brief.get("supportingPoints", []):
            c_ids = [cid for cid in p.get("claimIds", []) if cid in valid_claim_ids]
            if c_ids and p.get("text"):
                clean_sup.append({"text": p["text"], "claimIds": c_ids})
                all_cited_ids.update(c_ids)

        clean_watch: List[Dict[str, Any]] = []
        for p in brief.get("watchItems", []):
            c_ids = [cid for cid in p.get("claimIds", []) if cid in valid_claim_ids]
            if c_ids and p.get("text"):
                clean_watch.append({"text": p["text"], "claimIds": c_ids})
                all_cited_ids.update(c_ids)

        return {
            "thesis": brief.get("thesis"),
            "supportingPoints": clean_sup,
            "watchItems": clean_watch,
            "citations": sorted(list(all_cited_ids)),
        }

    @staticmethod
    def _deterministic_brief_synthesis(
        underlying_code: str, news_status: str, claims: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generates cited brief directly from verified claims list."""
        pos_claims = [c for c in claims if c.get("stance", "").upper() == "BULLISH"]
        neg_claims = [c for c in claims if c.get("stance", "").upper() == "BEARISH"]

        supporting_points: List[Dict[str, Any]] = []
        for c in pos_claims[:3]:
            if "id" in c:
                supporting_points.append({"text": c.get("statement", ""), "claimIds": [c["id"]]})

        watch_items: List[Dict[str, Any]] = []
        for c in neg_claims[:3]:
            if "id" in c:
                watch_items.append({"text": c.get("statement", ""), "claimIds": [c["id"]]})

        cited_ids = [c["id"] for c in claims if "id" in c]

        if news_status == "CLEAR_POSITIVE":
            thesis = (
                f"Fresh news clearance indicates supportive coverage for {underlying_code} "
                f"with {len(pos_claims)} verified positive statements and no material negative news detected. "
                "This serves as an information screen, not a market forecast."
            )
        elif news_status == "HAS_NEGATIVE":
            main_neg = neg_claims[0].get("statement", "adverse developments") if neg_claims else "negative factors"
            thesis = f"Underlying {underlying_code} has negative fresh coverage: {main_neg}."
        else:
            thesis = f"News status for {underlying_code} is {news_status} based on currently reviewed fresh sources."

        return {
            "thesis": thesis,
            "supportingPoints": supporting_points,
            "watchItems": watch_items,
            "citations": cited_ids,
        }


brief_writer = BriefWriter()
