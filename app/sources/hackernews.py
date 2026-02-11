"""
Hacker News signal source.
Uses the free Algolia HN Search API — no API key required.
"""

import requests
import time
from datetime import datetime, timezone


HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
HN_ITEM_URL = "https://news.ycombinator.com/item?id="


def fetch_signals(config: dict) -> list[dict]:
    """Fetch HN posts/comments matching ICP keywords."""
    hn_config = config["sources"]["hackernews"]
    if not hn_config.get("enabled", True):
        return []

    keywords = config["icp"]["keywords"]
    search_queries = hn_config.get("search_queries", keywords[:4])
    max_stories = hn_config.get("max_stories", 100)

    signals = []
    seen_ids = set()

    for query in search_queries:
        try:
            resp = requests.get(HN_SEARCH_URL, params={
                "query": query,
                "tags": "(story,show_hn,ask_hn)",
                "hitsPerPage": min(max_stories // len(search_queries), 50),
                "numericFilters": f"created_at_i>{int(time.time()) - 7*86400}",  # last 7 days
            }, timeout=15)
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
        except Exception as e:
            print(f"  [HN] Error searching '{query}': {e}")
            continue

        for hit in hits:
            obj_id = hit.get("objectID", "")
            if obj_id in seen_ids:
                continue
            seen_ids.add(obj_id)

            title = hit.get("title") or ""
            text = hit.get("story_text") or hit.get("comment_text") or ""
            content = f"{title} {text}".strip()

            signals.append({
                "source": "hackernews",
                "id": f"hn-{obj_id}",
                "title": title,
                "content": content,
                "url": hit.get("url") or f"{HN_ITEM_URL}{obj_id}",
                "hn_url": f"{HN_ITEM_URL}{obj_id}",
                "author": hit.get("author", ""),
                "created_at": hit.get("created_at", ""),
                "points": hit.get("points", 0) or 0,
                "num_comments": hit.get("num_comments", 0) or 0,
            })

    print(f"  [HN] Fetched {len(signals)} signals")
    return signals
