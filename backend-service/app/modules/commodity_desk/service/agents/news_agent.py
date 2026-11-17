"""
News sub-agent: what the news side says about this commodity, for the head trader. Pure: the caller passes the
Research Engine's latest read (research/service/news_service.py) and the move watcher's recent explanations.

  research   direction counts only when its score is >= MIN_DIRECTION_SCORE (25, research/scoring/score_rank.py):
             weaker reads are reported as context, never as a vote
  moves      a sudden move in the last 3 hours and the news found for it (service/move_watch.py)
Nothing here is invented: no research run -> "no research yet"; no headline -> none listed.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

MIN_DIRECTION_SCORE = 25.0


def _age(iso: str | None, now: datetime) -> str:
    if not iso:
        return ""
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return ""
    mins = (now - (t if t.tzinfo else t.replace(tzinfo=UTC))).total_seconds() / 60
    return f"{mins:.0f}m ago" if mins < 90 else f"{mins / 60:.0f}h ago"


def read(research: dict[str, Any] | None, moves: list[dict[str, Any]] | None = None,
         now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    facts: list[str] = []
    score = 0
    if not research:
        facts.append("no Research Engine read for this commodity yet")
    else:
        sc = float(research.get("score") or 0)
        d = research.get("direction")
        if d and sc >= MIN_DIRECTION_SCORE:
            score = 1 if d == "BULLISH" else -1
            facts.append(f"research {d.lower()} (score {sc:.0f}, {research.get('newsStatus')})")
        else:
            facts.append(f"research has no clear direction (score {sc:.0f}, {research.get('newsStatus') or 'n/a'})")
        for h in (research.get("headlines") or [])[:3]:
            facts.append(f"\"{h.get('title', '')[:110]}\" {_age(h.get('publishedAt'), now)}".strip())
    for m in (moves or [])[:2]:
        facts.append(f"sudden {m.get('direction', '').lower()} move {m.get('movePct', 0):+.2f}% at "
                     f"{m.get('at', '')}: {m.get('summary') or 'news check pending'}")
    stance = "BULLISH" if score > 0 else "BEARISH" if score < 0 else "NEUTRAL"
    return {"agent": "news", "name": "News & research", "stance": stance, "score": score, "summary": facts[0],
            "facts": facts, "data": {"research": research, "moves": moves or []}}
