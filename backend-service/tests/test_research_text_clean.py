"""17 Nov 2026: SENSEX was marked BEARISH from a Nokia story because every Economic Times page carries a market
ticker ("Benchmarks Nifty ... Sensex ...") and a "falling" headline was read as SENSEX news."""
from app.modules.research.scoring.score_rank import MIN_DIRECTION_SCORE, compute_opportunity_score
from app.modules.research.service.text_clean import mentions, strip_furniture

ET = ("Why are Nokia shares falling? Nvidia stake sale sparks concerns - Nokia shares extend losing streak amid AI "
      "concerns | The Economic Times Benchmarks Nifty 25,410.75 119.66 Sensex 82,705.35 FEATURED FUNDS ★★★★ ★ UTI "
      "Aggressive Hybrid Fund Regular Plan-Growth 5Y Return 9.96 % Invest Now Nokia said on Monday it would cut costs.")


def test_page_ticker_is_not_index_news():
    clean = strip_furniture(ET)
    assert "25,410" not in clean and "FEATURED FUNDS" not in clean and "Nokia said on Monday" in clean
    assert not mentions(ET, ["sensex", "bse sensex"]) and not mentions(ET, ["nifty"])
    assert mentions("Sensex hits a record high as banks rally", ["sensex"])
    assert not mentions("Sensexx-like word", ["sensex"])  # a whole word only


def test_weak_news_has_no_direction():
    # one weak negative claim from 3 sources (the SENSEX run 52 shape): score 8.9, no direction any more
    score, label, direction = compute_opportunity_score(0.0, 0.464, 3)
    assert score < MIN_DIRECTION_SCORE and label == "LOW" and direction is None
    score, _, direction = compute_opportunity_score(0.0, 6.0, 8)
    assert score >= MIN_DIRECTION_SCORE and direction == "BEARISH"
