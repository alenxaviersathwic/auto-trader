from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def identify_material_negatives(
    bearish_claims: List[Dict[str, Any]],
    thresholds: Dict[str, Any],
    sources_by_domain: Dict[str, float],
) -> List[int]:
    """
    Returns list of claim IDs that count as material negatives under the clearance policy.
    Criteria:
      - magnitude >= negMagnitudeMin (default 3)
      - confidence >= negConfidenceMin (default 0.50)
      - source credibility >= negCredibilityMin (default 0.50)
    """
    neg_mag_min = int(thresholds.get("negMagnitudeMin", 3))
    neg_conf_min = float(thresholds.get("negConfidenceMin", 0.50))
    neg_cred_min = float(thresholds.get("negCredibilityMin", 0.50))

    material_ids: List[int] = []
    seen_statements = set()

    for c in bearish_claims:
        if c.get("stance", "").upper() != "BEARISH":
            continue
        mag = int(c.get("magnitude", 1))
        conf = float(c.get("confidence", 0.8))
        domain = c.get("domain", "")
        cred = sources_by_domain.get(domain, 0.60)

        stmt = c.get("statement", "").strip().lower()
        if stmt in seen_statements:
            continue
        seen_statements.add(stmt)

        if mag >= neg_mag_min and conf >= neg_conf_min and cred >= neg_cred_min:
            claim_id = c.get("id")
            if claim_id:
                material_ids.append(claim_id)

    return material_ids


def classify_underlying(
    claims: List[Dict[str, Any]],
    fresh_articles: List[Dict[str, Any]],
    independent_sources: int,
    positive_weight: float,
    negative_weight: float,
    negative_share: float,
    thresholds: Dict[str, Any],
    sources_by_domain: Dict[str, float],
    has_unreviewed_signals: bool = False,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Pure decision rule implementing the news clearance flow.
    First matching status wins:
      1. NO_COVERAGE
      2. HAS_NEGATIVE
      3. MIXED
      4. CLEAR_POSITIVE (Suggested)
      5. CLEAR_NEUTRAL
    """
    if now is None:
        now = datetime.now(timezone.utc)

    min_sources = max(1, int(thresholds.get("minSources", 1)))
    max_stale_hours = float(thresholds.get("maxStaleHours", 24))
    neg_share_limit = float(thresholds.get("negShareLimit", 0.25))
    min_pos_claims = int(thresholds.get("minPositiveClaims", 1))
    min_pos_weight = float(thresholds.get("minPositiveWeight", 0.5))
    bearish_share_min = float(thresholds.get("bearishShareMin", 0.60))
    event_lookahead = float(thresholds.get("eventLookaheadHours", 36))
    veto_event_risk = bool(thresholds.get("vetoOnEventRisk", False))

    flags: List[str] = []
    reasons: List[str] = []

    # Check newest article staleness
    article_dates = [
        a.get("publishedAt") for a in fresh_articles if a.get("publishedAt") is not None
    ]
    newest_article_at = max(article_dates) if article_dates else None
    oldest_article_at = min(article_dates) if article_dates else None

    is_stale = False
    if newest_article_at:
        if isinstance(newest_article_at, str):
            newest_article_at = datetime.fromisoformat(newest_article_at.replace("Z", "+00:00"))
        age_hours = (now - newest_article_at).total_seconds() / 3600.0
        if age_hours > max_stale_hours:
            is_stale = True
            flags.append("STALE_COVERAGE")
            reasons.append(f"Coverage is stale: newest article is {age_hours:.1f}h old (max allowed {max_stale_hours}h)")

    # Identify claims breakdown
    pos_claims = [c for c in claims if c.get("stance", "").upper() == "BULLISH"]
    neg_claims = [c for c in claims if c.get("stance", "").upper() == "BEARISH"]

    # Check event risks
    for c in claims:
        if c.get("isRiskEvent"):
            flags.append("EVENT_RISK")
            reasons.append(f"Upcoming risk event scheduled: {c.get('statement', '')[:80]}")
            break

    # Material negatives
    material_negatives = identify_material_negatives(neg_claims, thresholds, sources_by_domain)
    if veto_event_risk and "EVENT_RISK" in flags and not material_negatives:
        material_negatives.append(-1)  # sentinel for veto

    if has_unreviewed_signals:
        flags.append("UNREVIEWED_NEGATIVE_SIGNALS")

    # 1. NO_COVERAGE
    if independent_sources < min_sources or is_stale or len(fresh_articles) == 0:
        news_status = "NO_COVERAGE"
        if independent_sources < min_sources:
            flags.append("LOW_COVERAGE")
            reasons.append(f"Insufficient coverage: {independent_sources} independent source(s) (minimum {min_sources} required)")
        suggested = False
        direction = None
        bearish_watch = False

    # 2. HAS_NEGATIVE
    elif len(material_negatives) > 0 or (negative_share >= neg_share_limit and positive_weight <= negative_weight):
        news_status = "HAS_NEGATIVE"
        suggested = False
        if len(material_negatives) > 0:
            reasons.append(f"Material negative news detected ({len(material_negatives)} high-severity claim(s))")
        if negative_share >= neg_share_limit:
            reasons.append(f"Negative news share ({negative_share:.1%}) exceeds threshold ({neg_share_limit:.1%})")

        # Bearish watch evaluation
        if negative_share >= bearish_share_min and independent_sources >= min_sources and len(neg_claims) >= 2:
            bearish_watch = True
            direction = "BEARISH"
            reasons.append("Strong negative consensus qualifying for Bearish Watch")
        else:
            bearish_watch = False
            direction = None

    # 3. CLEAR_POSITIVE (Suggested)
    elif (len(pos_claims) >= 1 and positive_weight >= 0.35 and len(material_negatives) == 0 and negative_share < 0.25) or \
         (positive_weight >= 0.8 and positive_weight > 1.3 * negative_weight and len(material_negatives) == 0):
        news_status = "CLEAR_POSITIVE"
        suggested = True
        direction = "BULLISH"
        bearish_watch = False
        reasons.append(f"Cleared across {len(fresh_articles)} fresh article(s) and {independent_sources} independent sources")
        reasons.append(f"Supported by {len(pos_claims)} verified bullish claim(s) (weight: {positive_weight:.2f})")

    # 4. MIXED (Unreviewed risk words found near underlying)
    elif has_unreviewed_signals or negative_share >= neg_share_limit:
        news_status = "MIXED"
        suggested = False
        direction = None
        bearish_watch = False
        reasons.append("Risk terms matched near underlying or mixed sentiment; conservative hold")

    # 5. CLEAR_NEUTRAL
    else:
        news_status = "CLEAR_NEUTRAL"
        suggested = False
        direction = None
        bearish_watch = False
        reasons.append("Clean of negative news, but catalyst or positive weight is currently insufficient")

    return {
        "newsStatus": news_status,
        "suggested": suggested,
        "direction": direction,
        "bearishWatch": bearish_watch,
        "positiveWeight": positive_weight,
        "negativeWeight": negative_weight,
        "negativeShare": negative_share,
        "positiveClaims": len(pos_claims),
        "negativeClaims": len(neg_claims),
        "materialNegatives": material_negatives,
        "independentSources": independent_sources,
        "freshArticleCount": len(fresh_articles),
        "newestArticleAt": newest_article_at,
        "oldestArticleAt": oldest_article_at,
        "flags": list(set(flags)),
        "reasons": reasons,
    }
