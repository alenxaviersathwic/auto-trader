from typing import Any, Dict, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging.logger import logger
from app.modules.research.entity.research_config_entity import ResearchConfig
from app.modules.research.entity.research_risk_term_entity import ResearchRiskTerm
from app.modules.research.entity.research_source_entity import ResearchSource
from app.modules.research.entity.research_underlying_entity import ResearchUnderlying


SEED_UNDERLYINGS: List[Dict[str, Any]] = [
    # Indices
    {
        "code": "NIFTY",
        "name": "Nifty 50 Index",
        "underlyingType": "INDEX",
        "groupName": "Indices",
        "exchange": "NSE",
        "aliases": ["Nifty 50", "NSE Nifty", "NIFTY50", "Nifty Index", "Indian benchmark Nifty"],
        "keywords": ["RBI policy", "FII flows", "DII buying", "India VIX", "headline inflation", "GDP growth"],
        "heavyweights": [
            {"name": "HDFC Bank", "aliases": ["HDFCBANK", "HDFC Bank Ltd"], "weightPct": 13.5},
            {"name": "Reliance Industries", "aliases": ["RELIANCE", "RIL"], "weightPct": 10.2},
            {"name": "ICICI Bank", "aliases": ["ICICIBANK", "ICICI Bank Ltd"], "weightPct": 7.8},
            {"name": "Infosys", "aliases": ["INFY", "Infosys Ltd"], "weightPct": 5.9},
        ],
        "enabled": True,
        "sortOrder": 1,
    },
    {
        "code": "BANKNIFTY",
        "name": "Nifty Bank Index",
        "underlyingType": "INDEX",
        "groupName": "Indices",
        "exchange": "NSE",
        "aliases": ["Bank Nifty", "NSE Bank Nifty", "Nifty Bank", "Banking Index"],
        "keywords": ["repo rate", "credit growth", "NPA", "net interest margin", "RBI liquidity", "banking regulatory norms"],
        "heavyweights": [
            {"name": "HDFC Bank", "aliases": ["HDFCBANK"], "weightPct": 29.0},
            {"name": "ICICI Bank", "aliases": ["ICICIBANK"], "weightPct": 23.0},
            {"name": "State Bank of India", "aliases": ["SBIN", "SBI"], "weightPct": 11.0},
            {"name": "Axis Bank", "aliases": ["AXISBANK"], "weightPct": 9.5},
        ],
        "enabled": True,
        "sortOrder": 2,
    },
    {
        "code": "FINNIFTY",
        "name": "Nifty Financial Services Index",
        "underlyingType": "INDEX",
        "groupName": "Indices",
        "exchange": "NSE",
        "aliases": ["Fin Nifty", "Nifty Financial Services", "Finnifty"],
        "keywords": ["NBFC borrowing", "insurance premium growth", "housing finance", "interest rate cycle"],
        "heavyweights": [],
        "enabled": True,
        "sortOrder": 3,
    },
    {
        "code": "MIDCPNIFTY",
        "name": "Nifty Midcap Select Index",
        "underlyingType": "INDEX",
        "groupName": "Indices",
        "exchange": "NSE",
        "aliases": ["Midcap Nifty", "Nifty Midcap Select", "Midcap Select"],
        "keywords": ["midcap rally", "retail flows", "market breadth", "valuation multiples"],
        "heavyweights": [],
        "enabled": True,
        "sortOrder": 4,
    },
    {
        "code": "SENSEX",
        "name": "BSE Sensex Index",
        "underlyingType": "INDEX",
        "groupName": "Indices",
        "exchange": "BSE",
        "aliases": ["BSE Sensex", "Sensex 30", "S&P BSE Sensex"],
        "keywords": ["BSE market cap", "FII investment", "global cues", "corporate earnings"],
        "heavyweights": [],
        "enabled": True,
        "sortOrder": 5,
    },
    {
        "code": "BANKEX",
        "name": "BSE Bankex Index",
        "underlyingType": "INDEX",
        "groupName": "Indices",
        "exchange": "BSE",
        "aliases": ["BSE Bankex", "Bankex Index"],
        "keywords": ["private banks", "PSU banks", "RBI circular", "deposit rates"],
        "heavyweights": [],
        "enabled": True,
        "sortOrder": 6,
    },
    # Commodities
    {
        "code": "CRUDEOIL",
        "name": "Crude Oil",
        "underlyingType": "COMMODITY",
        "groupName": "Energy",
        "exchange": "MCX",
        "aliases": ["Brent Crude", "WTI Crude", "MCX Crude Oil", "Petroleum crude", "Crude oil futures"],
        "keywords": ["OPEC+ production", "EIA inventory", "Middle East geopolitical tension", "Strait of Hormuz", "US shale production"],
        "heavyweights": [],
        "enabled": True,
        "sortOrder": 10,
    },
    {
        "code": "NATURALGAS",
        "name": "Natural Gas",
        "underlyingType": "COMMODITY",
        "groupName": "Energy",
        "exchange": "MCX",
        "aliases": ["Natural Gas", "MCX Natural Gas", "Henry Hub Natural Gas", "NatGas"],
        "keywords": ["EIA storage report", "LNG exports", "winter heating demand", "summer cooling demand", "pipeline maintenance"],
        "heavyweights": [],
        "enabled": True,
        "sortOrder": 11,
    },
    {
        "code": "GOLD",
        "name": "Gold",
        "underlyingType": "COMMODITY",
        "groupName": "Metals",
        "exchange": "MCX",
        "aliases": ["Spot Gold", "MCX Gold", "Gold futures", "Yellow metal", "XAUUSD"],
        "keywords": ["US Federal Reserve interest rates", "US dollar index DXY", "central bank gold buying", "safe haven demand", "Treasury yields"],
        "heavyweights": [],
        "enabled": True,
        "sortOrder": 12,
    },
    {
        "code": "SILVER",
        "name": "Silver",
        "underlyingType": "COMMODITY",
        "groupName": "Metals",
        "exchange": "MCX",
        "aliases": ["Spot Silver", "MCX Silver", "Silver futures", "XAGUSD"],
        "keywords": ["industrial demand", "solar photovoltaic demand", "gold silver ratio", "COMEX inventory"],
        "heavyweights": [],
        "enabled": True,
        "sortOrder": 13,
    },
    {
        "code": "COPPER",
        "name": "Copper",
        "underlyingType": "COMMODITY",
        "groupName": "Metals",
        "exchange": "MCX",
        "aliases": ["MCX Copper", "LME Copper", "Doctor Copper", "Copper cathode"],
        "keywords": ["China manufacturing PMI", "smelter production cuts", "LME warehouse stocks", "green energy transition"],
        "heavyweights": [],
        "enabled": True,
        "sortOrder": 14,
    },
    {
        "code": "ZINC",
        "name": "Zinc",
        "underlyingType": "COMMODITY",
        "groupName": "Metals",
        "exchange": "MCX",
        "aliases": ["MCX Zinc", "LME Zinc", "Zinc ingots"],
        "keywords": ["smelter treatment charges", "galvanizing demand", "mining production halts", "European energy costs"],
        "heavyweights": [],
        "enabled": True,
        "sortOrder": 15,
    },
]

SEED_SOURCES: List[Dict[str, Any]] = [
    {
        "name": "Economic Times Markets",
        "sourceType": "RSS",
        "baseUrl": "https://economictimes.indiatimes.com",
        "feedUrl": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "credibilityWeight": 0.85,
        "appliesToTypes": ["INDEX", "STOCK", "COMMODITY"],
        "enabled": True,
    },
    {
        "name": "Economic Times Commodities",
        "sourceType": "RSS",
        "baseUrl": "https://economictimes.indiatimes.com",
        "feedUrl": "https://economictimes.indiatimes.com/markets/commodities/rssfeeds/1808152.cms",
        "credibilityWeight": 0.85,
        "appliesToTypes": ["COMMODITY"],
        "enabled": True,
    },
    {
        "name": "Moneycontrol Markets",
        "sourceType": "RSS",
        "baseUrl": "https://www.moneycontrol.com",
        "feedUrl": "https://www.moneycontrol.com/rss/MCtopnews.xml",
        "credibilityWeight": 0.80,
        "appliesToTypes": ["INDEX", "STOCK", "COMMODITY"],
        "enabled": True,
    },
    {
        "name": "Moneycontrol Market Reports",
        "sourceType": "RSS",
        "baseUrl": "https://www.moneycontrol.com",
        "feedUrl": "https://www.moneycontrol.com/rss/marketreports.xml",
        "credibilityWeight": 0.80,
        "appliesToTypes": ["INDEX", "STOCK", "COMMODITY"],
        "enabled": True,
    },
    {
        "name": "Mint Markets",
        "sourceType": "RSS",
        "baseUrl": "https://www.livemint.com",
        "feedUrl": "https://www.livemint.com/rss/markets",
        "credibilityWeight": 0.85,
        "appliesToTypes": ["INDEX", "STOCK"],
        "enabled": True,
    },
    {
        "name": "Business Standard Markets",
        "sourceType": "RSS",
        "baseUrl": "https://www.business-standard.com",
        "feedUrl": "https://www.business-standard.com/rss/markets-106.rss",
        "credibilityWeight": 0.85,
        "appliesToTypes": ["INDEX", "STOCK", "COMMODITY"],
        "enabled": True,
    },
    {
        "name": "Reuters Business & Commodities",
        "sourceType": "AGENCY",
        "baseUrl": "https://www.reuters.com",
        "feedUrl": "https://feeds.reuters.com/reuters/businessNews",
        "credibilityWeight": 0.95,
        "appliesToTypes": ["INDEX", "COMMODITY", "STOCK"],
        "enabled": True,
    },
    {
        "name": "EIA Petroleum & Energy Reports",
        "sourceType": "AGENCY",
        "baseUrl": "https://www.eia.gov",
        "feedUrl": None,
        "credibilityWeight": 0.95,
        "appliesToTypes": ["COMMODITY"],
        "enabled": True,
    },
    {
        "name": "OPEC Press Releases",
        "sourceType": "AGENCY",
        "baseUrl": "https://www.opec.org",
        "feedUrl": None,
        "credibilityWeight": 0.95,
        "appliesToTypes": ["COMMODITY"],
        "enabled": True,
    },
    {
        "name": "IEA International Energy Agency",
        "sourceType": "AGENCY",
        "baseUrl": "https://www.iea.org",
        "feedUrl": None,
        "credibilityWeight": 0.90,
        "appliesToTypes": ["COMMODITY"],
        "enabled": True,
    },
    {
        "name": "World Gold Council",
        "sourceType": "AGENCY",
        "baseUrl": "https://www.gold.org",
        "feedUrl": None,
        "credibilityWeight": 0.90,
        "appliesToTypes": ["COMMODITY"],
        "enabled": True,
    },
    {
        "name": "Reserve Bank of India (RBI)",
        "sourceType": "AGENCY",
        "baseUrl": "https://www.rbi.org.in",
        "feedUrl": None,
        "credibilityWeight": 0.98,
        "appliesToTypes": ["INDEX", "STOCK"],
        "enabled": True,
    },
    {
        "name": "US Federal Reserve",
        "sourceType": "AGENCY",
        "baseUrl": "https://www.federalreserve.gov",
        "feedUrl": None,
        "credibilityWeight": 0.98,
        "appliesToTypes": ["INDEX", "COMMODITY"],
        "enabled": True,
    },
    {
        "name": "Web Intelligence Search",
        "sourceType": "SEARCH",
        "baseUrl": "https://searx.be",
        "feedUrl": None,
        "credibilityWeight": 0.70,
        "appliesToTypes": ["INDEX", "COMMODITY", "STOCK"],
        "enabled": True,
    },
]

SEED_RISK_TERMS: List[Dict[str, Any]] = [
    {"term": "fraud", "category": "FRAUD", "defaultSeverity": 5, "appliesToTypes": ["INDEX", "STOCK"]},
    {"term": "probe", "category": "LEGAL_REGULATORY", "defaultSeverity": 4, "appliesToTypes": ["INDEX", "STOCK"]},
    {"term": "raid", "category": "LEGAL_REGULATORY", "defaultSeverity": 5, "appliesToTypes": ["INDEX", "STOCK"]},
    {"term": "ban", "category": "LEGAL_REGULATORY", "defaultSeverity": 4, "appliesToTypes": ["INDEX", "COMMODITY", "STOCK"]},
    {"term": "penalty", "category": "LEGAL_REGULATORY", "defaultSeverity": 3, "appliesToTypes": ["INDEX", "STOCK"]},
    {"term": "sebi order", "category": "LEGAL_REGULATORY", "defaultSeverity": 4, "appliesToTypes": ["INDEX", "STOCK"]},
    {"term": "default", "category": "DEFAULT", "defaultSeverity": 5, "appliesToTypes": ["INDEX", "STOCK"]},
    {"term": "downgrade", "category": "DOWNGRADE", "defaultSeverity": 3, "appliesToTypes": ["INDEX", "STOCK", "COMMODITY"]},
    {"term": "sell-off", "category": "SELL_OFF", "defaultSeverity": 3, "appliesToTypes": ["INDEX", "STOCK", "COMMODITY"]},
    {"term": "plunge", "category": "SELL_OFF", "defaultSeverity": 3, "appliesToTypes": ["INDEX", "STOCK", "COMMODITY"]},
    {"term": "crash", "category": "SELL_OFF", "defaultSeverity": 4, "appliesToTypes": ["INDEX", "STOCK", "COMMODITY"]},
    {"term": "lower circuit", "category": "HALT", "defaultSeverity": 4, "appliesToTypes": ["INDEX", "STOCK"]},
    {"term": "halt", "category": "HALT", "defaultSeverity": 4, "appliesToTypes": ["INDEX", "STOCK", "COMMODITY"]},
    {"term": "war", "category": "GEOPOLITICAL", "defaultSeverity": 4, "appliesToTypes": ["INDEX", "COMMODITY"]},
    {"term": "sanction", "category": "GEOPOLITICAL", "defaultSeverity": 4, "appliesToTypes": ["COMMODITY", "INDEX"]},
    {"term": "strike", "category": "SUPPLY_SHOCK", "defaultSeverity": 3, "appliesToTypes": ["COMMODITY", "STOCK"]},
    {"term": "shutdown", "category": "SUPPLY_SHOCK", "defaultSeverity": 3, "appliesToTypes": ["COMMODITY", "STOCK"]},
    {"term": "outage", "category": "SUPPLY_SHOCK", "defaultSeverity": 3, "appliesToTypes": ["COMMODITY"]},
    {"term": "oil spill", "category": "SUPPLY_SHOCK", "defaultSeverity": 3, "appliesToTypes": ["COMMODITY"]},
    {"term": "embargo", "category": "GEOPOLITICAL", "defaultSeverity": 4, "appliesToTypes": ["COMMODITY"]},
]

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": 1,
    "weights": {
        "halfLifeHours": 12.0,
        "channelDirect": 1.0,
        "channelConstituent": 0.8,
        "channelSector": 0.7,
        "channelMacro": 0.5,
        "domainCap": 0.30,
        "scale": 5.0,
    },
    "thresholds": {
        "windowHours": 24,
        "minSources": 2,
        "maxStaleHours": 24,
        "negMagnitudeMin": 3,
        "negConfidenceMin": 0.50,
        "negCredibilityMin": 0.50,
        "negShareLimit": 0.25,
        "minPositiveClaims": 2,
        "minPositiveWeight": 1.0,
        "bearishShareMin": 0.60,
        "eventLookaheadHours": 36,
        "vetoOnEventRisk": False,
        "suggestNeutralClear": False,
        "includeBearishWatch": True,
        "topN": 5,
    },
    "limits": {
        "concurrency": 2,
        "maxDocsPerUnderlying": 20,
        "fetchTimeoutSec": 15,
        "llmTimeoutSec": 90,
        "runTimeoutMinutes": 45,
        "retentionDays": 90,
    },
    "note": "Initial baseline research configuration v1.0",
}


class ResearchSeedService:
    """Populates default underlyings, sources, risk terms, and config."""

    @staticmethod
    async def seed_defaults(session: AsyncSession) -> None:
        # 1. Underlyings
        existing_u = await session.execute(select(ResearchUnderlying.code))
        existing_codes = set(existing_u.scalars().all())
        for u_data in SEED_UNDERLYINGS:
            if u_data["code"] not in existing_codes:
                u = ResearchUnderlying(**u_data)
                session.add(u)

        # 2. Sources
        existing_s = await session.execute(select(ResearchSource.name))
        existing_sources = set(existing_s.scalars().all())
        for s_data in SEED_SOURCES:
            if s_data["name"] not in existing_sources:
                s = ResearchSource(**s_data)
                session.add(s)

        # 3. Risk terms
        existing_r = await session.execute(select(ResearchRiskTerm.term))
        existing_terms = set(existing_r.scalars().all())
        for r_data in SEED_RISK_TERMS:
            if r_data["term"] not in existing_terms:
                r = ResearchRiskTerm(**r_data)
                session.add(r)

        # 4. Config v1
        existing_c = await session.execute(select(ResearchConfig).where(ResearchConfig.version == 1))
        if not existing_c.scalar_one_or_none():
            cfg = ResearchConfig(
                version=DEFAULT_CONFIG["version"],
                weights=DEFAULT_CONFIG["weights"],
                thresholds=DEFAULT_CONFIG["thresholds"],
                limits=DEFAULT_CONFIG["limits"],
                note=DEFAULT_CONFIG["note"],
            )
            session.add(cfg)

        # 5. Master Tool Server 'research'
        from app.modules.master.entity.master_tool_server_entity import MasterToolServer
        existing_ts = await session.execute(
            select(MasterToolServer).where(MasterToolServer.name == "research").where(MasterToolServer.status == 1)
        )
        if not existing_ts.scalar_one_or_none():
            ts = MasterToolServer(
                name="research",
                transport="HTTP",
                url="http://localhost:8000/mcp/research",
                authRef="MCP_RESEARCH_TOKEN",
                tierCap="OPERATE",
                enabled=True,
                toolCount=10,
            )
            session.add(ts)

        await session.commit()
        logger.info("Research module initial defaults verified & seeded successfully.")
