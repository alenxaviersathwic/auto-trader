# Intraday Trading Flow

How a trading day should run through this platform, end to end. This is
the operational checklist the Research Engine / Suggestion Engine /
Strategy scheduling should collectively implement.

## 1. Pre-market (08:30-09:15 NSE; 08:30-09:00 MCX)

- Refresh the instrument master: lot sizes, expiry dates (`G-LOT-MASTER`).
- Resolve today's holiday/expiry flags per underlying (`isExpiryDay`,
  `dayOverrides`).
- Pull the event calendar for the day/week: RBI MPC dates, Union Budget,
  US CPI/NFP/FOMC, EIA crude (Wed) / nat-gas (Thu) reports.
- Snapshot prior-day OHLC / CPR (central pivot range), India VIX close,
  GIFT Nifty indication, overnight news/sentiment summary (this is what
  the Research Engine's news pipeline feeds).
- Set the day's risk budget (max daily loss, max trades) before the first
  signal is evaluated.
- Verify broker (Upstox) connectivity and margin availability.

## 2. Opening (09:15-09:45 NSE; 09:00-09:30 MCX)

- Observe only. No entries (`G-TIME-OPEN`) -- the opening print carries the
  pre-open auction and is noisy.
- Record the first 30-minute bar's high/low, the day's gap vs prior close,
  and the VIX change from yesterday's close.

## 3. Signal phase (09:45-14:45 NSE; through the session on MCX)

- Strategies evaluate on each 30-minute candle close.
- Every candidate must clear the guardrail stack before an order is even
  considered: time window, market regime (VIX/chop), liquidity (spread/OI/
  depth), cost ratio (target >= 3x round-trip cost), capital/margin.
- Log the accept/reject reason for every candidate -- this is what lets
  the post-market review (step 7) tell a real negative-expectancy
  strategy from one that just never got a clean signal.

## 4. Execution

- Limit orders at mid +/- 1 tick with a timeout, not market orders, on
  anything except a forced time-exit.
- Place the stop-loss order immediately after the entry fills -- never
  leave a filled position unprotected between signal and stop placement.
- Record slippage (signal price vs actual fill) per trade for the cost
  model in `docs/04-risk-and-profit-management.md`.

## 5. Management

- Trail stops per the strategy's own rule; never widen a stop once set.
- No averaging into a losing position (`G-NO-AVERAGING`).
- After +1R, move the stop to breakeven plus costs; after +1.5R, trail by
  0.5x ATR(30m) on the underlying (not the premium -- premium ATR is noisy).

## 6. Wind-down

- No new NSE entries after 14:45 (whitelist only `IDX_LAST_HALF_HOUR_MOMENTUM`);
  force-flat 15:20 NSE, 15:15 BSE, 23:00 MCX (`G-TIME-LATE-NSE`,
  `G-TIME-LATE-BSE`, `G-TIME-MCX`).
- On the underlying's own expiry day, long options in that series stop
  being entered after 13:30 and are flat by 15:00 (`G-EXP-GAMMA`).

## 7. Post-market review

- Reconcile fills and actual charges against the signal log.
- Compute, per strategy: win rate, average win, average loss, expectancy
  after costs, max adverse excursion, average slippage.
- Update each strategy's/rule's evidence count and success rate.
- **Flag any strategy whose rolling 30-trade expectancy turns negative for
  automatic demotion back to PAPER mode** -- this is the platform's own
  version of `G-PAPER-FIRST`: a strategy that stops working stops being
  trusted automatically, not just on promotion.
- Make rule changes (disabling a strategy, tightening a guardrail) only in
  this post-market step -- never intraday, and never as a reaction to a
  single bad trade (see `docs/05-trading-psychology.md`, "discipline system").
