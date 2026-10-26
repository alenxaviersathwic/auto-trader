import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Tuple


def calculate_claim_weight(
    claim: Dict[str, Any],
    now: datetime,
    config_weights: Dict[str, Any],
    source_credibility: float = 0.60,
    heavyweight_pct: float = 0.0,
) -> float:
    """
    Computes weighted contribution of a verified claim.
    Formula:
      ageHours = max(0, (now - publishedAt).total_seconds() / 3600)
      r = 0.5 ^ (ageHours / halfLifeHours)
      channelFactor = DIRECT (1.0), CONSTITUENT (0.8 * hw_factor), SECTOR (0.7), MACRO (0.5)
      weight = sourceCredibility * r * confidence * (magnitude / 5.0) * channelFactor
    """
    half_life = float(config_weights.get("halfLifeHours", 12.0))
    published_at = claim.get("publishedAt")
    if isinstance(published_at, str):
        try:
            published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except Exception:
            published_at = now
    elif not published_at:
        published_at = now

    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    age_hours = max(0.0, (now - published_at).total_seconds() / 3600.0)
    recency = 0.5 ** (age_hours / half_life) if half_life > 0 else 1.0

    channel = claim.get("channel", "DIRECT").upper()
    if channel == "DIRECT":
        channel_factor = float(config_weights.get("channelDirect", 1.0))
    elif channel == "CONSTITUENT":
        base_const = float(config_weights.get("channelConstituent", 0.8))
        hw_factor = min(1.5, max(0.5, heavyweight_pct / 10.0)) if heavyweight_pct > 0 else 1.0
        channel_factor = base_const * hw_factor
    elif channel == "SECTOR":
        channel_factor = float(config_weights.get("channelSector", 0.7))
    elif channel == "MACRO":
        channel_factor = float(config_weights.get("channelMacro", 0.5))
    else:
        channel_factor = 0.5

    confidence = float(claim.get("confidence", 0.8))
    magnitude = int(claim.get("magnitude", 1))
    magnitude_norm = min(5, max(1, magnitude)) / 5.0

    raw_weight = source_credibility * recency * confidence * magnitude_norm * channel_factor
    return round(raw_weight, 5)


def aggregate_weights(
    claims: List[Dict[str, Any]],
    now: datetime,
    config_weights: Dict[str, Any],
    sources_by_domain: Dict[str, float],
    heavyweights_by_alias: Dict[str, float],
) -> Tuple[float, float, float, List[str]]:
    """
    Aggregates positive & negative weights with domain capping (domainCap) and deduplication.
    Returns: (positiveWeight, negativeWeight, negativeShare, flags)
    """
    domain_cap = float(config_weights.get("domainCap", 0.30))
    flags: List[str] = []

    pos_weights_by_domain: Dict[str, float] = {}
    neg_weights_by_domain: Dict[str, float] = {}
    seen_dedupe_keys: Set[str] = set()

    for c in claims:
        # Near-duplicate document deduplication
        dedupe_key = f"{c.get('documentId')}_{c.get('statement', '')[:40]}"
        if dedupe_key in seen_dedupe_keys:
            continue
        seen_dedupe_keys.add(dedupe_key)

        domain = c.get("domain", "unknown")
        source_cred = sources_by_domain.get(domain, 0.60)
        hw_pct = heavyweights_by_alias.get(c.get("underlyingCode", ""), 0.0)

        w = calculate_claim_weight(c, now, config_weights, source_cred, hw_pct)
        stance = c.get("stance", "NEUTRAL").upper()

        if stance == "BULLISH":
            pos_weights_by_domain[domain] = pos_weights_by_domain.get(domain, 0.0) + w
        elif stance == "BEARISH":
            neg_weights_by_domain[domain] = neg_weights_by_domain.get(domain, 0.0) + w

    raw_pos = sum(pos_weights_by_domain.values())
    raw_neg = sum(neg_weights_by_domain.values())

    # Apply domain caps
    final_pos = 0.0
    for dom, w in pos_weights_by_domain.items():
        if raw_pos > 0 and (w / raw_pos) > domain_cap and len(pos_weights_by_domain) > 1:
            flags.append("SINGLE_SOURCE_DOMINANCE")
            final_pos += raw_pos * domain_cap
        else:
            final_pos += w

    final_neg = 0.0
    for dom, w in neg_weights_by_domain.items():
        if raw_neg > 0 and (w / raw_neg) > domain_cap and len(neg_weights_by_domain) > 1:
            if "SINGLE_SOURCE_DOMINANCE" not in flags:
                flags.append("SINGLE_SOURCE_DOMINANCE")
            final_neg += raw_neg * domain_cap
        else:
            final_neg += w

    total = final_pos + final_neg
    neg_share = (final_neg / total) if total > 0 else 0.0

    return round(final_pos, 3), round(final_neg, 3), round(neg_share, 3), list(set(flags))
