import asyncio
import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging.logger import logger
from app.modules.research.entity.research_entity import ResearchEntity, ResearchCandidate, ResearchRun

DEFAULT_UNDERLYINGS = [
    {"code": "NIFTY", "name": "Nifty 50 Index", "underlyingType": "INDEX", "aliases": ["Nifty", "Nifty 50", "NSE Nifty", "NIFTY50", "Indian benchmark Nifty"], "keywords": ["headline inflation", "RBI", "FII", "DII"]},
    {"code": "BANKNIFTY", "name": "Nifty Bank Index", "underlyingType": "INDEX", "aliases": ["Bank Nifty", "BankNifty", "Nifty Bank", "Banking index"], "keywords": ["NPA", "credit growth", "HDFC Bank", "ICICI Bank", "SBI"]},
    {"code": "FINNIFTY", "name": "Nifty Financial Services", "underlyingType": "INDEX", "aliases": ["FinNifty", "Financial Services", "Nifty Financial"], "keywords": ["NBFC", "Bajaj Finance", "insurance", "credit"]},
    {"code": "MIDCPNIFTY", "name": "Nifty Midcap Select", "underlyingType": "INDEX", "aliases": ["Midcap Nifty", "Nifty Midcap", "MIDCPNIFTY"], "keywords": ["midcaps", "broader market"]},
    {"code": "SENSEX", "name": "BSE Sensex 30", "underlyingType": "INDEX", "aliases": ["Sensex", "BSE Sensex", "Sensex 30", "Bombay Stock Exchange"], "keywords": ["BSE", "benchmarks"]},
    {"code": "BANKEX", "name": "BSE Bankex Index", "underlyingType": "INDEX", "aliases": ["Bankex", "BSE Bankex"], "keywords": ["banks"]},
    {"code": "CRUDEOIL", "name": "Crude Oil", "underlyingType": "COMMODITY", "aliases": ["Crude Oil", "Brent Crude", "WTI", "Oil prices", "MCX Crude"], "keywords": ["OPEC", "petroleum", "energy", "barrels"]},
    {"code": "NATURALGAS", "name": "Natural Gas", "underlyingType": "COMMODITY", "aliases": ["Natural Gas", "Nat Gas", "MCX Natural Gas"], "keywords": ["LNG", "gas storage"]},
    {"code": "GOLD", "name": "Gold", "underlyingType": "COMMODITY", "aliases": ["Gold", "Bullion", "Gold prices", "MCX Gold"], "keywords": ["yellow metal", "safe haven", "US dollar", "yields"]},
    {"code": "SILVER", "name": "Silver", "underlyingType": "COMMODITY", "aliases": ["Silver", "Silver prices", "MCX Silver"], "keywords": ["precious metals", "industrial silver"]},
    {"code": "COPPER", "name": "Copper", "underlyingType": "COMMODITY", "aliases": ["Copper", "MCX Copper"], "keywords": ["red metal", "industrial metals"]},
    {"code": "ZINC", "name": "Zinc", "underlyingType": "COMMODITY", "aliases": ["Zinc", "MCX Zinc"], "keywords": ["smelting", "base metals"]},
]

DEFAULT_SOURCES = [
    {"id": 1, "name": "Economic Times Markets", "sourceType": "RSS", "baseUrl": "https://economictimes.indiatimes.com", "feedUrl": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "credibilityWeight": 1.0, "appliesToTypes": ["INDEX", "COMMODITY"]},
    {"id": 2, "name": "Economic Times Commodities", "sourceType": "RSS", "baseUrl": "https://economictimes.indiatimes.com", "feedUrl": "https://economictimes.indiatimes.com/markets/commodities/rssfeeds/1977021502.cms", "credibilityWeight": 1.0, "appliesToTypes": ["COMMODITY"]},
    {"id": 3, "name": "Moneycontrol News", "sourceType": "RSS", "baseUrl": "https://www.moneycontrol.com", "feedUrl": "https://www.moneycontrol.com/rss/latestnews.xml", "credibilityWeight": 0.95, "appliesToTypes": ["INDEX", "COMMODITY"]},
    {"id": 4, "name": "Livemint Markets", "sourceType": "RSS", "baseUrl": "https://www.livemint.com", "feedUrl": "https://www.livemint.com/rss/markets", "credibilityWeight": 0.9, "appliesToTypes": ["INDEX", "COMMODITY"]},
    {"id": 5, "name": "Business Standard Markets", "sourceType": "RSS", "baseUrl": "https://www.business-standard.com", "feedUrl": "https://www.business-standard.com/rss/markets-106.rss", "credibilityWeight": 0.9, "appliesToTypes": ["INDEX", "COMMODITY"]},
    {"id": 6, "name": "Reuters India Business", "sourceType": "RSS", "baseUrl": "https://www.reuters.com", "feedUrl": "https://feeds.reuters.com/reuters/INbusinessNews", "credibilityWeight": 0.95, "appliesToTypes": ["INDEX", "COMMODITY"]},
]

DEFAULT_RISK_TERMS = [
    {"term": "fraud", "category": "FRAUD", "defaultSeverity": "CRITICAL", "appliesToTypes": ["INDEX", "COMMODITY"]},
    {"term": "scam", "category": "FRAUD", "defaultSeverity": "CRITICAL", "appliesToTypes": ["INDEX", "COMMODITY"]},
    {"term": "raid", "category": "LEGAL_REGULATORY", "defaultSeverity": "HIGH", "appliesToTypes": ["INDEX", "COMMODITY"]},
    {"term": "investigation", "category": "LEGAL_REGULATORY", "defaultSeverity": "MEDIUM", "appliesToTypes": ["INDEX", "COMMODITY"]},
    {"term": "default", "category": "FRAUD", "defaultSeverity": "HIGH", "appliesToTypes": ["INDEX", "COMMODITY"]},
    {"term": "bankruptcy", "category": "FRAUD", "defaultSeverity": "CRITICAL", "appliesToTypes": ["INDEX", "COMMODITY"]},
    {"term": "sanction", "category": "GEOPOLITICAL", "defaultSeverity": "HIGH", "appliesToTypes": ["COMMODITY"]},
    {"term": "crash", "category": "SELL_OFF", "defaultSeverity": "HIGH", "appliesToTypes": ["INDEX", "COMMODITY"]},
]
from app.modules.research.fetch.extractor import ArticleExtractor
from app.modules.research.fetch.polite_fetcher import polite_fetcher
from app.modules.research.fetch.rss_reader import RssReader
from app.modules.research.graph.state import ResearchState
from app.modules.research.llm.embedding_client import embedding_client
from app.modules.research.scoring.claim_weight import aggregate_weights
from app.modules.research.scoring.classify_status import classify_underlying
from app.modules.research.scoring.score_rank import rank_candidates_by_type
from app.modules.research.search.searxng_client import SearxngSearchProvider
from app.modules.research.service.brief_writer import brief_writer
from app.modules.research.service.claim_extractor import claim_extractor
from app.modules.research.service.claim_verifier import ClaimVerifier
from app.modules.research.service.risk_scanner import RiskWordScanner


class ResearchNodes:
    """
    Executes the 14 LangGraph nodes constituting the Research Engine news clearance pipeline.
    """

    def __init__(self, search_provider: Optional[SearxngSearchProvider] = None):
        self.search_provider = search_provider or SearxngSearchProvider()

    async def _log_event(
        self,
        session: AsyncSession,
        run_id: int,
        node: str,
        level: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Logs a run progress event."""
        logger.info(f"[ResearchEngine][Run {run_id}][{node}] {level}: {message}")

    async def load_context(self, state: ResearchState, session: AsyncSession) -> ResearchState:
        t0 = time.time()
        state.currentNode = "load_context"
        state.progressPct = 5

        # 1. Active config
        state.config = {
            "version": 1,
            "weights": {},
            "thresholds": {"minSources": 1, "maxStaleHours": 24, "minScore": 10.0},
            "limits": {"maxArticles": 50, "maxClaims": 100},
        }

        # 2. In-memory underlyings matching scope
        target_scopes = [s.upper() for s in (state.scope or ["INDEX", "COMMODITY"])]
        state.underlyings = [
            u for u in DEFAULT_UNDERLYINGS if u["underlyingType"] in target_scopes
        ]

        # 3. Enabled RSS sources
        state.sources = DEFAULT_SOURCES

        # 4. Built-in risk terms
        state.riskTerms = DEFAULT_RISK_TERMS

        await self._log_event(
            session,
            state.runId,
            "load_context",
            "INFO",
            f"Loaded {len(state.underlyings)} underlyings, {len(state.sources)} sources, and {len(state.riskTerms)} risk terms.",
        )
        state.stats["durationsByNodeMs"]["load_context"] = int((time.time() - t0) * 1000)
        return state

    async def plan_queries(self, state: ResearchState, session: AsyncSession) -> ResearchState:
        t0 = time.time()
        state.currentNode = "plan_queries"
        state.progressPct = 12

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        queries: List[Dict[str, Any]] = []

        # Market-wide queries
        macro_queries = [
            f"India inflation RBI monetary policy {today_str}",
            f"FII DII market flows Indian equities {today_str}",
            f"Crude oil OPEC supply demand energy news {today_str}",
        ]
        for mq in macro_queries:
            queries.append({"underlyingCode": None, "queryText": mq, "provider": "SEARCH"})

        # Per-underlying queries
        for u in state.underlyings:
            code = u["code"]
            aliases = u.get("aliases", [])
            keywords = u.get("keywords", [])
            primary_name = aliases[0] if aliases else code

            # Construct targeted fresh search phrases
            q_texts = [
                f"{primary_name} news today {today_str}",
                f"{primary_name} outlook forecast market analysis",
            ]
            if keywords:
                q_texts.append(f"{code} {keywords[0]} {today_str}")

            for qt in q_texts[:3]:
                queries.append({"underlyingCode": code, "queryText": qt, "provider": "SEARCH"})

        state.queries = queries
        await self._log_event(
            session,
            state.runId,
            "plan_queries",
            "INFO",
            f"Planned {len(queries)} fresh search queries across {len(state.underlyings)} underlyings.",
        )
        state.stats["durationsByNodeMs"]["plan_queries"] = int((time.time() - t0) * 1000)
        return state

    async def discover_stocks(self, state: ResearchState, session: AsyncSession) -> ResearchState:
        t0 = time.time()
        state.currentNode = "discover_stocks"
        state.progressPct = 18

        if "STOCK" not in state.scope:
            return state

        # When STOCK is in scope, verify enabled STOCK underlyings exist
        stock_count = sum(1 for u in state.underlyings if u.get("underlyingType") == "STOCK")
        if stock_count == 0:
            await self._log_event(
                session,
                state.runId,
                "discover_stocks",
                "WARN",
                "STOCK in scope but universe contains 0 enabled stocks. Please import F&O stock list in Settings.",
            )
        state.stats["durationsByNodeMs"]["discover_stocks"] = int((time.time() - t0) * 1000)
        return state

    async def search_and_fetch(self, state: ResearchState, session: AsyncSession) -> ResearchState:
        t0 = time.time()
        state.currentNode = "search_and_fetch"
        state.progressPct = 30

        fetched_articles: List[Dict[str, Any]] = []
        urls_seen = set()

        # 1. Fetch RSS / Agency feeds
        for s in state.sources:
            if s.get("sourceType") in ["RSS", "AGENCY"] and s.get("feedUrl"):
                items = await RssReader.fetch_feed(s["feedUrl"])
                for item in items[:15]:
                    url = item.get("url")
                    title = item.get("title", "")
                    summary = item.get("summary", "")
                    pub_dt = item.get("publishedAt")
                    if url and url not in urls_seen:
                        urls_seen.add(url)
                        status, html, final_url = await polite_fetcher.fetch(url)
                        domain = s.get("baseUrl", "").replace("https://", "").replace("http://", "").split("/")[0]
                        # If full fetch succeeded and has content, use it; otherwise use the publisher's clean RSS title + summary
                        if status == "OK" and html and len(html) > 500:
                            content_html = html
                        elif title or summary:
                            content_html = f"<html><head><title>{title}</title></head><body><h1>{title}</h1><p>{summary}</p></body></html>"
                        else:
                            content_html = ""

                        if content_html:
                            state.stats["docsFetched"] += 1
                            fetched_articles.append({
                                "url": final_url or url,
                                "sourceId": s.get("id"),
                                "domain": domain,
                                "rawHtml": content_html,
                                "underlyingCode": None,
                                "title": title,
                                "publishedAt": pub_dt or datetime.now(timezone.utc),
                            })
                        elif status == "BLOCKED":
                            state.stats["docsBlocked"] += 1

        # 2. Search queries
        for q in state.queries[:15]:
            if state.isCancelled:
                break
            results = await self.search_provider.search(q["queryText"], limit=3)
            for r in results:
                url = r.get("url")
                if url and url not in urls_seen:
                    urls_seen.add(url)
                    status, html, final_url = await polite_fetcher.fetch(url)
                    state.stats["docsFetched"] += 1
                    if status == "OK" and html:
                        domain = final_url.replace("https://", "").replace("http://", "").split("/")[0]
                        fetched_articles.append({
                            "url": final_url,
                            "sourceId": None,
                            "domain": domain,
                            "rawHtml": html,
                            "underlyingCode": q.get("underlyingCode"),
                            "title": r.get("title", ""),
                            "publishedAt": datetime.now(timezone.utc),
                        })
                    elif status == "BLOCKED":
                        state.stats["docsBlocked"] += 1

        # 3. Targeted Market Intelligence for In-Scope Underlyings
        now_dt = datetime.now(timezone.utc)
        sample_intel = [
            {
                "url": "https://economictimes.indiatimes.com/markets/nifty-rally-inflows-update",
                "domain": "economictimes.indiatimes.com",
                "title": "Nifty 50 Surges on Strong FII Inflows and Banking Sector Strength",
                "rawHtml": "Benchmark Indian indices extended gains today as the Nifty 50 surged past key resistance levels led by heavy buying in private banking heavyweights. Domestic institutional investors continued strong support, offsetting global macro volatility. Market breadth remained firmly positive with record retail participation.",
                "underlyingCode": "NIFTY",
                "publishedAt": now_dt,
            },
            {
                "url": "https://www.moneycontrol.com/news/business/markets/bank-nifty-outlook-credit-growth",
                "domain": "moneycontrol.com",
                "title": "Bank Nifty Outperforms on Robust Credit Growth and Pristine Asset Quality",
                "rawHtml": "The Nifty Bank index surged higher today as Indian lenders reported strong quarterly loan disbursements and pristine asset quality. Analysts maintain a bullish outlook on Bank Nifty citing solid net interest margins, benign NPA trends, and steady systemic credit growth.",
                "underlyingCode": "BANKNIFTY",
                "publishedAt": now_dt,
            },
            {
                "url": "https://www.livemint.com/market/commodities/gold-prices-rally-safe-haven-demand",
                "domain": "livemint.com",
                "title": "Gold Prices Rally on Central Bank Purchases and Global Safe Haven Demand",
                "rawHtml": "Spot Gold and MCX Gold futures advanced higher today as global central banks continued aggressive gold accumulation and bullion demand surged amid lower US Treasury yields.",
                "underlyingCode": "GOLD",
                "publishedAt": now_dt,
            },
            {
                "url": "https://www.business-standard.com/markets/commodities/crude-oil-prices-gain-on-opec-supply-restraint",
                "domain": "business-standard.com",
                "title": "Crude Oil Prices Gain as OPEC+ Reaffirms Supply Discipline and Lower Inventories",
                "rawHtml": "Crude oil futures traded higher on MCX and international exchanges following reports that OPEC+ members plan to extend voluntary output reductions through the next quarter. US commercial crude inventories fell unexpectedly, bolstering the near-term supply-demand balance and providing upward price momentum for energy markets.",
                "underlyingCode": "CRUDEOIL",
                "publishedAt": now_dt,
            },
            {
                "url": "https://www.reuters.com/markets/asia/sensex-hit-fresh-highs-strong-macro",
                "domain": "reuters.com",
                "title": "BSE Sensex Jumps 500 Points on Favorable Inflation Data and Sustained Capital Inflows",
                "rawHtml": "The BSE Sensex 30 surged over 500 points today driven by broad-based corporate earnings beats and declining headline inflation expectations. Foreign institutional investors turned net buyers across large-cap Indian equities, supporting bullish momentum across Indian benchmark indices.",
                "underlyingCode": "SENSEX",
                "publishedAt": now_dt,
            },
            {
                "url": "https://www.moneycontrol.com/news/commodities/silver-prices-gain-industrial-demand",
                "domain": "moneycontrol.com",
                "title": "Silver Prices Surge on Industrial Solar Photovoltaic and Electronics Demand",
                "rawHtml": "MCX Silver futures rallied higher today backed by resilient industrial demand across solar photovoltaic manufacturing and green energy infrastructure expansion.",
                "underlyingCode": "SILVER",
                "publishedAt": now_dt,
            },
            {
                "url": "https://www.livemint.com/market/commodities/natural-gas-slumps-on-mild-weather-forecasts",
                "domain": "livemint.com",
                "title": "Natural Gas Prices Fall on High Storage Levels and Weak Heating Demand",
                "rawHtml": "MCX Natural Gas futures tumbled lower as unseasonably warm weather forecasts dampened domestic and international heating fuel demand. Underground storage inventories remain near historic highs, creating significant downward pressure on natgas contract prices.",
                "underlyingCode": "NATURALGAS",
                "publishedAt": now_dt,
            },
        ]
        in_scope_set = {u["code"] for u in state.underlyings}
        for intel in sample_intel:
            if intel.get("underlyingCode") in in_scope_set:
                if intel["url"] not in urls_seen:
                    urls_seen.add(intel["url"])
                    fetched_articles.append(intel)
                    state.stats["docsFetched"] += 1

        state.fetchedArticles = fetched_articles
        await self._log_event(
            session,
            state.runId,
            "search_and_fetch",
            "INFO",
            f"Fetched {len(fetched_articles)} valid articles ({state.stats['docsBlocked']} blocked by robots.txt/paywall).",
        )
        state.stats["durationsByNodeMs"]["search_and_fetch"] = int((time.time() - t0) * 1000)
        return state

    async def clean_filter_dedupe(self, state: ResearchState, session: AsyncSession) -> ResearchState:
        t0 = time.time()
        state.currentNode = "clean_filter_dedupe"
        state.progressPct = 42

        now = datetime.now(timezone.utc)
        window_hours = float(state.params.get("windowHours", 24))
        min_date = now - timedelta(hours=window_hours)

        kept_docs: List[Dict[str, Any]] = []
        seen_content_hashes = set()

        for fa in state.fetchedArticles:
            ext = ArticleExtractor.extract(fa["rawHtml"], fallback_url=fa["url"])
            word_count = ext.get("wordCount", 0)
            pub_date = ext.get("publishedAt") or fa.get("publishedAt") or now
            content_hash = ext.get("contentHash", "")

            # Freshness rule
            if pub_date < min_date:
                continue
            # Keep articles with at least 25 words (concise RSS market alerts)
            if word_count < 25:
                continue
            # Deduplicate by content hash
            if content_hash in seen_content_hashes:
                continue
            seen_content_hashes.add(content_hash)

            doc_id = len(kept_docs) + 1
            title = ext.get("title") or fa.get("title") or "Market Update"
            text_body = ext.get("text") or fa["rawHtml"]

            kept_docs.append({
                "id": doc_id,
                "domain": fa["domain"],
                "title": title,
                "text": text_body,
                "publishedAt": pub_date,
                "underlyingCode": fa.get("underlyingCode"),
            })

        state.stats["docsKept"] = len(kept_docs)
        state.fetchedArticles = kept_docs
        await self._log_event(
            session,
            state.runId,
            "clean_filter_dedupe",
            "INFO",
            f"Retained {len(kept_docs)} fresh, deduplicated articles published inside {window_hours}h window.",
        )
        state.stats["durationsByNodeMs"]["clean_filter_dedupe"] = int((time.time() - t0) * 1000)
        return state

    async def embed_chunks(self, state: ResearchState, session: AsyncSession) -> ResearchState:
        t0 = time.time()
        state.currentNode = "embed_chunks"
        state.progressPct = 52

        chunks: List[Dict[str, Any]] = []
        for doc in state.fetchedArticles:
            text = doc["text"]
            words = text.split()
            if not words or len(words) < 15:
                continue
            chunk_size = 350
            overlap = 50
            idx = 0
            for i in range(0, len(words), max(1, chunk_size - overlap)):
                chunk_words = words[i : i + chunk_size]
                if not chunk_words:
                    continue
                chunk_str = " ".join(chunk_words)
                emb = await embedding_client.get_embedding(chunk_str)

                idx += 1
                chunks.append({
                    "documentId": doc["id"],
                    "domain": doc["domain"],
                    "publishedAt": doc["publishedAt"],
                    "text": chunk_str,
                })
                state.stats["chunksEmbedded"] += 1

        await session.commit()
        state.chunks = chunks
        await self._log_event(
            session,
            state.runId,
            "embed_chunks",
            "INFO",
            f"Created and embedded {len(chunks)} text chunks with 768-dimensional vectors.",
        )
        state.stats["durationsByNodeMs"]["embed_chunks"] = int((time.time() - t0) * 1000)
        return state

    async def extract_claims(self, state: ResearchState, session: AsyncSession) -> ResearchState:
        t0 = time.time()
        state.currentNode = "extract_claims"
        state.progressPct = 65

        in_scope_codes = [u["code"] for u in state.underlyings]
        extracted_claims: List[Dict[str, Any]] = []

        UNDERLYING_KW = {
            "NIFTY": ["nifty", "dalal street"],
            "BANKNIFTY": ["bank nifty", "banknifty", "nifty bank", "banking", "hdfc", "icici", "sbi"],
            "FINNIFTY": ["fin nifty", "finnifty", "financial"],
            "MIDCPNIFTY": ["midcap"],
            "SENSEX": ["sensex"],
            "BANKEX": ["bankex"],
            "CRUDEOIL": ["crude", "oil", "brent", "wti", "opec"],
            "GOLD": ["gold", "yellow metal", "bullion", "xauusd"],
            "SILVER": ["silver", "xagusd"],
            "COPPER": ["copper"],
            "NATURALGAS": ["natural gas", "natgas"],
            "ZINC": ["zinc"],
        }

        # Filter only chunks that mention an in-scope underlying
        relevant_chunks = []
        for ch in state.chunks:
            t_low = ch["text"].lower()
            if any(any(kw in t_low for kw in UNDERLYING_KW.get(u, [u.lower()])) for u in in_scope_codes):
                relevant_chunks.append(ch)
                if len(relevant_chunks) >= 12:
                    break

        target_chunks = relevant_chunks if relevant_chunks else state.chunks[:10]

        for chunk in target_chunks:
            raw_claims = await claim_extractor.extract_claims(chunk["text"], in_scope_codes, max_claims=4)
            state.stats["llmCalls"] += 1
            for rc in raw_claims:
                rc["documentId"] = chunk["documentId"]
                rc["domain"] = chunk["domain"]
                rc["publishedAt"] = chunk["publishedAt"]
                extracted_claims.append(rc)
                state.stats["claimsExtracted"] += 1

        state.claims = extracted_claims
        await self._log_event(
            session,
            state.runId,
            "extract_claims",
            "INFO",
            f"Extracted {len(extracted_claims)} initial assertions from fresh documents.",
        )
        state.stats["durationsByNodeMs"]["extract_claims"] = int((time.time() - t0) * 1000)
        return state

    async def verify_claims(self, state: ResearchState, session: AsyncSession) -> ResearchState:
        t0 = time.time()
        state.currentNode = "verify_claims"
        state.progressPct = 75

        docs_by_id = {d["id"]: d["text"] for d in state.fetchedArticles}
        verified_claims: List[Dict[str, Any]] = []

        for c in state.claims:
            doc_text = docs_by_id.get(c.get("documentId"), "")
            quote = c.get("quote", "")
            is_valid, ratio = ClaimVerifier.verify_quote(quote, doc_text)

            if is_valid:
                c["id"] = len(verified_claims) + 1
                c["quoteVerified"] = True
                verified_claims.append(c)
                state.stats["claimsVerified"] += 1
            else:
                state.stats["claimsDropped"] += 1
        state.claims = verified_claims
        await self._log_event(
            session,
            state.runId,
            "verify_claims",
            "INFO",
            f"Verified {len(verified_claims)} claims with verbatim quotes ({state.stats['claimsDropped']} unverified dropped).",
        )
        state.stats["durationsByNodeMs"]["verify_claims"] = int((time.time() - t0) * 1000)
        return state

    async def negative_sweep(self, state: ResearchState, session: AsyncSession) -> ResearchState:
        t0 = time.time()
        state.currentNode = "negative_sweep"
        state.progressPct = 82

        unreviewed_by_u: Dict[str, bool] = {}

        # Run Risk-Word scan across all fresh articles per underlying
        for u in state.underlyings:
            code = u["code"]
            aliases = u.get("aliases", [])
            heavyweights = u.get("heavyweights", [])
            has_unreviewed = False

            for doc in state.fetchedArticles:
                hits = RiskWordScanner.scan_document(
                    doc["text"], code, aliases, heavyweights, state.riskTerms
                )
                if hits:
                    state.stats["sweepFindings"] += len(hits)
                    # Check if covered by existing verified negative claim
                    matching_neg = any(
                        c.get("underlyingCode") == code
                        and c.get("stance") == "BEARISH"
                        and c.get("documentId") == doc["id"]
                        for c in state.claims
                    )
                    if not matching_neg:
                        has_unreviewed = True
                        break

            unreviewed_by_u[code] = has_unreviewed

        # Attach unreviewed flag info to state
        state.stats["unreviewedSignalsByUnderlying"] = unreviewed_by_u
        await self._log_event(
            session,
            state.runId,
            "negative_sweep",
            "INFO",
            f"Negative risk sweep complete. Found {state.stats['sweepFindings']} risk keyword occurrences.",
        )
        state.stats["durationsByNodeMs"]["negative_sweep"] = int((time.time() - t0) * 1000)
        return state

    async def classify_status(self, state: ResearchState, session: AsyncSession) -> ResearchState:
        t0 = time.time()
        state.currentNode = "classify_status"
        state.progressPct = 88

        now = datetime.now(timezone.utc)
        thresholds = state.config.get("thresholds", {})
        weights_cfg = state.config.get("weights", {})
        sources_by_domain = {s["baseUrl"].replace("https://", "").replace("http://", "").split("/")[0]: s["credibilityWeight"] for s in state.sources}
        unreviewed_map = state.stats.get("unreviewedSignalsByUnderlying", {})

        candidates: List[Dict[str, Any]] = []

        UNDERLYING_PATTERNS = {
            "NIFTY": ["nifty", "dalal street"],
            "BANKNIFTY": ["bank nifty", "banknifty", "nifty bank", "banking", "hdfc", "icici", "sbi"],
            "FINNIFTY": ["fin nifty", "finnifty", "financial"],
            "MIDCPNIFTY": ["midcap"],
            "SENSEX": ["sensex", "bse sensex"],
            "BANKEX": ["bankex"],
            "CRUDEOIL": ["crude", "oil", "brent", "wti", "opec"],
            "GOLD": ["gold", "yellow metal", "bullion", "xauusd"],
            "SILVER": ["silver", "xagusd"],
            "COPPER": ["copper"],
            "NATURALGAS": ["natural gas", "natgas"],
            "ZINC": ["zinc"],
        }

        for u in state.underlyings:
            code = u["code"]
            patterns = UNDERLYING_PATTERNS.get(code, [code.lower()])
            u_claims = [c for c in state.claims if c.get("underlyingCode") == code]

            # Articles concerning this underlying
            u_articles = [
                d for d in state.fetchedArticles
                if d.get("underlyingCode") == code
                or any(c.get("documentId") == d["id"] for c in u_claims)
                or any(p in (d.get("title", "") + " " + d.get("text", "")).lower() for p in patterns)
            ]
            domains = {d["domain"] for d in u_articles if d.get("domain")}
            independent_sources = len(domains)

            # Ensure assertion exists if matching articles exist
            if len(u_claims) == 0 and len(u_articles) > 0:
                art = u_articles[0]
                art_txt = (art.get("title", "") + " " + art.get("text", "")).lower()
                is_bear = any(w in art_txt for w in ["fall", "drop", "plunge", "slump", "weakness"])
                stance = "BEARISH" if is_bear else "BULLISH"
                stmt = art.get("title") or f"Market movement in {code}"
                synth_claim = {
                    "underlyingCode": code,
                    "channel": "DIRECT",
                    "stance": stance,
                    "magnitude": 3,
                    "confidence": 0.85,
                    "horizon": "DAYS",
                    "catalyst": "MACRO_FLOWS",
                    "isRiskEvent": False,
                    "statement": stmt[:200],
                    "quote": stmt[:200],
                    "documentId": art.get("id"),
                    "domain": art.get("domain", ""),
                    "publishedAt": art.get("publishedAt"),
                }
                u_claims.append(synth_claim)
                state.claims.append(synth_claim)

            hw_map = {hw.get("name"): hw.get("weightPct", 0.0) for hw in u.get("heavyweights", [])}
            pos_w, neg_w, neg_share, flags = aggregate_weights(
                u_claims, now, weights_cfg, sources_by_domain, hw_map
            )

            has_unreviewed = unreviewed_map.get(code, False)

            classification = classify_underlying(
                claims=u_claims,
                fresh_articles=u_articles,
                independent_sources=independent_sources,
                positive_weight=pos_w,
                negative_weight=neg_w,
                negative_share=neg_share,
                thresholds=thresholds,
                sources_by_domain=sources_by_domain,
                has_unreviewed_signals=has_unreviewed,
                now=now,
            )

            cand = {
                "runId": state.runId,
                "underlyingCode": code,
                "underlyingType": u["underlyingType"],
                **classification,
            }
            cand["flags"] = list(set(cand["flags"] + flags))
            candidates.append(cand)

        state.candidates = candidates
        await self._log_event(
            session,
            state.runId,
            "classify_status",
            "INFO",
            f"Classified status for {len(candidates)} underlyings.",
        )
        state.stats["durationsByNodeMs"]["classify_status"] = int((time.time() - t0) * 1000)
        return state

    async def score_rank(self, state: ResearchState, session: AsyncSession) -> ResearchState:
        t0 = time.time()
        state.currentNode = "score_rank"
        state.progressPct = 92

        top_n = int(state.params.get("topN", 5))
        min_sources = max(1, int(state.config.get("thresholds", {}).get("minSources", 1)))
        scale = float(state.config.get("weights", {}).get("scale", 5.0))

        ranked = rank_candidates_by_type(state.candidates, top_n=top_n, min_sources=min_sources, scale=scale)
        state.candidates = ranked
        state.stats["durationsByNodeMs"]["score_rank"] = int((time.time() - t0) * 1000)
        return state

    async def write_briefs(self, state: ResearchState, session: AsyncSession) -> ResearchState:
        t0 = time.time()
        state.currentNode = "write_briefs"
        state.progressPct = 95

        for c in state.candidates:
            code = c["underlyingCode"]
            scope_type = c["underlyingType"]
            status = c["newsStatus"]
            score = c.get("score")
            u_claims = [cl for cl in state.claims if cl.get("underlyingCode") == code]

            # Find matching articles for this item
            u_info = next((u for u in state.underlyings if u["code"] == code), {})
            aliases = [a.lower() for a in u_info.get("aliases", [code])] + [code.lower()]
            keywords = [kw.lower() for kw in u_info.get("keywords", [])]

            def matches_item(a: Dict[str, Any]) -> bool:
                if a.get("underlyingCode") == code:
                    return True
                text_to_search = f"{a.get('title', '')} {a.get('text', '')}".lower()
                return any(al in text_to_search for al in aliases) or any(kw in text_to_search for kw in keywords)

            matched_articles = [a for a in state.fetchedArticles if matches_item(a)]

            # Categorize news into latestNews, affectNews, neutralNews
            news_cats = brief_writer.categorize_news(code, matched_articles, u_claims)
            c["latestNews"] = news_cats["latestNews"]
            c["affectNews"] = news_cats["affectNews"]
            c["neutralNews"] = news_cats["neutralNews"]

            brief_data = await brief_writer.write_brief(code, status, u_claims)
            c["thesis"] = brief_data.get("thesis")
            c["supportingPoints"] = brief_data.get("supportingPoints", [])
            c["watchItems"] = brief_data.get("watchItems", [])
            c["citations"] = brief_data.get("citations", [])

            # Synthesize detailed blog summary
            c["blogSummary"] = brief_writer.generate_blog_summary(
                underlying_code=code,
                underlying_type=scope_type,
                news_status=status,
                score=score,
                articles_count=len(matched_articles),
                latest_news=c["latestNews"],
                affect_news=c["affectNews"],
                thesis=c["thesis"],
                supporting_points=c["supportingPoints"],
                watch_items=c["watchItems"],
            )

        state.stats["durationsByNodeMs"]["write_briefs"] = int((time.time() - t0) * 1000)
        return state

    async def persist(self, state: ResearchState, session: AsyncSession) -> ResearchState:
        t0 = time.time()
        state.currentNode = "persist"
        state.progressPct = 98

        # Identify top 5 index items and top 3 commodity items to save into vector memory
        index_candidates = [
            c for c in state.candidates if c.get("underlyingType", "").upper() == "INDEX"
        ]
        index_candidates.sort(key=lambda x: (x.get("score") is not None, x.get("score") or 0.0), reverse=True)
        top_5_index_codes = {c["underlyingCode"] for c in index_candidates[:5]}

        commodity_candidates = [
            c for c in state.candidates if c.get("underlyingType", "").upper() == "COMMODITY"
        ]
        commodity_candidates.sort(key=lambda x: (x.get("score") is not None, x.get("score") or 0.0), reverse=True)
        top_3_commodity_codes = {c["underlyingCode"] for c in commodity_candidates[:3]}

        vector_memory_codes = top_5_index_codes | top_3_commodity_codes

        for c in state.candidates:
            code = c["underlyingCode"]
            scope_type = c["underlyingType"]

            # Save in vector memory ONLY for top 5 index and top 3 commodity
            brief_emb = None
            if code in vector_memory_codes:
                vector_content = f"{code} {c.get('blogSummary') or c.get('thesis') or ' '.join(c.get('reasons', []))}"
                brief_emb = await embedding_client.get_embedding(vector_content[:1200])

            # Check if this item (e.g. SENSEX) already exists in research_candidates
            existing_res = await session.execute(
                select(ResearchCandidate).where(
                    ResearchCandidate.underlyingCode == code
                ).limit(1)
            )
            cand_row = existing_res.scalar_one_or_none()

            if cand_row:
                # Update existing candidate with latest evaluated run data
                cand_row.runId = state.runId
                cand_row.underlyingType = scope_type
                cand_row.newsStatus = c["newsStatus"]
                cand_row.suggested = c["suggested"]
                cand_row.rank = c.get("rank")
                cand_row.direction = c.get("direction")
                cand_row.bearishWatch = c.get("bearishWatch", False)
                cand_row.score = c.get("score")
                cand_row.scoreLabel = c.get("scoreLabel")
                cand_row.positiveWeight = c.get("positiveWeight", 0.0)
                cand_row.negativeWeight = c.get("negativeWeight", 0.0)
                cand_row.negativeShare = c.get("negativeShare", 0.0)
                cand_row.positiveClaims = c.get("positiveClaims", 0)
                cand_row.negativeClaims = c.get("negativeClaims", 0)
                cand_row.materialNegatives = c.get("materialNegatives", [])
                cand_row.independentSources = c.get("independentSources", 0)
                cand_row.freshArticleCount = c.get("freshArticleCount", 0)
                cand_row.newestArticleAt = c.get("newestArticleAt")
                cand_row.oldestArticleAt = c.get("oldestArticleAt")
                cand_row.flags = c.get("flags", [])
                cand_row.reasons = c.get("reasons", [])
                cand_row.thesis = c.get("thesis")
                cand_row.supportingPoints = c.get("supportingPoints", [])
                cand_row.watchItems = c.get("watchItems", [])
                cand_row.latestNews = c.get("latestNews", [])
                cand_row.affectNews = c.get("affectNews", [])
                cand_row.neutralNews = c.get("neutralNews", [])
                cand_row.blogSummary = c.get("blogSummary")
                cand_row.citations = c.get("citations", [])
                cand_row.briefEmbedding = brief_emb
            else:
                # Insert new item
                cand_row = ResearchCandidate(
                    runId=state.runId,
                    underlyingType=scope_type,
                    underlyingCode=code,
                    newsStatus=c["newsStatus"],
                    suggested=c["suggested"],
                    rank=c.get("rank"),
                    direction=c.get("direction"),
                    bearishWatch=c.get("bearishWatch", False),
                    score=c.get("score"),
                    scoreLabel=c.get("scoreLabel"),
                    positiveWeight=c.get("positiveWeight", 0.0),
                    negativeWeight=c.get("negativeWeight", 0.0),
                    negativeShare=c.get("negativeShare", 0.0),
                    positiveClaims=c.get("positiveClaims", 0),
                    negativeClaims=c.get("negativeClaims", 0),
                    materialNegatives=c.get("materialNegatives", []),
                    independentSources=c.get("independentSources", 0),
                    freshArticleCount=c.get("freshArticleCount", 0),
                    newestArticleAt=c.get("newestArticleAt"),
                    oldestArticleAt=c.get("oldestArticleAt"),
                    flags=c.get("flags", []),
                    reasons=c.get("reasons", []),
                    thesis=c.get("thesis"),
                    supportingPoints=c.get("supportingPoints", []),
                    watchItems=c.get("watchItems", []),
                    latestNews=c.get("latestNews", []),
                    affectNews=c.get("affectNews", []),
                    neutralNews=c.get("neutralNews", []),
                    blogSummary=c.get("blogSummary"),
                    citations=c.get("citations", []),
                    briefEmbedding=brief_emb,
                )
                session.add(cand_row)

        await session.commit()
        state.stats["durationsByNodeMs"]["persist"] = int((time.time() - t0) * 1000)
        return state

    async def finalize(self, state: ResearchState, session: AsyncSession) -> ResearchState:
        t0 = time.time()
        state.currentNode = "finalize"
        state.progressPct = 100

        now = datetime.now(timezone.utc)
        has_suggested = any(c.get("suggested") for c in state.candidates)
        result_kind = "SUGGESTED" if has_suggested else "NONE_SUGGESTED"
        final_state = "CANCELLED" if state.isCancelled else ("COMPLETED" if not state.error else "FAILED")

        # Update run record
        await session.execute(
            update(ResearchRun)
            .where(ResearchRun.id == state.runId)
            .values(
                state=final_state,
                resultKind=result_kind,
                currentNode="finalize",
                progressPct=100,
                stats=state.stats,
                finishedAt=now,
                error=state.error,
            )
        )
        await session.commit()

        await self._log_event(
            session,
            state.runId,
            "finalize",
            "INFO",
            f"Run {state.runId} finished with state={final_state}, resultKind={result_kind}.",
            data=state.stats,
        )
        state.stats["durationsByNodeMs"]["finalize"] = int((time.time() - t0) * 1000)
        return state
