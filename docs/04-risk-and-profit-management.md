# Risk and Profit Management

## The arithmetic of a 5-10% premium target

Worked example (NIFTY ATM weekly CE at Rs100, lot 65 -> Rs6,500/lot):

- A 5% target = Rs5 premium = Rs325/lot gross. With delta ~0.5 that is
  only ~10 NIFTY points (~0.04% of the index) -- **inside normal one-minute
  noise.**
- Round-trip cost: ~Rs40 brokerage + ~Rs10 STT (0.15% on sell premium) +
  ~Rs10-15 other exchange/SEBI/GST/stamp charges = **Rs60-65, roughly 1%
  of premium**, before slippage.
- Break-even win rate for a straight 5% target / 5% stop bracket: **~60%**.
  For 8% target / 5% stop: **~46%**. For 10% target / 5% stop: **~40%**.
- One tick of slippage each way (Rs0.05 x 2) adds ~0.1% on a NIFTY ATM
  option -- small, but on MCX options with wider spreads the spread alone
  can consume an entire 5% target.

**Conclusion used throughout this platform's strategy registry:** a flat
5% premium stop on an ATM weekly option is simply inside the noise band
and will be hit by randomness most of the time. Every strategy should
instead:

1. **Define the stop on the underlying**, not the premium -- a structural
   level (range midpoint, VWAP, 0.5-1x ATR on 30-min bars) converted to a
   premium stop via delta (`premium stop ~= delta x underlying stop
   distance + spread buffer`).
2. **Size lots from the stop distance**, so Rs-risk per trade stays within
   the daily/trade risk budget below -- never size first and discover the
   stop afterward.
3. **Target >= 1.5R and >= 3x round-trip cost** (`G-COST-RATIO`). If the
   30-minute ATR implies the target can't be reached before the day's
   force-flat time, skip the trade rather than taking a worse-than-coinflip bet.
4. **Prefer ATM/slightly-ITM strikes (delta 0.45-0.6)** over cheap
   far-OTM options for directional buys -- cheap options have the worst
   cost-to-premium ratio of all.

## Position sizing and limits

- **Per trade:** max loss <= 0.5-1% of trading capital; size lots from the
  stop distance, never a fixed lot count.
- **Per day:** realised + unrealised loss >= 2% of capital -> flatten
  everything and halt for the session (`G-RISK-DAY`).
- **Per week:** ~5% drawdown triggers a mandatory strategy/process review
  before trading resumes.
- **Consecutive losses:** 3 in a row -> halt for the session
  (`G-RISK-CONSEC`) -- this is a behavioural circuit-breaker, not a
  statistical one; it exists to stop revenge-trading, not because 3 losses
  proves anything about the edge.
- **Trade count:** max ~6 trades/day across the platform, max 2 per
  strategy (`G-RISK-MAXTRADES`) -- costs alone moved SEBI's FY26 retail
  loss share from 82.1% (before costs) to 87.7% (after costs); a
  many-small-trades design is the most cost-sensitive design there is.
- **Correlated exposure:** NIFTY/BANKNIFTY/FINNIFTY/SENSEX move together
  intraday -- count concurrent positions across them as *one* exposure for
  risk-budget purposes, max 2 concurrent correlated positions.
- **Drawdown response:** halve size after a 10% drawdown from the equity
  peak; stop live trading and re-validate every strategy after 20%.

## Why high win-rate premium selling still blows up

Short-premium (straddle/strangle/iron-fly) strategies can show win rates
of 60-80% in backtests while the **average loss runs 2-3x the average
win** -- a handful of tail days erase many small wins. Always define risk
with wings (iron fly/condor), never run naked short options on this
platform, and never remove a hedge "just for one trade" to save margin.

## Expectancy, in one line

```
expectancy = win% x avg_win - loss% x avg_loss - costs
```

Compute this per strategy after every session (see
`docs/03-intraday-trading-flow.md`, step 7) and demote to PAPER
automatically once the rolling 30-trade expectancy goes negative.

## Profit handling

- Lock in gains with a breakeven-plus-costs stop once a trade reaches +1R.
- Do not raise position size until a strategy has 100+ live-paper trades
  confirming the edge survives real costs and real fills -- a backtest
  number is not a reason to size up.
