"""Round-trip charges for ONE lot of an option bought and sold the same day, as % of the premium paid.

Estimates (verify against your broker's contract note; rates change):
  brokerage   flat per executed order (default Rs 20) x 2
  STT / CTT   on the SELL premium: equity index options 0.1% (from Oct 2024), MCX options CTT 0.05%
  exchange    transaction charges on premium turnover: NSE ~0.03503%, BSE ~0.0325%, MCX ~0.0418%
  SEBI fee    Rs 10 per crore of turnover
  GST         18% on brokerage + exchange + SEBI fee
  stamp duty  0.003% on the BUY premium
A 5% target on a cheap option can be half eaten by these, so validation compares edge AFTER costs."""

STT_SELL = {"NSE": 0.001, "BSE": 0.001, "MCX": 0.0005}
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
