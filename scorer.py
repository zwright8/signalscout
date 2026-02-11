"""
Signal scorer — heuristic + AI-powered scoring via Claude.
"""

import json
import re
from datetime import datetime, timezone


def score_signals_heuristic(signals: list[dict], config: dict) -> list[dict]:
    """Score each signal using heuristic rules. Returns sorted list."""
    keywords = [k.lower() for k in config["icp"]["keywords"]]
    pain_points = [p.lower() for p in config["icp"].get("pain_points", [])]
    negative_keywords = [n.lower() for n in config.get("negative_keywords", [])]
    weights = config["scoring"]["weights"]

    scored = []
    for signal in signals:
        content = signal.get("content", "").lower()
        title = signal.get("title", "").lower()
        text = f"{title} {content}"

        # Check negative keywords — skip if matched
        if any(nk in text for nk in negative_keywords):
            continue

        kw_hits = sum(1 for kw in keywords if kw in text)
        kw_score = min(10, (kw_hits / max(len(keywords) * 0.3, 1)) * 10)

        pp_hits = sum(1 for pp in pain_points if pp in text)
        pp_score = min(10, (pp_hits / max(len(pain_points) * 0.2, 1)) * 10)

        recency_score = _recency_score(signal.get("created_at", ""))

        points = signal.get("points", 0)
        comments = signal.get("num_comments", 0)
        engagement = points + comments * 2
        eng_score = min(10, (engagement / 50) * 10)

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
    print(f"  [Scorer] Heuristic scored {len(scored)} signals")
    return scored


def score_signals_ai(signals: list[dict], config: dict) -> list[dict]:
    """AI-score signals using Claude. Falls back to heuristic if no API key."""
    scoring_config = config.get("scoring", {})
    api_key = scoring_config.get("ai_api_key", "")

    if not api_key:
        print("  [Scorer] No AI API key configured, using heuristic only")
        return signals

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        print(f"  [Scorer] Failed to init Anthropic client: {e}")
        return signals

    icp_desc = json.dumps({
        "description": config["icp"]["description"],
        "keywords": config["icp"]["keywords"],
        "pain_points": config["icp"].get("pain_points", []),
        "industries": config["icp"].get("industries", []),
    })

    max_ai = scoring_config.get("max_ai_per_run", 50)
    ai_threshold = scoring_config.get("ai_threshold", 4)
    ai_count = 0

    for signal in signals:
        if ai_count >= max_ai:
            break
        if signal.get("score", 0) < ai_threshold:
            continue

        title = signal.get("title", "")
        text = signal.get("content", "") or signal.get("text", "")
        if not title and not text:
            continue

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": f"""You are a B2B sales intelligence analyst. Given this social media post and the target ICP described below, rate the buying intent from 1-10 and classify as high_intent/medium_intent/low_intent/noise. Also suggest a brief, natural response the user could post to engage this prospect. Return JSON only.

ICP: {icp_desc}

Post Title: {title}
Post Content: {text[:1000]}

Return ONLY valid JSON with keys: score (int 1-10), category (string), reasoning (string, 1-2 sentences), suggested_response (string)"""
                }]
            )
            result_text = response.content[0].text.strip()
            # Extract JSON from response
            json_match = re.search(r'\{[^{}]+\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                signal["ai_score"] = result.get("score", signal.get("score"))
                signal["intent_category"] = result.get("category", "noise")
                signal["ai_reasoning"] = result.get("reasoning", "")
                signal["suggested_response"] = result.get("suggested_response", "")
                ai_count += 1
        except Exception as e:
            print(f"  [Scorer] AI scoring failed for '{title[:40]}': {e}")
            continue

    print(f"  [Scorer] AI scored {ai_count} signals")
    return signals


def score_signals(signals: list[dict], config: dict) -> list[dict]:
    """Main scoring entry point — applies heuristic, then optionally AI."""
    scored = score_signals_heuristic(signals, config)

    mode = config.get("scoring", {}).get("mode", "heuristic")
    if mode in ("ai", "hybrid"):
        scored = score_signals_ai(scored, config)
        # Re-sort by AI score if available, else heuristic
        scored.sort(key=lambda x: x.get("ai_score") or x.get("score", 0), reverse=True)

    # Assign intent categories for heuristic-only leads
    for s in scored:
        if not s.get("intent_category"):
            score = s.get("ai_score") or s.get("score", 0)
            if score >= 7:
                s["intent_category"] = "high_intent"
            elif score >= 5:
                s["intent_category"] = "medium_intent"
            elif score >= 3:
                s["intent_category"] = "low_intent"
            else:
                s["intent_category"] = "noise"

    return scored


def _recency_score(created_at: str) -> float:
    if not created_at:
        return 5.0
    try:
        if isinstance(created_at, str):
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
