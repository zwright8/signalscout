"""
Signal scorer — heuristic-based, no paid API calls.
Rates each signal 1-10 based on keyword match, pain points, recency, and engagement.
"""

import re
from datetime import datetime, timezone


def score_signals(signals: list[dict], config: dict) -> list[dict]:
    """Score each signal and return sorted list with scores."""
    keywords = [k.lower() for k in config["icp"]["keywords"]]
    pain_points = [p.lower() for p in config["icp"].get("pain_points", [])]
    weights = config["scoring"]["weights"]

    scored = []
    for signal in signals:
        content = signal.get("content", "").lower()
        title = signal.get("title", "").lower()
        text = f"{title} {content}"

        # 1. Keyword match score (0-10)
        kw_hits = sum(1 for kw in keywords if kw in text)
        kw_score = min(10, (kw_hits / max(len(keywords) * 0.3, 1)) * 10)

        # 2. Pain point score (0-10)
        pp_hits = sum(1 for pp in pain_points if pp in text)
        pp_score = min(10, (pp_hits / max(len(pain_points) * 0.2, 1)) * 10)

        # 3. Recency score (0-10) — newer = better
        recency_score = _recency_score(signal.get("created_at", ""))

        # 4. Engagement score (0-10)
        points = signal.get("points", 0)
        comments = signal.get("num_comments", 0)
        engagement = points + comments * 2
        eng_score = min(10, (engagement / 50) * 10)

        # Weighted total
        total = (
            kw_score * weights.get("keyword_match", 0.4) +
            pp_score * weights.get("pain_point_match", 0.2) +
            recency_score * weights.get("recency", 0.2) +
            eng_score * weights.get("engagement", 0.2)
        )
        final_score = round(min(10, max(1, total)), 1)

        signal["score"] = final_score
        signal["score_breakdown"] = {
            "keyword": round(kw_score, 1),
            "pain_point": round(pp_score, 1),
            "recency": round(recency_score, 1),
            "engagement": round(eng_score, 1),
        }
        scored.append(signal)

    scored.sort(key=lambda x: x["score"], reverse=True)
    print(f"  [Scorer] Scored {len(scored)} signals")
    return scored


def _recency_score(created_at: str) -> float:
    """Score 0-10 based on how recent the signal is (last 7 days)."""
    if not created_at:
        return 5.0
    try:
        if isinstance(created_at, str):
            # Handle both ISO formats
            created_at = created_at.replace("Z", "+00:00")
            dt = datetime.fromisoformat(created_at)
        else:
            dt = datetime.fromtimestamp(created_at, tz=timezone.utc)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        if age_hours < 6:
            return 10.0
        elif age_hours < 24:
            return 8.0
        elif age_hours < 72:
            return 6.0
        elif age_hours < 168:
            return 4.0
        else:
            return 2.0
    except Exception:
        return 5.0
