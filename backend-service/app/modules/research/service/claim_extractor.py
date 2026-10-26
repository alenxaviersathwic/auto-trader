import json
import re
from typing import Any, Dict, List
import httpx
from pydantic import BaseModel, Field
from app.core.config.settings import settings
from app.core.logging.logger import logger


class ExtractedClaimItem(BaseModel):
    underlyingCode: str
    channel: str = Field(default="DIRECT", description="DIRECT, CONSTITUENT, SECTOR, MACRO")
    stance: str = Field(description="BULLISH, BEARISH, NEUTRAL")
    magnitude: int = Field(default=3, ge=1, le=5)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    horizon: str = Field(default="DAYS", description="INTRADAY, DAYS, WEEKS, MONTHS")
    catalyst: str = Field(default="OTHER")
    isRiskEvent: bool = False
    eventDate: str = None
    statement: str = Field(description="One sentence summary of the assertion")
    quote: str = Field(description="Exact verbatim excerpt from the document")


class ClaimExtractionOutput(BaseModel):
    claims: List[ExtractedClaimItem] = []


class ClaimExtractor:
    """
    Extracts structured, cited claims from text chunks using LLM with heuristic fallback.
    """

    def __init__(self, base_url: str = "", model: str = ""):
        self.base_url = (base_url or getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or getattr(settings, "OLLAMA_MODEL", "qwen3:8b")

    async def extract_claims(
        self,
        chunk_text: str,
        underlyings_in_scope: List[str],
        max_claims: int = 6,
    ) -> List[Dict[str, Any]]:
        """
        Extracts up to max_claims claims from chunk_text.
        """
        if not chunk_text.strip():
            return []

        # System prompt enforcing exact quote extraction
        sys_prompt = (
            "You are a rigorous quantitative financial news analyst. Extract market claims from the text "
            f"concerning these specific underlyings: {', '.join(underlyings_in_scope)}.\n"
            "Requirements:\n"
            "1. Extract both BULLISH (supportive) and BEARISH (negative/risk) claims.\n"
            "2. Note scheduled risk events (isRiskEvent=True) such as policy meetings or data releases.\n"
            "3. The 'quote' field MUST BE AN EXACT, VERBATIM substring directly from the text. Do not paraphrase.\n"
            f"4. Return at most {max_claims} high-confidence claims.\n"
            "Output strictly valid JSON matching ClaimExtractionOutput."
        )

        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": f"Document chunk:\n{chunk_text[:3000]}"},
                ],
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.0},
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                if resp.status_code == 200:
                    raw_content = resp.json().get("message", {}).get("content", "{}")
                    parsed = json.loads(raw_content)
                    raw_claims = parsed.get("claims", [])
                    validated_claims: List[Dict[str, Any]] = []
                    for rc in raw_claims[:max_claims]:
                        u_code = rc.get("underlyingCode", "").upper()
                        if any(u_code == u.upper() for u in underlyings_in_scope):
                            validated_claims.append(rc)
                    if validated_claims:
                        return validated_claims
        except Exception as e:
            logger.debug(f"LLM claim extraction call failed: {e}; applying rule-based claim extractor")

        # Heuristic extraction fallback when LLM is unavailable
        return self._heuristic_claim_extraction(chunk_text, underlyings_in_scope, max_claims)

    @staticmethod
    def _heuristic_claim_extraction(
        chunk_text: str, underlyings_in_scope: List[str], max_claims: int
    ) -> List[Dict[str, Any]]:
        """Extracts claims using keyword heuristic matching sentences."""
        claims: List[Dict[str, Any]] = []
        sentences = [s.strip() for s in re.split(r"(?<=[.!?]) +", chunk_text) if len(s.strip()) > 30]

        bullish_cues = ["rally", "surge", "gain", "inflow", "boost", "higher", "record high", "outperform", "bullish", "jumped", "growth"]
        bearish_cues = ["fall", "drop", "plunge", "decline", "sell-off", "probe", "loss", "lower", "slump", "bearish", "crash", "weakness"]

        UNDERLYING_ALIASES: Dict[str, List[str]] = {
            "NIFTY": ["nifty", "nifty 50", "nifty50", "nse nifty", "benchmark nifty", "dalal street"],
            "BANKNIFTY": ["bank nifty", "banknifty", "nifty bank", "banking index", "hdfc bank", "icici bank", "sbi"],
            "FINNIFTY": ["fin nifty", "finnifty", "financial services"],
            "MIDCPNIFTY": ["midcap nifty", "midcap select", "midcap"],
            "SENSEX": ["sensex", "bse sensex", "sensex 30"],
            "BANKEX": ["bankex", "bse bankex"],
            "CRUDEOIL": ["crude oil", "crude", "brent", "wti", "oil prices", "petroleum", "opec"],
            "GOLD": ["gold", "yellow metal", "xauusd", "gold prices", "bullion", "mcx gold"],
            "SILVER": ["silver", "xagusd", "silver prices", "mcx silver"],
            "COPPER": ["copper", "lme copper", "doctor copper"],
            "NATURALGAS": ["natural gas", "natgas", "mcx natural gas"],
            "ZINC": ["zinc", "lme zinc"],
        }

        for s in sentences:
            if len(claims) >= max_claims:
                break
            s_lower = s.lower()
            matched_u = None
            for u in underlyings_in_scope:
                u_upper = u.upper()
                aliases = UNDERLYING_ALIASES.get(u_upper, [u.lower()])
                if any(alias in s_lower for alias in aliases):
                    matched_u = u_upper
                    break

            if not matched_u:
                continue

            has_bull = any(cue in s_lower for cue in bullish_cues)
            has_bear = any(cue in s_lower for cue in bearish_cues)

            if has_bear:
                claims.append({
                    "underlyingCode": matched_u,
                    "channel": "DIRECT",
                    "stance": "BEARISH",
                    "magnitude": 3,
                    "confidence": 0.85,
                    "horizon": "DAYS",
                    "catalyst": "MACRO_DATA",
                    "isRiskEvent": False,
                    "eventDate": None,
                    "statement": s[:200],
                    "quote": s[:300],
                })
            elif has_bull:
                claims.append({
                    "underlyingCode": matched_u,
                    "channel": "DIRECT",
                    "stance": "BULLISH",
                    "magnitude": 3,
                    "confidence": 0.85,
                    "horizon": "DAYS",
                    "catalyst": "FLOWS",
                    "isRiskEvent": False,
                    "eventDate": None,
                    "statement": s[:200],
                    "quote": s[:300],
                })

        return claims


claim_extractor = ClaimExtractor()
