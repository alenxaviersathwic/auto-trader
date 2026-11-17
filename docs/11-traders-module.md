# 11. Active Traders & Live Execution Module (`trades`)

> **Document Type:** Module Specification
> **Status:** Authoritative
> **Module path:** `backend-service/app/modules/trade_history`, `frontend/src/modules/trade-history`

---

## 1. Overview (updated 16 Nov 2026: two traders)

The `trades` module has **two Traders**. A Trader is (1) the setups it may take and (2) how it manages the position.

| | `FIB_GOLDEN_TRADER` — Fib Golden-Pocket Trader | `FLOW_MOMENTUM_TRADER` — Flow & Momentum Trader |
|---|---|---|
| Takes | Only `FIB_GOLDEN_POCKET` (`opportunity_finder/service/fib_pocket.py`) | Every other setup the policy lets trade: `NOISE_BREAKOUT`, `INSIDE_BAR`, `FII_OPEN_DRIVE`, `LATE_DAY_MOMENTUM`, and `VWAP_PULLBACK` / `RANGE_BREAKOUT` / `GAP_GO` inside an active breakout |
| Checks | 1. Impulse swing >= 3 ATR5, pullback into the 0.50-0.618 pocket, 5-minute turn bar. 2. **OI**: no OI wall in the first 60% of the path to target, and the opposite wall behind the pocket or futures buildup agreeing. 3. **Volume**: pullback quieter than the impulse, turn bar >= average volume. All three are required. | Day type, dealer-gamma routing, institutional filters, 15-minute trend and the 1-minute timing gate (unchanged) |
| Plan | Entry = turn-bar close, stop just beyond 0.786, target = swing high (1.0) | From the setup (chart levels) |
| Manages | Waits for 80% of the move before locking half, then steps the target to 1.272 and 1.618 | Momentum setups: breakeven at +1.5R, trail 2R under the peak, no fixed target. Others: step guard (+30% at 50% progress, +50% at 80%) and step-wave target expansion on strong momentum |

- Ownership is by setup name (`trader_presets.assign_trader_for_opportunity`), never by confidence.
- The old codes `ORB_WAVE_TRADER` and `FLOW_VWAP_TRADER` map to `FLOW_MOMENTUM_TRADER` (`normalize_trader_code`); migration `0025` rewrites stored session lists.
- `trader_brain.evaluate_tick(..., trader_code=...)` now receives the trader. Before this change the stored `traderProfile` was always `HIGH_CONVICTION` / `STEP_GUARD`, so the trader-specific branches never ran.
- `FIB_GOLDEN_POCKET` has policy `CONFIRMED` in `setups.SETUP_POLICY`. A pocket found without both confirmations is reported in the funnel with the reason and does not trade.
- **Not backtested.** Upstox keeps no option-chain history, so the OI check cannot be replayed on past days. Judge the Fib trader from its saved-opportunity outcomes (forward test) before giving it size.

### Real swing carried to the trade (`setup_meta`, migration `0026`)

`fib_pocket.setup_meta()` stores the swing the Fib setup found (underlying swing low / high and the 0.5, 0.618, 0.786, 1.272, 1.618 levels) plus the same levels as option-premium prices (`premium = ltp + |delta| x move`). It travels `TradeOpportunity.setupMeta` -> `SessionPick.setupMeta` -> `marketTelemetry.fibLevels` with `source: "SETUP_SWING"`, shifted by the difference between the fill and the premium at signal time. The Fib trader's 1.272 / 1.618 targets (`trader_brain.evaluate_tick(fib_extensions=...)`) and the trade screen's level ladder use these. Every other trade gets `source: "PLAN"`: multiples of the planned move, with no swing low / high (none is made up any more).

### Option-chain (OI) view on a trade

`marketTelemetry.oaAnalysis` is built by `opportunity_finder/service/chain_view.py` from the newest `option_chain_snapshots` row (recorded about every 15 s while the scanner runs) and refreshed about once a minute. It carries `source: "CHAIN_SNAPSHOT"` and `asOf`. OI change is measured against the snapshot about 15 minutes earlier and is `null` when there is none. When no snapshot is newer than 5 minutes the value is `null` and the UI says so. Until 16 Nov 2026 this field held hard-coded numbers; trades entered before then still carry them and the UI ignores any ladder without `source`.

---

## 2. Backend Architecture

### 2.1 Data Model (`active_trades`)
- Table `active_trades` (Alembic `0023_active_trades`) stores each entered position:
  - `sessionId`, `pickId`, `opportunityId`, `userId`, `underlyingCode`, `optionType`, `strike`, `expiry`, `instrumentKey`, `strategy`, `confidence`, `winRatePct`, `traderProfile`, `sessionType`, `routeThroughUpstox`.
  - Price & sizing: `lots`, `lotUnits`, `quantity`, `plannedEntry`, `entryAt`, `capitalUsed`, `initialStop`, `initialTarget`, `currentStop`, `currentTarget`, `lastPrice`, `peakPrice`, `troughPrice`.
  - Broker & PnL: `entryOrderId`, `exitOrderId`, `brokerStatus`, `tradeState` (`RUNNING` | `EXITED`), `exitReason`, `exitPrice`, `grossPnl`, `charges`, `netPnl`, `pnlPct`.
  - Live telemetry (`marketTelemetry` JSONB): `traderCode`, `traderName`, `projectedTarget`, `fibLevels` (`swingLow`, `swingHigh`, `fib618`, `fib786`, `fib100`, `fib1272`, `fib1618`), `oaAnalysis` (PCR, Put OI Support Floor, Call OI Resistance Wall, Max Pain, 7-strike butterfly OI data), `exitSignal`, `exitRecommendation`, and `trailEvents` (chronological decision trail).

### 2.2 Dedicated 1-Second Trader Pilot (`engine/trade_pilot_runner.py` + `service/trader_brain.py`)
- Each `RUNNING` trade runs its own `asyncio` task (`trade-pilot-{tradeId}`) ticking every **1 second**.
- Fetches live option LTP + 1m candles from Upstox, runs `trader_brain.evaluate(...)`, persists SL/Target step-ups and telemetry, and publishes real-time snapshots via SSE (`GET /api/v1/trades/{id}/stream`).
- **`SEMI_AUTO` vs `FULL_AUTO`**:
  - In `SEMI_AUTO`: auto-locks and auto-enters the #1 setup, then marks `exitSignal` (`★ EXIT NOW`) on the live chart when an exit condition triggers so the user can square off.
  - In `FULL_AUTO`: auto-locks, auto-enters, trails SL/Target, and executes the exit automatically (including live Upstox `SELL` order when `routeThroughUpstox = true`).

### 2.3 API Endpoints (`/api/v1/trades`)
- `GET /api/v1/trades/presets` — Lists the Preset Traders with their real stats (win rate 0 until a trade has closed).
- `GET /api/v1/trades/preview-sizing` — Risk- and capital-based lot sizing preview (`max 3` parallel open trades per session).
- `POST /api/v1/trades` — Enters a locked `SessionPick` and starts its 1-second Trader loop.
- `POST /api/v1/trades/insert` — Direct trade insertion (`TradeDirectInsertRequest`).
- `POST /api/v1/trades/search` — Paginated search over active and historical trades.
- `GET /api/v1/trades/{id}` & `GET /api/v1/trades/{id}/stream` — Trade detail and 1s SSE stream.
- `POST /api/v1/trades/{id}/adjust` — Manual SL / Target override.
- `POST /api/v1/trades/{id}/llm-analyze` — Invokes the **LangGraph LLM Position Pilot** (`position_trail_graph`) to evaluate live 1m candles, volume, RSI(14), and Risk Profile, returning `HOLD` / `TRAIL_SL` / `STEP_TARGET` / `EXIT_NOW` with reasoning.
- `POST /api/v1/trades/{id}/exit` — Manual square-off.

### 2.4 LangGraph LLM Trader Pilot (`graph/trader_llm_graph.py`)
Two compiled LangGraph `StateGraph` workflows communicate with the local LLM (`OllamaClient.generate_structured`, with deterministic rule fallback when offline):
1. **`opportunity_selector_graph`** (`START → assess_risk_budget → llm_rank_and_pick → END`): Evaluates candidate setups discovered by each Trader against the Session's Risk Level (`L1–L4`), available capital, and open parallel trade count (`max 3`), selecting the best setup to lock.
2. **`position_trail_graph`** (`START → analyze_microstructure → llm_trail_decision → enforce_invariants → END`): Evaluates live 1m option candles, volume ratio, and Risk Level to decide whether to `HOLD`, `TRAIL_SL`, `STEP_TARGET`, or `EXIT_NOW` while enforcing that SL never moves downward.

---

## 3. Frontend UI (`frontend/src/modules/trade-history`)

### 3.1 Traders & Session Manager Hub (`/trades`)
- **2 Main Tabs** (`?tab=trader` | `?tab=sessions`):
  1. **`Opportunities Trader`**: Filter by Trader, inspect live & historical positions, and open any trade's live cockpit.
  2. **`Session Manager`**: Create sessions (`+ New Session`), toggle `UPSTOX LIVE / SIMULATED`, close/delete sessions, and jump into `/sessions/$id`.
- **4-Level Risk Configuration (`Configure Risk` button / `RiskConfigModal.tsx`)**:
  - **L1 · Capital Shield (Conservative)**: `2%` Max Day Loss · `0.25%` Risk/Trade · `2` Open Cap
  - **L2 · Institutional Standard (Balanced)**: `4%` Max Day Loss · `0.50%` Risk/Trade · `3` Open Cap
  - **L3 · Momentum Expansion (Growth)**: `6%` Max Day Loss · `1.00%` Risk/Trade · `3` Open Cap
  - **L4 · High-Conviction Max (Aggressive)**: `10%` Max Day Loss · `1.50%` Risk/Trade · `3` Open Cap

### 3.2 Full-Screen Trade Cockpit (`/trades/$tradeId`)
- Live 1s SSE-powered cockpit (`TradeDetailPage.tsx`) featuring real-data `TradePremiumChart.tsx` (real Upstox 1m candles + volume, Risk-Reward box, Trailing SL, and RSI(14) — zero synthetic data), `TradeLiveLadder.tsx`, **`Ask LangGraph LLM`** button, manual SL/Target override, and chronological `TradeDecisionLog.tsx`.

---

## 4. Two LLM-Supported Session Managers & Indian Index Playbook

When creating a session in `SessionDialog.tsx`, the user single-selects one of **2 LLM-supported Manager Psychology modes** (both wired to `opportunity_selector_graph` & `position_trail_graph` in `trader_llm_graph.py`):

1. **`My View · My Experience (LLM)`** (`FIB_GOLDEN_TRADER`) — Human trader psychology: patient `0.50–0.618` Golden Pocket pullbacks backed by Put/Call OI walls, zero FOMO chasing, strict `0.786` initial SL, locking SL at `0.618` at 80% of `1.0` Swing High, and stepping targets to `1.272` / `1.618`.
2. **`AI View · Indian Quant Flow (LLM)`** (`FLOW_MOMENTUM_TRADER`) — Indian index options scalping desk:
   - **Index Personalities (`INDEX_PROFILES`)**:
     - **NIFTY (NSE, Weekly Expiry: Tuesday):** Cleanest trend & VWAP/PDH/PDL/CPR respect, tightest spreads, round-number OI walls.
     - **BANKNIFTY (NSE, Monthly Expiry):** High-beta 100–200pt whipsaws & slingshot Gamma traps; requires strict ΔOI + narrow CPR/VWAP alignment.
     - **SENSEX (BSE, Weekly Expiry: Thursday):** Wider spreads in quiet hours, explosive Thursday PM Gamma bursts; tight spread check & fast `+1.0R` BE lock.
   - **Confluence & Macro Filters:** Current weekly ATM (`Δ ~0.45–0.50`) or 1-ITM (`Δ ~0.60`), India VIX (`12–18` sweet spot), `15m ORB` (`09:15–09:30 IST`), `PDH/PDL`, `Narrow vs Wide CPR` (skip wide-CPR chop), `Session VWAP` alignment, and `ΔOI` confirmation (Call unwinding + Put addition for CE; Put unwinding + Call addition for PE).
   - **IST Windows & Time-Stop:** `09:15–11:30` Morning ORB, `11:30–13:30` Mid-Day Theta Slump (avoid chop), `13:30–15:15` Gamma Window, hard exit by `15:15 IST`, plus `15–20m` Time-Stop if stalled.
   - **Trailing Discipline:** Hard `15%–25%` SL (no averaging down), `+1.0R` Breakeven + brokerage/STT lock, `+1.5R–2.0R` `5-EMA`/`9-EMA` or 50% peak lock, immediate exit on opposite VWAP cross.
   - **2025–2026 Index Setups Built into Core Engine (`setups.py`):**
     1. **`GAMMA_BLAST`**: Post-`13:30–15:10 IST` expiry afternoon breakout (Tuesday for NIFTY, Thursday for SENSEX) crossing tight consolidation and heavy round-number OI strike with expanding volume/delta cascade; 5-EMA 1m option chart trailing.
     2. **`LIQUIDITY_SWEEP`**: Trapped stop-hunt reversal piercing Previous Day High/Low (`PDH`/`PDL`) by `≥ 0.1 ATR` with 5-EMA non-touch alert candle and aggressive reclaim back inside.
     3. **`SCALP_IMPULSE`**: 1m/5m fast momentum burst with body `≥ 55%` of bar range, volume `≥ 1.25x` prior bar, and tight SL behind the impulse low/high.
     4. **`WEDGE_BREAKOUT` / `WEDGE_BREAKDOWN`**: Falling/rising wedge trendline break with RSI(14) divergence confirmation.
   - **Institutional Execution & Slippage Guards**:
     - Never use raw market orders during spikes; use pegged limit orders with **+1 to +2 pts buffer on NIFTY** and **+3 to +5 pts buffer on SENSEX**.
     - Spread filter: Skip any contract with `(Ask - Bid) / Mid > 0.5%`.
     - Expiry day schedule: NIFTY 50 Tuesday weekly expiry; SENSEX Thursday weekly expiry (SEBI single weekly expiry per exchange mandate).





## One session manager per session (17 Nov 2026)

> **Superseded the same day by [14. Opportunity finders](14-opportunity-finders.md):** the manager no longer
> decides which trader's setups a session gets. `traders` holds only the manager (same duty for every market);
> the new `finders` field holds the finders, chosen by the scope through each finder's `optionTypes`.

A session is now run by exactly **one** trader, called its session manager:

| Manager (UI name) | Trader | Takes |
|---|---|---|
| Indian Quant Desk (default) | FLOW_MOMENTUM_TRADER | every coded setup except the Fib pocket |
| My Experience | FIB_GOLDEN_TRADER | only FIB_GOLDEN_POCKET (with OI + volume confirmation), so few suggestions |

- `TradingSessionCreateRequest.traders` / `TradingSessionUpdateRequest.traders` must name exactly one trader
  (old codes are mapped); default `["FLOW_MOMENTUM_TRADER"]`. Validation: `trading_session_schema._one_trader`.
- The New Session dialog has a single-choice radio group (no chips, no Select all).
- On the session screen, picking the other trader hands the session over: `traders` becomes `[code]` and the old
  trader's open offers expire on the next loop tick (existing `no_longer_wanted` rule).
- Sessions created earlier with both traders keep working unchanged; picking one on the session screen converts them.

## Fib pocket: price action (17 Nov 2026)

`fib_pocket._price_action_check` is the third required confirmation (with OI and volume):

1. **Corrective pullback**: at least `MIN_PULLBACK_BARS` (2) bars, and no pullback body as big as the impulse's
   biggest body. One big bar into the pocket is a reversal, not a pullback.
2. **Rejection signal** on the last or previous 5-minute bar, one of:
   - `PIN_BAR`: wick >= 2x body and >= half the range, close in the top 40% (bottom 40% for PE), wick tip inside the
     0.45-0.786 zone;
   - `ENGULFING`: the turn bar's body engulfs the previous pullback-direction body;
   - `INSIDE_BAR_BREAK`: previous bar inside the one before it, turn bar closes beyond it.

The signal carries `priceActionConfirmed` and `priceAction {pattern, why}`; `setup_meta` saves `priceActionConfirm`
and `priceActionPattern` on the opportunity, pick and trade.

## Backtest = the session flow

`POST /backtest/range` takes `sessionManager` (`FLOW_MOMENTUM_TRADER` default, `FIB_GOLDEN_TRADER`, or `ALL` to
compare) and `riskLevel` (`LOW` default). Inside the replay, before a trade is simulated:

- the other trader's setups are out of scope (`range_backtest_service.session_block`);
- the live `session_risk.risk_gate` applies (setup class, trend side from `trend15`, reward:risk); a blocked signal is
  simulated as a counterfactual under rule `SESSION <reason>`, so the Rules tab shows what the risk level saved or cost;
- each trade is managed by its own trader: `premium_sim.simulate_fib` (lock 50% / 70% at 80% / 95% of the move,
  stop to the swing at Fib 1.0, then 1.272, book at 1.618; outcomes STOP / LOCKED / TARGET / EOD) or `simulate_momo`.

Fib in a replay: `analysis["replay"] = True` makes the OI and volume checks "not replayable" (no option-chain history,
no futures volume on index candles), so the backtest measures swing + pocket + price action only. Live takes fewer of
these trades. The report says so in `range.fibNote` and adds `perTrader` and `perPriceAction`.

Removed: `managerView` / `traderFilter` / `guardEnabled`. The old `MY_VIEW` filter dropped trades whose own result was
worse than -18% (look-ahead: it used the outcome to choose the trades), and the results screen re-filtered trades
with a keyword guess at the trader.

## 15-minute trend + 1-minute trigger on every opportunity (17 Nov 2026)

Every setup is confirmed on three timeframes before it becomes an opportunity (`setups.confirm_timeframes`):
15-minute trend (must agree for TREND setups, Fib included; FLAT or agreeing for RANGE setups), the 5-minute setup
itself, and the 1-minute trigger (`one_minute_check`: EMA9 side, no fresh extreme, stop untouched, not chasing,
target not reached). FII_OPEN_DRIVE (09:15 opening trade) is the one exception.

- Before about 10:00 fewer than three 15-minute bars have closed today. The 15-minute EMAs then run on the previous
  session's 15-minute bars followed by today's (`market_analysis.prior_session_15m`, source `15m+prev`) instead of
  the old 5-minute proxy. Live takes them from the noise-area history; the range backtest passes the previous day's
  bars (`prevSession5m`) and fetches 5 extra days before FROM for the first day.
- The evidence travels with the opportunity: `timeframeDetail` on the signal -> `setupMeta.timeframes` ->
  `SessionPickResponse.timeframes` = `{"15m": {trend, source}, "1m": {close, ema9, trigger}}`. Each opportunity
  card shows "15m UP" and "1m ✓ > trigger".

Session screen layout: left 60% = the session manager agent (trace, decision, folded autopsy sub-agent) and the
opportunities; right 40% (sticky) = the session itself: identity, controls, capital, locked picks, running and
closed trades, agent activity.

## Index view: today's bias and what each trader waits for (17 Nov 2026)

Each scan pass now also saves `spot` and `fibWatch` (`fib_pocket.watch`): per side, the Fib trader's stage --
`NO_SWING`, `SHALLOW` (impulse found, waiting for the pullback to reach 0.50-0.618), `IN_POCKET` (waiting for a
rejection candle), `STALE`, `FAILED` (past 0.786) -- with the swing, pocket and invalidation prices.

The opportunity finders ARE the two opportunity traders. On the Traders page (menu "Traders", Opportunity
traders tab) each trader card has a "Today across indices" strip (`traders/components/TraderTodayStrip.tsx`): one
line per index scanned today -- the bias and what THIS trader is waiting for there (Fib: the most advanced stage,
e.g. "CE waiting pocket"; Flow: the latest blocked momentum setup). Clicking it opens that trader's sheet
(`traders/components/TraderTodaySheet.tsx`) with every index stacked: bias, what the trader waits for (Fib: the
retracement bar with the pocket shaded; Flow: blocked setups and why), the temporary trend with its votes, and
recent scans. Both traders read the same per-index scans (`traders/components/useIndexToday.ts`).
There is no separate per-index strip.

## "Now" vs "day" (17 Nov 2026, after SENSEX showed BULL while falling)

At 15:07 SENSEX had dropped from 82,800 (14:30) to 82,578, yet the trader "today" view said BULL (+4). Every
input was a whole-day or older read: day type TREND up (set in the morning, +2), price vs the opening noise area
(still 0.5 pt above it, +1), FII positioning (yesterday's data, +1), 15-min trend (flat, 0). Nothing measured the
last hour.

Each scan now also saves `now` (`opportunity_finder/service/momentum_now.py`): the last ~60 minutes from 5-minute
bars -- EMA9/21 stack, futures VWAP side, the 60-minute change in ATRs (>= 0.75 ATR counts), 30-minute swing
structure (higher/lower highs and lows), and a turn off the 90-minute high/low (>= 1.5 ATR). >= +2 bullish,
<= -2 bearish.

Rule (user, 17 Nov 2026): the Traders area shows ONLY this temporary (last-hour) trend, per index. The overall /
whole-day trend is the Research Engine's job, so the old whole-day read (day type, noise area, FII positioning,
news) was removed from the Traders area (`indexView.ts` deleted). Tests: `tests/test_momentum_now.py` (replays today's SENSEX afternoon shape).

## Why the Fib trader found nothing (17 Nov 2026) -- and what changed

User: "so many Fib zones on NIFTY and SENSEX today, why does the system find none?"

Today (logs + saved scans): FIB_GOLDEN_POCKET fired 71 times after 13:50 IST, all rejected. FINNIFTY PE passed price
action ~40 times and was blocked only by the OI check ("no call-OI wall behind the pocket, futures NEUTRAL") and the
volume check ("turn bar volume below average"). The afternoon CE pockets on all four indices (14:50-15:00) never got
a turn candle and fell through 0.786: those swings failed and correctly did not trade.

6-month replay on real 1-minute data (`logs/realdata6m`, May-Nov 2026, 134 days per index), per swing that reached
the 0.46-0.70 pocket inside an entry window (~1,370 per index, about 10 a day):
- 44% died at "reward:risk < 1.3": the stop was fixed at 0.786 and a strong turn candle ate the reward;
- 29% never turned (failed pockets: correct), 11% turned too late (> 2 bars after the low);
- only ONE swing per side was ever examined: the one ending at the 3-hour extreme. Every smaller leg + pullback
  after the day's high was invisible.

Changes in `fib_pocket.py`:
- `_swings()`: every recent swing, newest first (a real local high/low not exceeded since; the leg starts after the
  last bar beyond it). `detect()` takes the newest swing that sets up; `watch()` reports the newest live one.
- stop = just beyond the pocket's rejection extreme (STOP_BUFFER_ATR = 0.15 ATR5), never beyond the 0.786
  invalidation (`stopBasis` says which).
- OI and volume confirmations are unchanged (still required live).

Result, same replay with live entry windows + 15-min trend + price action (OI/volume not replayable):
NIFTY 4 -> 22 trades in 6 months (+0.65R -> +0.09R avg; 4 trades is too few to judge), SENSEX 4 -> 22 (-0.40R ->
0.00R). It now sees the zones, but the pocket + price action alone is about breakeven on the index -- not an edge
on its own before option costs. Whether OI / volume add the edge can only be measured once enough option-chain
snapshots are recorded (chain_recorder). Tests: `tests/test_two_traders.py` (pocket stop, 0.786 cap, newer swing).
