from datetime import datetime, timedelta, timezone
from app.modules.research.scoring.claim_weight import aggregate_weights, calculate_claim_weight
from app.modules.research.scoring.classify_status import classify_underlying, identify_material_negatives
from app.modules.research.scoring.score_rank import compute_candidate_score, rank_candidates_by_type


def test_claim_weight_recency_decay():
    now = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)
    config_weights = {"halfLifeHours": 12.0, "channelDirect": 1.0}

    # 0 hours old
    claim_fresh = {
        "publishedAt": now,
        "channel": "DIRECT",
        "confidence": 1.0,
        "magnitude": 5,
    }
    w0 = calculate_claim_weight(claim_fresh, now, config_weights, source_credibility=1.0)
    assert round(w0, 2) == 1.00

    # 12 hours old (half-life) -> weight should be 0.50
    claim_12h = {
        "publishedAt": now - timedelta(hours=12),
        "channel": "DIRECT",
        "confidence": 1.0,
        "magnitude": 5,
    }
    w12 = calculate_claim_weight(claim_12h, now, config_weights, source_credibility=1.0)
    assert round(w12, 2) == 0.50


def test_classify_status_no_coverage():
    thresholds = {"minSources": 3, "maxStaleHours": 12}
    sources = {"domain1.com": 0.8}

    # Zero articles -> NO_COVERAGE
    res = classify_underlying(
        claims=[],
        fresh_articles=[],
        independent_sources=0,
        positive_weight=0.0,
        negative_weight=0.0,
        negative_share=0.0,
        thresholds=thresholds,
        sources_by_domain=sources,
    )
    assert res["newsStatus"] == "NO_COVERAGE"
    assert res["suggested"] is False
    assert "LOW_COVERAGE" in res["flags"]


def test_classify_status_has_negative_and_bearish_watch():
    thresholds = {
        "minSources": 3,
        "maxStaleHours": 12,
        "negMagnitudeMin": 3,
        "negConfidenceMin": 0.5,
        "negCredibilityMin": 0.5,
        "negShareLimit": 0.25,
        "bearishShareMin": 0.60,
    }
    sources = {"domainA.com": 0.9, "domainB.com": 0.8, "domainC.com": 0.85}

    neg_claims = [
        {"id": 101, "stance": "BEARISH", "magnitude": 4, "confidence": 0.9, "domain": "domainA.com", "statement": "SEBI probes fraud"},
        {"id": 102, "stance": "BEARISH", "magnitude": 4, "confidence": 0.8, "domain": "domainB.com", "statement": "Large FII sell-off triggers drop"},
    ]
    fresh_articles = [
        {"publishedAt": datetime.now(timezone.utc)},
        {"publishedAt": datetime.now(timezone.utc)},
        {"publishedAt": datetime.now(timezone.utc)},
    ]

    res = classify_underlying(
        claims=neg_claims,
        fresh_articles=fresh_articles,
        independent_sources=3,
        positive_weight=0.5,
        negative_weight=2.5,
        negative_share=0.833,
        thresholds=thresholds,
        sources_by_domain=sources,
    )
    assert res["newsStatus"] == "HAS_NEGATIVE"
    assert res["suggested"] is False
    assert res["bearishWatch"] is True
    assert res["direction"] == "BEARISH"
    assert 101 in res["materialNegatives"]


def test_classify_status_clear_positive_suggested():
    thresholds = {
        "minSources": 3,
        "maxStaleHours": 12,
        "negMagnitudeMin": 3,
        "negConfidenceMin": 0.5,
        "negCredibilityMin": 0.5,
        "negShareLimit": 0.25,
        "minPositiveClaims": 2,
        "minPositiveWeight": 1.0,
    }
    sources = {"domainA.com": 0.9, "domainB.com": 0.8, "domainC.com": 0.85}

    pos_claims = [
        {"id": 201, "stance": "BULLISH", "magnitude": 4, "confidence": 0.9, "domain": "domainA.com", "statement": "Strong GDP beats estimates"},
        {"id": 202, "stance": "BULLISH", "magnitude": 3, "confidence": 0.85, "domain": "domainB.com", "statement": "FII inflows surge into index"},
    ]
    fresh_articles = [
        {"publishedAt": datetime.now(timezone.utc)},
        {"publishedAt": datetime.now(timezone.utc)},
        {"publishedAt": datetime.now(timezone.utc)},
    ]

    res = classify_underlying(
        claims=pos_claims,
        fresh_articles=fresh_articles,
        independent_sources=3,
        positive_weight=2.2,
        negative_weight=0.0,
        negative_share=0.0,
        thresholds=thresholds,
        sources_by_domain=sources,
    )
    assert res["newsStatus"] == "CLEAR_POSITIVE"
    assert res["suggested"] is True
    assert res["direction"] == "BULLISH"
    assert res["bearishWatch"] is False


def test_scoring_and_ranking():
    c1 = {
        "underlyingCode": "NIFTY",
        "underlyingType": "INDEX",
        "suggested": True,
        "positiveWeight": 4.5,
        "negativeShare": 0.05,
        "independentSources": 6,
    }
    c2 = {
        "underlyingCode": "BANKNIFTY",
        "underlyingType": "INDEX",
        "suggested": True,
        "positiveWeight": 1.5,
        "negativeShare": 0.10,
        "independentSources": 3,
    }
    c3 = {
        "underlyingCode": "FINNIFTY",
        "underlyingType": "INDEX",
        "suggested": False,
        "positiveWeight": 0.0,
        "negativeShare": 0.5,
        "independentSources": 1,
    }

    ranked = rank_candidates_by_type([c1, c2, c3], top_n=5, min_sources=3, scale=5.0)

    nifty = next(x for x in ranked if x["underlyingCode"] == "NIFTY")
    banknifty = next(x for x in ranked if x["underlyingCode"] == "BANKNIFTY")
    finnifty = next(x for x in ranked if x["underlyingCode"] == "FINNIFTY")

    assert nifty["rank"] == 1
    assert nifty["score"] > banknifty["score"]
    assert nifty["scoreLabel"] in ["HIGH", "MEDIUM"]
    assert banknifty["rank"] == 2
    assert finnifty["rank"] is None
    assert finnifty["score"] is None
