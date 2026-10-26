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


def rank_candidates_by_type(
    candidates: List[Dict[str, Any]],
    top_n: int = 5,
    min_sources: int = 3,
    scale: float = 5.0,
) -> List[Dict[str, Any]]:
    """
    Computes scores for suggested candidates and assigns 1-based ranks within each underlying type.
    Non-suggested candidates have score = None and rank = None.
    """
    # Group by underlyingType
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for c in candidates:
        u_type = c.get("underlyingType", "INDEX")
        by_type.setdefault(u_type, []).append(c)

    final_results: List[Dict[str, Any]] = []

    for u_type, group in by_type.items():
        suggested_group = [c for c in group if c.get("suggested")]
        non_suggested_group = [c for c in group if not c.get("suggested")]

        for c in suggested_group:
            score, label = compute_candidate_score(
                positive_weight=float(c.get("positiveWeight", 0.0)),
                negative_share=float(c.get("negativeShare", 0.0)),
                independent_sources=int(c.get("independentSources", 0)),
                min_sources=min_sources,
                scale=scale,
            )
            c["score"] = score
            c["scoreLabel"] = label

        # Sort suggested descending by score
        suggested_group.sort(key=lambda x: (x.get("score") or 0.0), reverse=True)

        for idx, c in enumerate(suggested_group):
            if idx < top_n:
                c["rank"] = idx + 1
            else:
                c["rank"] = None
                c["suggested"] = False  # exceeded top N cap

        for c in non_suggested_group:
            c["score"] = None
            c["scoreLabel"] = None
            c["rank"] = None

        final_results.extend(suggested_group)
        final_results.extend(non_suggested_group)

    return final_results
