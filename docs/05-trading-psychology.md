# Trading Psychology, Emotion and Discipline

An algo removes in-the-moment decisions, but not the temptation to switch
the rules off after a loss. This file names the failure modes SEBI's loss
studies and practitioner literature keep pointing to, and the structural
fix this platform uses for each one.

## Fear

**Symptom:** exiting winners early; skipping a valid signal right after a
loss, out of a fear it will lose again. **Fix:** pre-committed targets and
mandatory execution of any signal that clears the guardrail stack --
the system does not get to "feel" about a trade; it either passes the
rules or it doesn't.

## Greed

**Symptom:** moving a target further away mid-trade because it's winning;
oversizing the next trade after a win. **Fix:** fixed sizing formula
(risk-based, from the stop distance -- see `docs/04-risk-and-profit-management.md`);
a hard max-lots-per-strategy cap that a winning streak does not unlock.

## Revenge trading

**Symptom:** taking an unplanned, rule-breaking trade to "win back" a
loss. SEBI's studies note that a large share of loss-making traders kept
trading at the same or higher frequency after losses, rather than less.
**Fix:** the consecutive-loss halt (`G-RISK-CONSEC`) and daily-loss halt
(`G-RISK-DAY`) are hard stops that cannot be overridden intraday by
anyone, including the person who built the system.

## Overtrading

**Symptom:** taking every marginal setup; fatigue late in the session
leading to worse decisions. **Fix:** the cost-ratio filter
(`G-COST-RATIO`) and the max-trades-per-day cap (`G-RISK-MAXTRADES`) --
both exist because costs, not bad luck, are what turn a marginal edge into
a loss at high frequency.

## FOMO

**Symptom:** chasing a gap or a breakout late, after the good risk/reward
has already gone. **Fix:** no entries in the first 30-minute bar
(`G-TIME-OPEN`); the gap-risk filter (`G-GAP`); entries only ever
evaluated at a bar close, never mid-candle on a "it's moving now" impulse.

## Hope / denial

**Symptom:** refusing to take a stop because "it'll come back"; averaging
into a losing position to lower the average cost. **Fix:** stops are
placed at the broker immediately on fill (step 4 of the trading flow), and
`G-NO-AVERAGING` blocks adding to a losing position outright.

## The discipline system, end to end

1. **Written strategy specs** -- every strategy in the registry
   (`docs/02-derivatives-and-expiry-calendar.md` and the `Strategy`/`Rule`
   DB records) states exactly when it fires, what invalidates it, and what
   evidence it's based on, before it ever sees live money.
2. **A journal for every trade** -- signal, the reason it fired, the
   guardrails it passed, and the outcome. Any manual override is logged
   explicitly and reviewed in the next post-market session.
3. **A weekly review** against the expectancy numbers from
   `docs/04-risk-and-profit-management.md`, not against how any single day
   felt.
4. **Rule changes happen only in post-market review** (step 7 of
   `docs/03-intraday-trading-flow.md`) -- never intraday, and never as a
   same-day reaction to one bad trade. The whole point of an algo platform
   is to decide the rules when calm and follow them when not; changing a
   rule mid-session because of today's P&L defeats that purpose entirely.

## The one number worth remembering

SEBI's FY26 study: 82.1% of individual F&O traders lost money **before**
any transaction costs. The main problem most retail traders have is
negative-expectancy behaviour -- not bad luck, not bad timing, not a
missing indicator. Every guardrail in this registry exists to keep this
platform out of that 82.1%, mechanically, regardless of how any single
day's trading feels while it's happening.
