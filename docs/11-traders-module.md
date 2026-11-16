# 11. Active Traders & Live Execution Module (`trades`)

> **Document Type:** Module Specification
> **Status:** Authoritative
> **Module path:** `backend-service/app/modules/trades`, `frontend/src/modules/trades`

---

## 1. Executive Overview

The **Active Traders** module (`trades`) replaces the generic standalone opportunity workflow with a **Trader-First Institutional Architecture** powered by **3 Preset Specialist Traders**:

1. **`FIB_GOLDEN_TRADER` — Fibonacci Golden-Pocket Trader**:
   - **Discovery:** Finds `0.50–0.618` Fibonacci retracement pullbacks inside directional intraday trends with Put/Call OI wall support.
   - **1-Second Brain:** Sets initial SL below `0.786` retracement; trails SL to `0.618` at 80% of Target `1.0`, then steps Target along `1.272` and `1.618` Fibonacci extensions.
2. **`ORB_WAVE_TRADER` — ORB & Momentum Wave Runner**:
   - **Discovery:** Captures 15m/5m Opening Range Breakouts (`ORB`), FII Open Drive, and volatility squeezes with `volumeRatio >= 1.35x`.
   - **1-Second Step-Wave Brain:** Re-analyzes wave potential every second. When planned Target is `100` (e.g. Entry `50`, SL `35`) and live momentum projects `150` (`projectedTarget = 150`), at `75–80%` progress (`LTP = 90`) it locks **SL at `75`** and steps **Target `100 → 120`**, and when approaching `120` (`LTP = 118`) it locks **SL at `100`** and steps **Target `120 → 150`**.
3. **`FLOW_VWAP_TRADER` — Institutional VWAP & OI Flow Trader**:
   - **Discovery:** Tracks institutional option-chain Open Interest (`OA`) unwinding, PCR shifts, and Session VWAP reclaims.
   - **1-Second Step-Guard Brain:** Protects capital rapidly: ratchets SL to `+30%` at 50% progress and `+50%` at 80% progress, stepping Target up on high-volume surges.

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
- `GET /api/v1/trades/presets` — Lists the 3 Preset Institutional Traders with live & historical stats.
- `GET /api/v1/trades/preview-sizing` — Risk- and capital-based lot sizing preview (`max 3` parallel open trades per session).
- `POST /api/v1/trades` — Enters a locked `SessionPick` and starts its 1-second Trader loop.
- `POST /api/v1/trades/insert` — Direct trade insertion from the Traders Desk using Fibonacci + OA (Option Chain) parameters or a Trader Suggestion (`TradeDirectInsertRequest`).
- `POST /api/v1/trades/search` — Paginated search over active and historical trades.
- `GET /api/v1/trades/{id}` & `GET /api/v1/trades/{id}/stream` — Trade detail and 1s SSE stream.
- `POST /api/v1/trades/{id}/adjust` — Manual SL / Target override (or 1-click Fib Step-Wave apply).
- `POST /api/v1/trades/{id}/exit` — Manual square-off.

---

## 3. Frontend UI (`frontend/src/modules/trades`)

### 3.1 Traders & Live Execution Desk (`/trades`)
- **3 Preset Trader Cards**: Displays each Trader's methodology, discovery rules, 1-second brain logic, live loop count, win rate, and realized P&L.
- **Right-Side Bar (`TraderSideSheet.tsx`)**: Synced with URL search parameters (`?sheet=SUGGESTIONS|INSERT_TRADE|TRADE_INSPECT&trader=...&tradeId=...`):
  1. **`SUGGESTIONS`**: Live setups & Fib+OA templates for the chosen Trader, with 1-click **`Open in Fib + OA Chart`** and **`Quick Launch 1s Trade`**.
  2. **`INSERT_TRADE`**: Interactive **Fibonacci Golden-Pocket & Wave Extension Chart** + **OA Option-Chain Call/Put OI Butterfly Chart** (`FibAndOACharts.tsx`) with automatic `0.618` / `0.786` / `1.0` / `1.272` / `1.618` calculation.
  3. **`TRADE_INSPECT`**: Opens when clicking any live or historical trade row, displaying the 1s Trader Brain suggestion banner, 1-click **Step Wave** / **Square Off**, Live Price Ladder, 1m Trade Graph, Fibonacci Chart, and OA Option-Chain Chart.

### 3.2 Full-Screen Trade Cockpit (`/trades/$tradeId`)
- Live 1s SSE-powered cockpit (`TradeDetailPage.tsx`) featuring `TradePremiumChart.tsx` (Entry, Trailing SL, Step Target, `★ WAVE EXT` ceiling, and Exit Marks), `TradeLiveLadder.tsx`, `FibRetracementChart`, `OptionChainOAChart`, manual override form, and chronological `TradeDecisionLog.tsx`.

