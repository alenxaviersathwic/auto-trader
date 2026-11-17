# 14. Opportunity finders, markets (`optionTypes`) and session managers (17 Nov 2026)

Menu: Traders → Opportunity traders. Backend `app/modules/opportunity_finder/` (entity, schema, repository, service,
controller `opportunity_finder_*`), frontend `src/modules/traders/` (types, api, queryKeys, hooks
`useOpportunityFinders`), API `/api/v1/opportunity-finders`, migration `0030_opportunity_finders`.

## The idea

- **Every opportunity finder is the same kind of agent.** All of them read the scans, think, propose setups and
  manage the trade they own; they have the same fields and are rendered by the same card. They differ only in
  strategy and method (`strategies`, `checks`, `entryLogic`, `trailLogic`) and in the markets they work on.
- **Finders are split by market, managers are not.** A commodity finder works from international drivers (US /
  London hours, EIA and US data, dollar, global news); an index finder ~90% from national ones (FII flow, NSE
  option chain and dealer gamma, RBI / domestic news). So the market split lives on the finder (`optionTypes`).
- **The session manager's duty is the same for every market** (pick the best offer, size it to capital, analyse
  batches, autopsy its own trades). There is no "Commodity Desk" session manager any more.
- **No simulated-only finder.** Every finder, the Commodity Desk included, follows the session's own Upstox
  switch (`routeThroughUpstox`, off by default). Picks are also acted on by hand with another broker.

## Entity `opportunity_finders` (`OpportunityFinder`)

| Field (API) | Column | Meaning |
|---|---|---|
| `code` | `code` | `FLOW_MOMENTUM_TRADER`, `FIB_GOLDEN_TRADER`, `COMMODITY_DESK_TRADER` (unique among active rows) |
| `name`, `shortLabel`, `badgeColor` | … | display |
| **`optionTypes`** | `option_types` JSONB array | markets it works on: any of `INDEX`, `COMMODITY`; never empty |
| `methodology`, `entryLogic`, `trailLogic` | … | how it thinks / enters / manages |
| `strategies` | JSONB | setups it owns |
| `checks` | JSONB | what it checks before entering, in order |
| `drivers` | `drivers` | what moves its market (national vs international) |
| `liveOnly` | `live_only` | needs live chains / news / LLM: not in the backtest |
| `enabled` | `enabled` | switched off = never offered, never run |
| `sortOrder` | `sort_order` | display order |
| `extra` | JSONB | reserved |

Seeded by migration 0030 (values frozen in the migration):

| Finder | optionTypes | Drivers |
|---|---|---|
| Flow & Momentum Trader | `["INDEX"]` | mostly national |
| Fib Golden-Pocket Trader | `["INDEX"]` | mostly national |
| Commodity Desk | `["COMMODITY"]` | international |

The setup logic stays in code (`opportunity_finder/service`, `commodity_desk`); the row is the finder's editable
profile. `trade_history/service/trader_presets.py` keeps the same values as code defaults (used before the table
is read, and in tests).

## API (`/api/v1/opportunity-finders`)

| Method | Path | |
|---|---|---|
| GET | `/opportunity-finders?optionType=INDEX` | finders (all, or only those working on that market), display order |
| POST | `/opportunity-finders/search` | `OpportunityFinderSearchFilter` (BaseFilter + `optionType`, `enabled`; default sort `sortOrder asc`) |
| GET | `/opportunity-finders/{code}` | one finder |
| PUT | `/opportunity-finders/{code}` | change `optionTypes` (cleaned: upper-case, de-duplicated, ≥1, only INDEX/COMMODITY), `enabled`, `name` |

## How `optionTypes` is used

1. **Session create** (`trading_session_service.create`): the request names one manager in `traders` and the finders
   in `finders`. `opportunity_finder_service.check_session_finders(scope, finders)` refuses a finder whose
   optionTypes do not include the scope; an empty `finders` means every enabled finder that covers the scope.
   The same check runs when `finders` is updated.
2. **Session loop** (`session_loop_service`): a pick is offered only if its owning finder is in the session's
   `finders` (excluded reason `finder not in session`). The manager in `traders` does not filter.
3. **Scan** (`opportunity_finder/graph/nodes.py`): after the setups are confirmed, a setup whose owning finder
   does not cover the underlying's type is moved to `rejected` ("its finder does not work on COMMODITY"); the
   Commodity Desk runs only if it covers COMMODITY. The scan reads an in-process cache
   (`opportunity_finder_service.covers()`), refreshed from the table at most every 60 s and right after an update.

## Sessions: manager vs finders

| Session field | Holds |
|---|---|
| `traders` | the session **manager**: exactly one of `FLOW_MOMENTUM_TRADER` (Indian Quant Desk, default) or `FIB_GOLDEN_TRADER` (My Experience). Any scope. An old `COMMODITY_DESK_TRADER` manager is read as Indian Quant Desk. |
| `finders` (new, migration 0030) | the opportunity finders feeding the session; each covers the scope |

Migration back-fill: old sessions get `finders = traders` (what they used before); old Commodity Desk sessions get
Indian Quant Desk as manager and the desk as finder. Reading code falls back the same way
(`trader_presets.session_finder_codes`). Switching manager on the session screen keeps the finders.

## UI

- **Traders → Opportunity traders**: one card per finder, all alike, in `sortOrder`. The header has `INDEX` /
  `COMMODITY` toggles (the finder's markets; the last one cannot be switched off) and the drivers line. A
  finder's "today" strip and sheet show only scanners of its markets. The Commodity Desk card carries its live
  sub-agent view like any other finder's working view.
- **Traders → Session managers**: two managers, no scope.
- **New Session**: 3. Session Manager (two, any market) → 4. Market scope & underlyings → **5. Opportunity
  Finders · {scope}**: only finders whose optionTypes include the scope, all picked by default. 6. Upstox routing:
  the session's own switch, for every finder.
- **Session screen**: the manager panel shows the session's finder badges; the desk's live view appears when the
  desk is one of the session's finders.

## Note on behaviour change

Before 0030, the Flow and Fib traders also ran on MCX. With the seeded `["INDEX"]` they no longer do; add
`COMMODITY` to them on the Traders page to bring that back.
