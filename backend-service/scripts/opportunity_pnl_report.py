#!/usr/bin/env python3
"""
Opportunity P&L report for ONE trading day: every saved opportunity, whether it hit target or stop, and what one lot
of each would have made after charges.

  # on your Mac, inside the backend (container or venv with DB access + Upstox token):
  python scripts/opportunity_pnl_report.py                       # today (IST), re-checks every open opportunity first
  python scripts/opportunity_pnl_report.py --date 2026-11-05 --no-check
  # offline, from the SQL backup (no Upstox, outcomes as last saved):
  python scripts/opportunity_pnl_report.py --date 2026-11-04 --dump backup/latest.sql.gz

How P&L is computed (per opportunity, 1 lot, entry assumed filled at the saved entry price):
  TARGET_HIT  +(target - entry) x lot
  STOP_HIT    -(entry - stop)  x lot
  EXPIRED     marked at the window-end price when the checker supplied it (DB mode), otherwise counted as 0
  PENDING     0, flagged "open"
  charges     round-trip brokerage / STT / exchange / GST / stamp (services/costs.py) on every TARGET/STOP trade
It reports BOTH all rows and a de-duplicated view (first signal per contract per 30 minutes), because each iteration of
the engine can re-save the same contract and would otherwise count one idea several times.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import gzip
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.modules.opportunities.provider.underlying_config import get_config  # noqa: E402
from app.modules.opportunities.service.costs import round_trip_cost_pct  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
DEDUP_MINUTES = 30
COLS = ("id created_at status master_id iteration_no ref underlying_code underlying_type contract_id instrument_key "
        "option_type spot strike expiry entry stop target profit_margin_pct reward_risk confidence risk_level rank "
        "strategy reasons risks source valid_until outcome resolved_at is_latest").split()


def parse_ts(s: str) -> datetime:
    s = s.strip()
    if s.endswith("+00"):
        s += ":00"
    return datetime.fromisoformat(s).astimezone(UTC)


# ───────────────────────── loaders ─────────────────────────
def load_dump(path: Path, day: str) -> list[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    rows, cap = [], False
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("COPY public.trade_opportunities"):
                cap = True
                continue
            if cap:
                if line.startswith("\\."):
                    break
                r = dict(zip(COLS, line.rstrip("\n").split("\t")))
                created = parse_ts(r["created_at"])
                if created.astimezone(IST).date().isoformat() != day or r["status"] not in ("1", "ACTIVE"):
                    continue
                rows.append({
                    "id": int(r["id"]), "createdAt": created, "validUntil": parse_ts(r["valid_until"]),
                    "underlyingCode": r["underlying_code"], "contractId": r["contract_id"], "optionType": r["option_type"],
                    "strike": float(r["strike"]), "expiry": r["expiry"], "entry": float(r["entry"]),
                    "stop": float(r["stop"]), "target": float(r["target"]), "confidence": int(r["confidence"]),
                    "strategy": r["strategy"] if r["strategy"] != "\\N" else "", "outcome": r["outcome"],
                    "exitPrice": None, "masterId": int(r["master_id"]), "iterationNo": int(r["iteration_no"]),
                })
    return rows


async def load_db(day: str, check: bool) -> list[dict]:
    from sqlalchemy import select

    from app.core.db.session import async_session_factory
    from app.modules.opportunities.entity.opportunity_entity import TradeOpportunity
    from app.modules.opportunities.service.run_service import opportunity_run_service as svc

    start = datetime.fromisoformat(day).replace(tzinfo=IST).astimezone(UTC)
    end = start + timedelta(days=1)
    async with async_session_factory() as db:
        ents = (await db.execute(
            select(TradeOpportunity).where(TradeOpportunity.status == 1)
            .where(TradeOpportunity.createdAt >= start).where(TradeOpportunity.createdAt < end)
            .order_by(TradeOpportunity.createdAt)
        )).scalars().all()
        marks: dict[int, float] = {}
        if check and ents:  # re-evaluates every row against Upstox 1-minute candles and persists the corrected outcomes
            for res in await svc._evaluate_opportunities(db, list(ents), rewrite=True):  # noqa: SLF001
                marks[res["opportunityId"]] = res["exitPrice"]
            await db.commit()
        return [{
            "id": e.id, "createdAt": e.createdAt, "validUntil": e.validUntil, "underlyingCode": e.underlyingCode,
            "contractId": e.contractId, "optionType": e.optionType, "strike": float(e.strike), "expiry": e.expiry,
            "entry": float(e.entry), "stop": float(e.stop), "target": float(e.target), "confidence": e.confidence,
            "strategy": e.strategy or "", "outcome": e.outcome, "exitPrice": marks.get(e.id),
            "masterId": e.masterId, "iterationNo": e.iterationNo,
        } for e in ents]


# ───────────────────────── P&L ─────────────────────────
def price_trade(r: dict) -> dict:
    cfg = get_config(r["underlyingCode"])
    lot, exch = (cfg.lotSize, cfg.exchange) if cfg else (1, "NSE")
    entry, stop, target, o = r["entry"], r["stop"], r["target"], r["outcome"]
    if o == "TARGET_HIT":
        exit_p = target
    elif o == "STOP_HIT":
        exit_p = stop
    elif o == "EXPIRED" and r.get("exitPrice") is not None:
        exit_p = r["exitPrice"]
    else:
        exit_p = None
    resolved = o in ("TARGET_HIT", "STOP_HIT") or (o == "EXPIRED" and exit_p is not None)
    gross = (exit_p - entry) * lot if exit_p is not None else 0.0
    margin = (target - entry) / entry * 100
    cost = round_trip_cost_pct(entry, lot, exch, margin) / 100 * entry * lot if resolved else 0.0
    return {**r, "lot": lot, "exit": exit_p, "gross": round(gross, 2), "cost": round(cost, 2),
            "net": round(gross - cost, 2), "deployed": round(entry * lot, 2), "resolved": resolved,
            "ist": r["createdAt"].astimezone(IST).strftime("%H:%M")}


def dedupe(trades: list[dict]) -> list[dict]:
    last: dict[tuple, datetime] = {}
    out = []
    for t in sorted(trades, key=lambda x: x["createdAt"]):
        key = (t["underlyingCode"], t["optionType"], t["strike"], t["expiry"])
        if key in last and t["createdAt"] - last[key] < timedelta(minutes=DEDUP_MINUTES):
            continue
        last[key] = t["createdAt"]
        out.append(t)
    return out


def summarize(trades: list[dict]) -> dict:
    n = len(trades)
    tgt = sum(t["outcome"] == "TARGET_HIT" for t in trades)
    stp = sum(t["outcome"] == "STOP_HIT" for t in trades)
    exp = sum(t["outcome"] == "EXPIRED" for t in trades)
    pen = sum(t["outcome"] == "PENDING" for t in trades)
    gross = sum(t["gross"] for t in trades)
    cost = sum(t["cost"] for t in trades)
    net = gross - cost
    decided = tgt + stp
    wins = [t["net"] for t in trades if t["resolved"] and t["net"] > 0]
    losses = [t["net"] for t in trades if t["resolved"] and t["net"] <= 0]
    pf = (sum(wins) / -sum(losses)) if losses and sum(losses) < 0 else float("inf") if wins else 0.0
    return {"n": n, "target": tgt, "stop": stp, "expired": exp, "pending": pen, "winrate": (tgt / decided * 100) if decided else 0.0,
            "gross": gross, "cost": cost, "net": net, "pf": pf, "deployed": sum(t["deployed"] for t in trades if t["resolved"])}


def group(trades: list[dict], key) -> list[tuple[str, dict]]:
    g: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        g[key(t)].append(t)
    return sorted(((k, summarize(v)) for k, v in g.items()), key=lambda kv: kv[1]["net"], reverse=True)


def money(x: float) -> str:
    return f"{'-' if x < 0 else '+'}₹{abs(x):,.0f}"


def table(title: str, rows: list[tuple[str, dict]]) -> str:
    out = [f"### {title}", "", "| | Trades | Target | Stop | Expired | Win % | Gross | Charges | Net | PF |", "|---|---|---|---|---|---|---|---|---|---|"]
    for k, s in rows:
        pf = "inf" if s["pf"] == float("inf") else f"{s['pf']:.2f}"
        out.append(f"| {k} | {s['n']} | {s['target']} | {s['stop']} | {s['expired']} | {s['winrate']:.0f} | {money(s['gross'])} | -₹{s['cost']:,.0f} | **{money(s['net'])}** | {pf} |")
    return "\n".join(out) + "\n"


def conf_bucket(t: dict) -> str:
    c = t["confidence"]
    return "85+" if c >= 85 else "75-84" if c >= 75 else "65-74" if c >= 65 else "<65"


def report(day: str, trades: list[dict], source: str) -> str:
    uniq = dedupe(trades)
    allsum, uniqsum = summarize(trades), summarize(uniq)
    md = [f"# Opportunity P&L, {day}", "", f"Source: {source}. 1 lot per opportunity, charges included, entry assumed filled at the saved price.", ""]
    md.append(table("Overall", [("All saved rows", allsum), (f"De-duplicated (1 per contract / {DEDUP_MINUTES} min)", uniqsum)]))
    for title, tr in (("De-duplicated view", uniq),):
        md.append(table(f"{title}: by underlying", group(tr, lambda t: t["underlyingCode"])))
        md.append(table(f"{title}: by strategy", group(tr, lambda t: t["strategy"] or "(none)")))
        md.append(table(f"{title}: by option side", group(tr, lambda t: t["optionType"])))
        md.append(table(f"{title}: by confidence", group(tr, conf_bucket)))
        md.append(table(f"{title}: by hour (IST)", sorted(group(tr, lambda t: t["ist"][:2] + ":00"), key=lambda kv: kv[0])))
    md.append("### Every de-duplicated opportunity\n")
    md.append("| Time | Contract | Strategy | Conf | Entry | Stop | Target | Outcome | Net |\n|---|---|---|---|---|---|---|---|---|")
    for t in uniq:
        md.append(f"| {t['ist']} | {t['underlyingCode']} {t['strike']:.0f} {t['optionType']} | {t['strategy']} | {t['confidence']} | "
                  f"{t['entry']:.2f} | {t['stop']:.2f} | {t['target']:.2f} | {t['outcome']} | {money(t['net'])} |")
    unresolved = sum(1 for t in uniq if not t["resolved"])
    md += ["", "Notes:", f"- {unresolved} de-duplicated rows are EXPIRED/PENDING without an exit price and count as ₹0 (run without --dump / with the check to mark them).",
           "- Win % = target hits / (target hits + stop hits). Profit factor = gross wins / gross losses after charges.",
           "- Fills at the saved entry are optimistic: real entries slip, and the stop is checked before the target inside a 1-minute bar that touches both."]
    return "\n".join(md) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default=datetime.now(IST).date().isoformat())
    ap.add_argument("--dump", type=Path, help="read the SQL backup (.sql or .sql.gz) instead of the database")
    ap.add_argument("--no-check", action="store_true", help="DB mode: do not re-evaluate against Upstox candles first")
    ap.add_argument("--out", type=Path, default=ROOT / "backtest_out")
    a = ap.parse_args()
    if a.dump:
        rows, source = load_dump(a.dump, a.date), f"SQL backup {a.dump.name} (outcomes as last saved)"
    else:
        rows, source = asyncio.run(load_db(a.date, check=not a.no_check)), "database" + ("" if a.no_check else ", re-checked against Upstox 1-minute candles")
    if not rows:
        sys.exit(f"No opportunities found for {a.date} in the {source}.")
    trades = [price_trade(r) for r in rows]
    a.out.mkdir(parents=True, exist_ok=True)
    md = report(a.date, trades, source)
    (a.out / f"opportunity_pnl_{a.date}.md").write_text(md, encoding="utf-8")
    with open(a.out / f"opportunity_pnl_{a.date}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time_ist", "underlying", "strike", "side", "strategy", "confidence", "entry", "stop", "target", "outcome", "lot", "gross", "cost", "net"])
        for t in trades:
            w.writerow([t["ist"], t["underlyingCode"], t["strike"], t["optionType"], t["strategy"], t["confidence"], t["entry"], t["stop"], t["target"], t["outcome"], t["lot"], t["gross"], t["cost"], t["net"]])
    print(md)
    print(f"Saved: {a.out}/opportunity_pnl_{a.date}.md and .csv")


if __name__ == "__main__":
    main()
