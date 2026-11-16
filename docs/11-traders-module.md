# 11. Active Traders & Live Execution Module (`trades`)

> **Document Type:** Module Specification
> **Status:** Authoritative
> **Module path:** `backend-service/app/modules/trades`, `frontend/src/modules/trades`

---

## 1. Overview (updated 16 Nov 2026: two traders)

The `trades` module has **two Traders**. A Trader is (1) the setups it may take and (2) how it manages the position.

| | `FIB_GOLDEN_TRADER` — Fib Golden-Pocket Trader | `FLOW_MOMENTUM_TRADER` — Flow & Momentum Trader |
|---|---|---|
| Takes | Only `FIB_GOLDEN_POCKET` (`opportunities/service/fib_pocket.py`) | Every other setup the policy lets trade: `NOISE_BREAKOUT`, `INSIDE_BAR`, `FII_OPEN_DRIVE`, `LATE_DAY_MOMENTUM`, and `VWAP_PULLBACK` / `RANGE_BREAKOUT` / `GAP_GO` inside an active breakout |
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

`marketTelemetry.oaAnalysis` is built by `opportunities/service/chain_view.py` from the newest `option_chain_snapshots` row (recorded about every 15 s while the scanner runs) and refreshed about once a minute. It carries `source: "CHAIN_SNAPSHOT"` and `asOf`. OI change is measured against the snapshot about 15 minutes earlier and is `null` when there is none. When no snapshot is newer than 5 minutes the value is `null` and the UI says so. Until 16 Nov 2026 this field held hard-coded numbers; trades entered before then still carry them and the UI ignores any ladder without `source`.

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

## 3. Frontend UI (`frontend/src/modules/trades`)

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




