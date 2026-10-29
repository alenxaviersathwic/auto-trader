# Derivatives and Expiry Calendar (as of October 2026)

## Option basics

- **Call (CE)** -- right to buy at the strike; **Put (PE)** -- right to sell.
- **Premium = intrinsic value + time value.** Intrinsic value is the
  in-the-money amount; time value shrinks to zero at expiry.
- **Greeks** this platform should reason about:
  - **Delta** -- sensitivity of premium to a 1-point underlying move;
    used in `menu_builder.py` to translate an underlying stop/target into
    a premium stop/target.
  - **Gamma** -- rate of change of delta; highest ATM, and highest of all
    on the day a series itself expires (0DTE). This is why `G-EXP-GAMMA`
    blocks new entries in an expiring series after 13:30 IST.
  - **Theta** -- time decay; accelerates sharply in the final 1-2 days of
    a series' life, fastest of all on expiry day itself.
  - **Vega** -- sensitivity to implied volatility (India VIX for indices).

## Weekly vs monthly expiry (current structure)

- **NIFTY** -- weekly, every **Tuesday** (NSE). Monthly = last Tuesday.
- **SENSEX** -- weekly, every **Thursday** (BSE). Monthly = last Thursday.
- **BANKNIFTY, FINNIFTY, MIDCPNIFTY** -- **monthly only**, last Tuesday (NSE).
- **BANKEX** -- **monthly only**, last Thursday (BSE).

This is the opposite of the pre-September-2025 convention (NSE used to run
Thursday weeklies). **Do not hard-code "Thursday = NSE expiry" anywhere.**

### Holiday shift rule

When an expiry weekday falls on a trading holiday, the contract expires on
the **previous trading day**. This is exactly what the platform's
`dayOverrides` field on a `Strategy` exists to encode -- update it from the
NSE/BSE/MCX holiday circulars every January, and whenever an exchange
publishes a mid-year holiday notice.

### Expiry-day mechanics (why it needs its own guardrails)

- Theta collapses fastest of the whole option's life on its own expiry day.
- Gamma risk is highest in the last 1-2 hours before close.
- SEBI's Oct-2024 package adds an extra 2% Extreme Loss Margin on *short*
  options on expiry day, and removes the calendar-spread margin benefit on
  expiry day (since 1 Feb 2025) -- expiry-day short-premium strategies need
  more free margin than a normal day.
- Full option premium is collected upfront from buyers since 1 Feb 2025 --
  no more "pay later" on option purchases.

## MCX calendar

| Contract | Lot | Option expiry rule |
|---|---|---|
| CRUDEOIL | 100 bbl | Options ~17th of month; futures ~19th (verify against the MCX calendar each month) |
| CRUDEOILM | 10 bbl | Same series dates as CRUDEOIL |
| NATURALGAS | 1,250 mmBtu | 2 business days before futures expiry |
| NATGASMINI | 250 mmBtu | As above |
| GOLD / GOLDM | 1 kg / 100 g | Monthly options |
| SILVER / SILVERM | 30 kg / 5 kg | Monthly options |
| COPPER, ZINC | 2,500 kg / 5 MT | Options liquidity too thin to trade reliably -- futures only on this platform |

Weekly US data that moves MCX energy contracts:

- **EIA Weekly Petroleum Status Report** -- Wednesday, 10:30 ET =
  20:00 IST (US daylight time) / 21:00 IST (US standard time, i.e. from
  November 2026 through the following March).
- **EIA Weekly Natural Gas Storage Report** -- Thursday, same IST windows
  as above (holiday weeks shift this by a day -- check the EIA release
  calendar).

US daylight saving time ends **1 November 2026**: all US-session event
windows and MCX's late close (23:30 -> 23:55) shift by an hour from that date.

## India VIX

A 30-day implied-volatility index derived from NIFTY options. Use it as a
**regime filter** (e.g. block naked short premium when VIX closes above
14.5, or when it spikes >8% intraday) -- not as a directional signal.

## Keeping this file correct

Re-verify this entire document against exchange circulars at least once a
quarter; every fact in it (expiry weekday, lot size, close time, STT rate)
has changed at least once in the 24 months before this was written
(October 2026).
