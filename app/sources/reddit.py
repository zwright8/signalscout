"""
Reddit signal source.
Uses public JSON endpoints — no API key required.
Appends .json to Reddit URLs for public access.
"""

import requests
import time

REDDIT_BASE = "https://www.reddit.com"
HEADERS = {"User-Agent": "SignalScout/1.0 (B2B Lead Detection Tool)"}


def fetch_signals(config: dict) -> list[dict]:
    """Fetch Reddit posts matching ICP from configured subreddits."""
    reddit_config = config["sources"]["reddit"]
    if not reddit_config.get("enabled", True):
        return []

    subreddits = reddit_config.get("subreddits", [])
    search_queries = reddit_config.get("search_queries", config["icp"]["keywords"][:3])
    max_posts = reddit_config.get("max_posts_per_sub", 25)

    signals = []
    seen_ids = set()

    for sub in subreddits:
        for query in search_queries:
            try:
                url = f"{REDDIT_BASE}/r/{sub}/search.json"
                resp = requests.get(url, params={
                    "q": query,
                    "restrict_sr": "on",
                    "sort": "new",
                    "t": "week",
                    "limit": min(max_posts, 25),
                }, headers=HEADERS, timeout=15)
                resp.raise_for_status()
                posts = resp.json().get("data", {}).get("children", [])
            except Exception as e:
                print(f"  [Reddit] Error on r/{sub} '{query}': {e}")
                time.sleep(2)
                continue

            for post in posts:
                data = post.get("data", {})
                post_id = data.get("id", "")
                if post_id in seen_ids:
                    continue
                seen_ids.add(post_id)

                title = data.get("title", "")
                selftext = data.get("selftext", "")
                content = f"{title} {selftext}".strip()

                signals.append({
                    "source": "reddit",
                    "id": f"reddit-{post_id}",
                    "title": title,
                    "content": content,
                    "url": f"https://reddit.com{data.get('permalink', '')}",
                    "subreddit": data.get("subreddit", sub),
                    "author": data.get("author", ""),
                    "created_at": _ts_to_iso(data.get("created_utc", 0)),
                    "points": data.get("score", 0),
                    "num_comments": data.get("num_comments", 0),
                })

            # Be polite to Reddit
            time.sleep(1)

    print(f"  [Reddit] Fetched {len(signals)} signals")
    return signals


def _ts_to_iso(ts):
    if not ts:
        return ""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
