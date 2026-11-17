"""Article text without page furniture, before any matching or claim extraction.

17 Nov 2026: every Economic Times page carries a market ticker ("Benchmarks Nifty 25,410.75 119.66 ... Sensex ...")
and fund adverts ("FEATURED FUNDS ... Invest Now"). Matched as text, they tied EVERY article (Nokia shares, Nvidia
earnings, Australian bonds) to NIFTY / SENSEX, and "Nokia shares falling" then made SENSEX "BEARISH" on the day it
hit an all-time high."""
import re
from typing import Iterable

_FURNITURE = [
    re.compile(r"Benchmarks?\s+(?:Nifty|Sensex)[\s\S]{0,600}?(?=(?:FEATURED FUNDS|Invest Now|$))", re.I),
    re.compile(r"FEATURED FUNDS[\s\S]{0,400}?Invest Now", re.I),
    re.compile(r"★+\s*★*", re.I),
    re.compile(r"\b5Y Return\s+[-\d.]+\s*%", re.I),
]


def strip_furniture(text: str | None) -> str:
    out = text or ""
    for rx in _FURNITURE:
        out = rx.sub(" ", out)
    return re.sub(r"\s{2,}", " ", out).strip()


def mentions(text: str | None, patterns: Iterable[str]) -> bool:
    """True when the cleaned text names the underlying (one of `patterns`, lower-case) as a word."""
    low = strip_furniture(text).lower()
    return any(re.search(rf"(?<![a-z]){re.escape(p)}(?![a-z])", low) for p in patterns)
