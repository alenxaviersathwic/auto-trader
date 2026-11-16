# 12. Learning Module: Session Manager, Batches and the Autopsy Agent

> **Status:** Authoritative (added 17 Nov 2026)
> **Module paths:** `backend-service/app/modules/learning`, `backend-service/app/modules/sessions/service/session_manager.py`, `frontend/src/modules/learning`
> **Reference:** trading-engine's post-trade autopsies, strategy net-expectancy quarantine and candidate promotion (`ARCHITECTURE_AND_FLOW.md` §18, §21.1, §29 there)

## 1. Flow

```text
opportunity engine ──saves──▶ opportunities ──read by──▶ session loop ──▶ session manager (best suggestion)
       ▲                                                     │
       │ paused setups + applied guards                      ▼  lock / enter
       │ (learning view, live engine only)              trade pilot ──exit──▶ autopsy agent
       │                                                                          │
       └──────────────────── setup scorecards + guards ◀──────────────────────────┘
```

## 2. Session manager (`sessions/service/session_manager.py`)

- **Best suggestion** (`SessionLoopResponse.manager`): the top open pick by the loop's ranking (expected net after charges, then confidence, then reward:risk), with reasons from the session's capital, the remaining loss budget, the risk level and the setup's scorecard, and cautions (the pick's own risks, a losing scorecard, the last parallel slot, uncalibrated confidence).
- **Batches**: every pick one loop pass offered (same `offeredAt`). `POST /sessions/{id}/batches/search` (BaseFilter, newest first).
- **Analyse**: `POST /sessions/{id}/batches/analyse {batchKey}` checks each pick's opportunity against real 1-minute candles (`opportunity_run_service.analyse_opportunities`, which resolves only PENDING rows) and against the trade taken from it, and stores the result on the pick (`session_picks.outcome_analysis`).

| Pick verdict | Meaning |
|---|---|
| `TAKEN_WIN` / `TAKEN_LOSS` / `TAKEN_RUNNING` | entered; result from the trade (and its autopsy verdict) |
| `LOCKED_NOT_ENTERED` | locked, never entered |
| `MISSED_WINNER` | not taken, opportunity reached its target |
| `GOOD_SKIP` | not taken, opportunity hit its stop |
| `NO_MOVE` | not taken, neither target nor stop in its window |
| `PENDING` | window open or no candles |

Batch verdict: `SUCCESS` (more picks reached target than failed), `FAILURE` (the reverse), `MIXED` (equal), `NO_MOVE`, `PENDING`.

## 3. Autopsy agent (`learning/service/autopsy_agent.py`)

Runs inside `trade_service._finalize_exit` for every exit (never blocks the exit). Measures in R (entry − initial stop): `rMultiple`, `mfeR`, `maeR`, `givebackPct`; verdict (`RAN_TO_TARGET`, `PROTECTED_PROFIT`, `WON_BUT_GAVE_BACK`, `FEES_ATE_PROFIT`, `GAVE_BACK_WINNER`, `CUT_EARLY`, `NEVER_WORKED`, `STOPPED_OUT`); what went right / wrong; failure tags `AGAINST_TREND`, `LATE_ENTRY`, `GAVE_BACK`, `FEES_ATE_PROFIT`, `NEVER_WORKED`. Stored in `trade_autopsies` (one per trade).

## 4. What the results change (`learning/service/learning_rules.py`)

**Setup scorecards (strategy update, automatic).** Per setup over 14 days (only trades after a manual resume): closed trades, wins, net P&L, average R. At least 5 closed trades and a net loss → `PAUSED`: the live engine stops signalling it (`setups.policy_block`) and the session skips its saved opportunities. It comes back when the losers age out of the window, or by **Resume**. Win rate alone never pauses: momentum setups win rarely by design.

**Guards (rule update).** A failure tag repeated 3 times on one setup inside the window proposes a guard. Applied guards are enforced; each is mirrored as an `AUTOPSY-<id>` rule on the Rules page (enabled while applied).

| Tag | Guard | Enforced in |
|---|---|---|
| `AGAINST_TREND` | `WITH_TREND_ONLY` | session loop skips the setup's against-trend picks |
| `LATE_ENTRY` | `NO_LATE_ENTRY` (60 min) | engine `policy_block` |
| `GAVE_BACK` | `EARLIER_BREAKEVEN` (+1R) | trade pilot momentum trail (momentum setups only) |
| `FEES_ATE_PROFIT` | `MIN_TARGET_PCT` (1.5 × median planned target) | session loop |

`settings.AUTOPSY_AUTO_APPLY_GUARDS` (default `False`): `True` applies guards as soon as they are proposed. A rejected guard is not re-proposed for 14 days.

The live engine gets the learning view through `analysis["learning"]` (set in `graph/nodes.py`), so backtests and replays are never affected.

## 5. API (`/api/v1/learning`)

`POST /autopsies/search`, `GET /autopsies/trade/{tradeId}`, `POST /scorecards/search`, `POST /scorecards/{setup}/resume`, `POST /guards/search`, `POST /guards/{id}/apply`, `POST /guards/{id}/reject`.

Migration `0027_learning_and_batches`: `trade_autopsies`, `setup_scorecards`, `setup_guards`, `session_picks.outcome_analysis` (+ archive).

## 6. UI (`/sessions/$id`)

Laid out after trading-engine's session desk, on auto-trader's colour tokens (`te-` classes in `index.css`): header with Mode / Risk / Upstox / scanner / Close, stat row, **Session manager** card (best suggestion, reasons, cautions, Lock), **Current** tab (setups per trader, collapsible cards with the stop / entry / target range) and **History · batches** tab (Analyse / Re-analyse per batch), right column with running trades, session trades with autopsy verdicts, and the **Autopsy agent** panel (scorecards with Resume, learned rules with Apply / Reject). The trade page shows the autopsy under the decision log.
