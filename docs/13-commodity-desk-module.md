# Commodity Desk module (17 Nov 2026)

Menu: Traders (third trader, "Commodity Desk"). Backend `app/modules/commodity_desk/`, frontend
`src/modules/commodity-desk/`, API `/api/v1/commodity-desk/*`, migration `0029_commodity_desk`.

## What it is

A specialist desk for MCX **crude oil, natural gas, gold and silver**, run as a third opportunity trader
(`COMMODITY_DESK_TRADER`, finder with `optionTypes = ["COMMODITY"]`). Code sub-agents report; an LLM head trader
decides. Since 0030 it is a finder only, not a session manager (see [14](14-opportunity-finders.md)).

| Sub-agent | File | What it reports |
|---|---|---|
| Session clock | `service/agents/session_clock.py` | MCX phase from the real London / New York clocks (ASIA, EUROPE, US_OPEN, US_LATE, CLOSING), EIA crude (Wed 10:30 ET) / natural-gas storage (Thu 10:30 ET), US CPI / FOMC / jobs report. CAUTION 20 min before to 15 min after; BLOCK in the last 10 min and the last 30 min of MCX |
| Price structure | `service/agents/structure_agent.py` | stance from 15-min trend, 5-min EMA stack, VWAP, last hour; setups: `DESK_TREND_PULLBACK`, `DESK_RANGE_BREAK`, `DESK_FIB_POCKET` (risk 0.5-2.5 ATR5, RR >= 1.5) |
| Option chain | `service/agents/options_agent.py` | the chain of the nearest NON-expiring expiry on its own future: PCR, OI walls, ATM IV, ATM spread / sellers (both sides illiquid -> BLOCK) |
| News & research | `service/agents/news_agent.py` | the Research Engine's read (votes only at score >= 25) + recent sudden-move explanations |
| Risk gate | `service/agents/risk_agent.py` | code, final say: refuses on clock BLOCK, illiquid side, RR < 1.5, structure hard the other way; warns on an OI wall in the path |
| Head trader | `service/head_trader.py` | local LLM (shared queue, JSON schema): writes 3-5 sentences of reasoning, TAKE one allowed setup or WAIT; a TAKE must name an allowed setup and have conviction >= 55. Model down -> a code rule decides and says so (source CODE) |

## How a decision becomes a trade

`desk_service.run()` runs inside every commodity scan (`opportunity_finder/graph/nodes.py`). The head trader thinks
in the background (5-30 s); a TAKE is acted on at the NEXT scan only if it still holds: decision < 3 min old, price
within 0.3 ATR5 of the planned entry, still allowed by the risk gate. Then it enters the normal opportunity flow
(contract choice, liquidity / spread / delta, Time Machine, edge after charges) and reaches the COMMODITY sessions
that have the desk among their finders. It asks the head trader again when the setups on the table change, otherwise every 10 minutes.
Every decision is stored (`commodity_desk_decisions`: reports, setups, refusals, reasoning, outcome).

## Orders (changed 17 Nov 2026)

- The desk is no longer simulated-only. Its picks are acted on (by hand with another broker, or through Upstox), so
  it follows the session's own `routeThroughUpstox` switch like every other finder
  (`trader_presets.routes_to_broker(session_routes)`). The "SIMULATED ONLY" badge and the forced-off toggle are gone.
- The desk is live-only: it is not offered in the backtest (no history of chains, news or model answers).

## Sudden-move news sub-agent (all underlyings)

`service/move_watch.py`, on every scan of every underlying: a move of >= 2.5 ATR5 and >= 0.25% (index) / 0.4%
(commodity) in 15 minutes -> stored (`market_moves`), fresh headlines that NAME the instrument
(`research/service/news_service.recent_headlines`), the LLM explains it using only those headlines or says
NO_CLEAR_NEWS (flows / technical). Never invents a cause. Notification kind `MARKET_MOVE`; shown in the desk and as
the "News sub-agent" card on every non-desk session.

## Settings

`COMMODITY_DESK_ENABLED` (default true), `MOVE_WATCH_ENABLED` (default true).

## Not done / honest limits

- No backtest: the desk needs live chains, news and the model. Judge it on its sessions' results.
- The head trader prompt is tested with a mocked model only; the first live decisions show source LLM vs CODE.
- Holiday-shifted EIA releases are not modelled (the warning comes on the usual day).

## Live working flow (UI)

`GET /commodity-desk/live` (in-memory, this process; polled every 2 s by `useDeskLive`): per commodity the last
sub-agent pass (time, number, duration, each agent's stance), the risk gate's allowed / refused count, whether the
head trader is thinking right now (`thinkingSince`) and its last decision; plus the news checks running now and their
step (recording -> reading the feeds -> LLM explaining). `DeskFlow.tsx` draws it: each real pass replays as a wave
through Clock / Structure / Chain / News -> Risk gate -> Head trader -> Decision; connectors flow while the desk is
live (a pass in the last 60 s) and stop when it is idle; the head trader pulses with a running "thinking Ns" only
while the model actually works. The News sub-agent card on every session shows its running checks the same way.
Animations stop under `prefers-reduced-motion`.
