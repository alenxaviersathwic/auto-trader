import math
from typing import Any, Dict, List, Optional, Tuple


def compute_candidate_score(
    positive_weight: float,
    negative_share: float,
    independent_sources: int,
    min_sources: int = 3,
    scale: float = 5.0,
) -> Tuple[float, str]:
    """
    Computes saturating 0-100 score and score label (HIGH, MEDIUM, LOW) for suggested candidates.
    """
    if positive_weight <= 0:
        return 0.0, "LOW"

    positive_strength = 1.0 - math.exp(-positive_weight / max(0.1, scale))
    coverage_factor = min(1.0, independent_sources / max(1.0, 2.0 * min_sources))
    raw_score = 100.0 * positive_strength * coverage_factor * max(0.0, 1.0 - negative_share)
    score = round(max(0.0, min(100.0, raw_score)), 1)

    if score >= 70.0 and independent_sources >= 5:
        label = "HIGH"
    elif score >= 50.0:
        label = "MEDIUM"
    else:
        label = "LOW"

    return score, label


def compute_opportunity_score(
    positive_weight: float,
    negative_weight: float,
    independent_sources: int,
    min_sources: int = 3,
    scale: float = 5.0,
) -> Tuple[float, str, Optional[str]]:
    """
    Opportunity score 0-100 for ANY underlying, recomputed on every run.
    Bullish news is a call opportunity, bearish news is a put opportunity: strength comes from the
    dominant side, reduced when the other side is also loud, and scaled by source coverage.
    Returns (score, label, direction) where direction is BULLISH, BEARISH or None (no clear edge).
    """
    pos, neg = max(0.0, positive_weight), max(0.0, negative_weight)
    total = pos + neg
    if total <= 0:
        return 0.0, "LOW", None
    dominant = max(pos, neg)
    strength = 1.0 - math.exp(-dominant / max(0.1, scale))
    clarity = dominant / total  # 1.0 = one-sided, 0.5 = fully mixed
    coverage = min(1.0, independent_sources / max(1.0, 2.0 * min_sources))
    score = round(max(0.0, min(100.0, 100.0 * strength * (2.0 * clarity - 1.0) * coverage)), 1)
    if score >= 70.0 and independent_sources >= 5:
        label = "HIGH"
    elif score >= 50.0:
        label = "MEDIUM"
    else:
        label = "LOW"
    direction = None if score <= 0 else ("BULLISH" if pos >= neg else "BEARISH")
    return score, label, direction


def rank_candidates_by_type(
    candidates: List[Dict[str, Any]],
    top_n: int = 5,
    min_sources: int = 3,
    scale: float = 5.0,
) -> List[Dict[str, Any]]:
    """
    Computes opportunityScore for EVERY candidate on every run and ranks them 1..n within each
    underlying type by that score. `score` mirrors opportunityScore for older consumers.
    """
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for c in candidates:
        by_type.setdefault(c.get("underlyingType", "INDEX"), []).append(c)

    final_results: List[Dict[str, Any]] = []
    for _u_type, group in by_type.items():
        for c in group:
            score, label, direction = compute_opportunity_score(
                positive_weight=float(c.get("positiveWeight", 0.0)),
                negative_weight=float(c.get("negativeWeight", 0.0)),
                independent_sources=int(c.get("independentSources", 0)),
                min_sources=min_sources,
                scale=scale,
            )
            if c.get("newsStatus") == "NO_COVERAGE":
                score, label, direction = 0.0, "LOW", None
            c["opportunityScore"] = score
            c["score"] = score
            c["scoreLabel"] = label
            if direction:
                c["direction"] = direction

        group.sort(key=lambda x: x["opportunityScore"], reverse=True)
        for idx, c in enumerate(group, 1):
            c["rank"] = idx if c["opportunityScore"] > 0 else None
        final_results.extend(group)

    return final_results
