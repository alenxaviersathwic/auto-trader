# Indian Market Basics (as of October 2026)

Reference doc for the auto-trader platform. Source: Claude research task
`wf-73cd02ba-57fd-81e6-bc87-e3915505046a` (Oct 2026). Re-verify Section 1
facts quarterly -- regulation has changed every few months since 2024.

## Exchanges and regulator

- **NSE** and **BSE** -- equity and equity-derivatives exchanges.
- **MCX** -- commodity derivatives exchange (energy, bullion, base metals).
- **SEBI** -- the regulator for all three; clearing corporations guarantee
  settlement, and margins (SPAN + exposure/ELM) are collected upfront.

## Indices traded on this platform

| Index | Exchange | Weekly expiry | Monthly expiry | Lot size (Oct-Dec 2026 series) |
|---|---|---|---|---|
| NIFTY | NSE | Every Tuesday | Last Tuesday | 65 |
| BANKNIFTY | NSE | None (discontinued Nov 2024) | Last Tuesday | 30 |
| FINNIFTY | NSE | None | Last Tuesday | 60 |
| MIDCPNIFTY | NSE | None | Last Tuesday | 120 |
| SENSEX | BSE | Every Thursday | Last Thursday | 20 |
| BANKEX | BSE | None | Last Thursday | 30 |

Index options are European-style and cash-settled. NSE reviews lot sizes
using March/September average prices -- **lot size and expiry date must be
read from the live broker instrument master every morning**, never
hard-coded for long (see guardrail `G-LOT-MASTER`). This file's table was
last reconciled with `underlying_config.py` on 2026-10-29.

MCX options are mostly options *on futures* and devolve into futures if
held in-the-money at expiry (see `docs/02-derivatives-and-expiry-calendar.md`).

## Session timings

| Segment | Hours (IST) | Notes |
|---|---|---|
| NSE equity derivatives | 09:15 - 15:40 | Extended from 15:30, effective 3 Aug 2026. Closing-price VWAP window 15:10-15:40; cash-market Closing Auction Session 15:15-15:35 |
| BSE (SENSEX/BANKEX) | 09:15 - 15:30 | BSE had not matched NSE's extension as of Oct 2026 |
| MCX non-agri (crude, nat-gas, bullion, base metals) | 09:00 - 23:30 (US daylight time) / 09:00 - 23:55 (US standard time) | Switches to the later close after US DST ends (1 Nov 2026) |

The pre-open auction (09:00-09:08 NSE cash market) sets the opening print
that feeds the day's first candle -- that is why strategies in this
platform wait for the first 30-minute bar to close before evaluating signals.

## Costs

- **STT** (from 1 Apr 2026, Finance Act 2026): options 0.15% of premium on
  the sell side (was 0.10%); exercised options 0.15% (was 0.125%); futures
  0.05% (was 0.02%).
- **CTT on MCX** (unchanged in Budget 2026): options 0.05% of premium
  (seller); futures 0.01% (seller); exercised options with delivery
  0.0001% (purchaser).
- Plus brokerage, exchange transaction charges, SEBI fee, stamp duty, GST.
- Round-trip cost on a typical NIFTY ATM weekly option is roughly 1% of
  premium before slippage -- see `docs/04-risk-and-profit-management.md`
  for why this matters for a 5-10% target design.

## What SEBI's loss studies say (why this matters for a many-small-trades design)

| Study | Period | Individuals with net losses | Aggregate net loss |
|---|---|---|---|
| Jan 2023 | FY22 | 89% | avg loss ~Rs1.1 lakh |
| Sep 2024 | FY22-FY24 | 93% (over 1 crore traders) | ~Rs1.8 lakh crore |
| Jul 2025 | FY25 | 91% | Rs1,05,603 crore (+41% vs FY24) |
| Aug 2026 (Press Release 50/2026) | FY26 | 87.7% (82.1% before costs) | Rs91,685 crore; options = 92% of losses; ~Rs24,800 crore transaction costs; avg loss ~Rs1.17 lakh |

The loss rate improved mostly because *participation* fell, not because
traders got better: 82.1% were still losing **before** any costs. Costs
then push a meaningful slice of marginal traders from break-even into
loss. For a platform aiming for frequent small (5-10%) targets, this is
the single most important fact in the whole research project: **every
strategy here must be proven positive after realistic costs, on your own
fills, in paper mode, before going live.**

## Regulatory changes that broke old assumptions (2024-2026)

- SEBI circular 1 Oct 2024: one benchmark index with a weekly expiry per
  exchange (effective 20 Nov 2024) -- removed BANKNIFTY/FINNIFTY/MIDCPNIFTY
  weeklies on NSE and BANKEX/SENSEX50 weeklies on BSE.
- SEBI circular 26 May 2025: all equity-derivative expiries restricted to
  Tuesday or Thursday; NSE = Tuesday, BSE = Thursday, effective for
  contracts expiring on/after 1 Sep 2025.
- NSE circular NSE/FAOP/70616 (3 Oct 2025): lot size cuts -- NIFTY 75->65,
  BANKNIFTY 35->30, FINNIFTY 65->60, MIDCPNIFTY 140->120 (effective 6 Jan
  2026 weekly, 27 Jan 2026 monthly).
- NSE circular 29 May 2026: F&O close extended 15:30->15:40, effective
  3 Aug 2026.
- Finance Act 2026: STT hike effective 1 Apr 2026 (see Costs above).
- SEBI circular 1 Sep 2025 (effective 1 Oct 2025): entity-level intraday
  position-limit monitoring on index options (Rs5,000cr net / Rs10,000cr
  gross per side), checked by random intraday snapshots including one
  between 14:45-15:30. Institutional-scale, but signals SEBI is actively
  policing expiry-day flows -- expect more changes.

**Any "Thursday expiry" or lot-size assumption written into this codebase
before September 2025 / January 2026 is now wrong.** This is exactly the
bug class the Oct-2026 research run fixed in `underlying_config.py`
(`NIFTY` 75->65, `FINNIFTY` 65->60 lot sizes; NSE close 15:30->15:40).
