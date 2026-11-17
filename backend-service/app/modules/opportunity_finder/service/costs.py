"""Round-trip charges for ONE lot of an option bought and sold the same day, as % of the premium paid.

Estimates (verify against your broker's contract note; rates change):
  brokerage   flat per executed order (default Rs 20) x 2
  STT / CTT   on the SELL premium: equity index options 0.15% (0.1% until 31 Mar 2026; re-verify each Budget),
              MCX options CTT 0.05%
  exchange    transaction charges on premium turnover: NSE ~0.03503%, BSE ~0.0325%, MCX ~0.0418%
  SEBI fee    Rs 10 per crore of turnover
  GST         18% on brokerage + exchange + SEBI fee
  stamp duty  0.003% on the BUY premium
  slippage    slippage_pct(): one tick (Rs 0.05) per side under Rs 20 premium, else 0.25% per side. On a Rs 2
              option that is ~5% of premium round trip -- far more than every statutory charge together.
A 5% target on a cheap option can be half eaten by these, so validation compares edge AFTER costs."""

STT_SELL = {"NSE": 0.0015, "BSE": 0.0015, "MCX": 0.0005}
TICK = 0.05
CHEAP_PREMIUM = 20.0  # below this the tick, not a percentage, is the real cost
EXCHANGE_TXN = {"NSE": 0.0003503, "BSE": 0.000325, "MCX": 0.000418}


def round_trip_cost_pct(premium: float, lot_units: int, exchange: str, target_pct: float,
                        brokerage_per_order: float = 20.0) -> float:
    if premium <= 0 or lot_units <= 0:
        return 0.0
    buy = premium * lot_units
    sell = buy * (1 + target_pct / 100)
    turnover = buy + sell
    brokerage = 2 * brokerage_per_order
    exch = turnover * EXCHANGE_TXN.get(exchange, 0.00035)
    sebi = turnover * 1e-6
    gst = 0.18 * (brokerage + exch + sebi)
    stt = sell * STT_SELL.get(exchange, 0.001)
    stamp = buy * 0.00003
    return round((brokerage + exch + sebi + gst + stt + stamp) / buy * 100, 2)


def slippage_pct(premium: float) -> float:
    """Round-trip slippage as % of premium: 1 tick per side on cheap options, 0.25% per side otherwise."""
    if premium <= 0:
        return 0.0
    return round(2 * TICK / premium * 100, 2) if premium < CHEAP_PREMIUM else 0.5
