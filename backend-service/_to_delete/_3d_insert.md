## 3d. Day type, strike modes and premium exits (10 Nov 2026 redesign)

Why: a replay of 9 Nov under §3c still lost on the trend-following setups (VWAP pullback / EMA retest inside chop), and
the engine could only buy ATM / 1-ITM. Research summary: SEBI FY26 — ~88 % of individual F&O traders lost money, ~90 %
of option-only buyers; cheap far-OTM options are overpriced on average (Boyer & Vorkink 2014); intraday momentum is
real mainly outside a "noise area" around the open (Zarattini, Aziz & Barbon 2024) and on short-gamma days (Baltussen
et al. 2021); stops cluster just beyond round numbers (Osler 2005). So: fewer trades, gated by day type, and
out-of-the-money strikes only when the day is expanding.

**Day type (`service/day_type.py`, in `analysis["dayType"]`, `diag.dayType`)**

| Type | Rule | Allowed |
|---|---|---|
| PIN | ≤ 1 day to expiry, after 10:30, inside the noise area and inside an OI box ≤ 2 × the straddle-implied move, VIX not rising | REVERSAL + RANGE setups only |
| RANGE | inside the noise area (default) | REVERSAL + RANGE setups only |
| TREND | last 5-min close outside the noise area | TREND setups on that side, REVERSAL, RANGE (no VWAP fades) |
| EXPANSION | TREND + fuel: gap ≥ 0.5 daily ATR, VIX ≥ +3 %, day range ≥ 80 % of daily ATR, or price through the OI wall | same as TREND |

Noise area = `max(open, prevClose) × (1 + σ)` … `min(open, prevClose) × (1 − σ)`, σ = average |move from the open| at this
time of day over the last 14 sessions (the Time Machine's cached 5-min history); without history, a daily-ATR ×
√time proxy (`noise.source = "atr-proxy"`).

**New setups**: `NOISE_BREAKOUT` (first 5-min close outside the noise area), `LATE_DAY_MOMENTUM` (14:30-15:05, first
half hour and day return agree, outside the noise area), and round numbers (NIFTY 100s, BANKNIFTY/SENSEX 500s) added
to the levels `FAILED_BREAK_RECLAIM` watches.

**Strike mode (`menu_builder.strike_mode`, index options only)**

| Mode | When | Strikes | Exits |
|---|---|---|---|
| ATM | default; every reclaim / range setup | ATM or 1 ITM, \|delta\| ≥ 0.45 | chart points (§3c) |
| ITM | expiry day after 13:30 | \|delta\| ≥ 0.6 | chart points |
| OTM | TREND-family setup on a TREND/EXPANSION day, ≤ 1 day to expiry | \|delta\| 0.20-0.35 | premium −35 % (min −20 %) / +60 %, exit if no new high in 10 min |
| LOTTERY | as OTM, EXPANSION day, expiry day after 13:30 | \|delta\| 0.08-0.20 | premium −50 % / +100 %; risk per lot = whole premium |

Filters: premium ≥ ₹2; under ₹20 the spread must be ≤ 1 tick (₹0.05) instead of the % rule. `costPct` now includes
slippage (1 tick per side under ₹20, else 0.25 % per side) and STT 0.15 % on the sell side. Each saved pick carries a
sizing line: risk per lot and lots for `params.riskPerTradeRs` (default ₹2,000). Out-of-the-money picks skip the Time
Machine (a delta map cannot replay gamma). Guardrail daily cap is now 4 per underlying.

**Chain recorder (`service/chain_recorder.py`, table `option_chain_snapshots`, migration 0021)**: each iteration's
chain (24 strikes: LTP, OI, volume, bid, ask, delta, IV) is stored about once a minute. Upstox keeps no chain history,
so OI-wall / short-covering / premium-momentum rules can only be backtested from these rows — keep the cards running.

**Replay** `scripts/backtest_day.py` (9 Nov 2026, Black-Scholes premiums at a fixed IV, one position at a time):
11 opportunities (NIFTY 4, BANKNIFTY 4, SENSEX 3), about +₹8,400 for one lot of each; 303 of 393 fired setups were
blocked by the day type. One day is not evidence: shadow-trade 4-8 weeks and judge on 200+ trades.

Not built yet: premium-momentum breakout on the option's own chart, wall-break with short covering, gamma
concentration (all need the recorded chains), constituent-breadth program-flow proxy, 30-level depth.

---

