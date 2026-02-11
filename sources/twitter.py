"""
Twitter/X signal source.
Uses Nitter-based public search as a fallback since Twitter API requires paid access.
Falls back gracefully if unavailable.
"""

import requests
import time
import re
from datetime import datetime, timezone


NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SignalScout/2.0)"}


def fetch_signals(config: dict) -> list[dict]:
    """Attempt to fetch Twitter signals via public endpoints."""
    twitter_config = config.get("sources", {}).get("twitter", {})
    if not twitter_config.get("enabled", False):
        return []

    keywords = config["icp"]["keywords"][:4]
    signals = []
    seen_ids = set()

    for query in keywords:
        for instance in NITTER_INSTANCES:
            try:
                url = f"{instance}/search"
                resp = requests.get(url, params={"f": "tweets", "q": query},
                                    headers=HEADERS, timeout=10)
                if resp.status_code != 200:
                    continue

                # Parse basic tweet data from HTML
                tweets = _parse_nitter_html(resp.text, instance)
                for tweet in tweets:
                    tid = tweet.get("id", "")
                    if tid in seen_ids:
                        continue
                    seen_ids.add(tid)
                    signals.append(tweet)
                break  # Success with this instance
            except Exception as e:
                print(f"  [Twitter] Error with {instance}: {e}")
                continue
        time.sleep(1)

    print(f"  [Twitter] Fetched {len(signals)} signals")
    return signals


def _parse_nitter_html(html: str, instance: str) -> list[dict]:
    """Basic HTML parsing for Nitter search results."""
    tweets = []
    # Find tweet containers
    tweet_blocks = re.findall(
        r'<div class="timeline-item[^"]*">(.*?)</div>\s*</div>\s*</div>',
        html, re.DOTALL
    )

    for block in tweet_blocks[:20]:
        try:
            # Extract username
            username_match = re.search(r'class="username"[^>]*>@?([^<]+)</a>', block)
            username = username_match.group(1).strip() if username_match else ""

            # Extract tweet text
            text_match = re.search(r'class="tweet-content[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
            text = re.sub(r'<[^>]+>', '', text_match.group(1)).strip() if text_match else ""

            # Extract link
            link_match = re.search(r'class="tweet-link"[^>]*href="([^"]+)"', block)
            path = link_match.group(1) if link_match else ""

            if not text:
                continue

            tweet_id = re.search(r'/status/(\d+)', path)
            tid = f"twitter-{tweet_id.group(1)}" if tweet_id else f"twitter-{hash(text)}"

            tweets.append({
                "source": "twitter",
                "id": tid,
                "title": text[:120],
                "content": text,
                "url": f"https://twitter.com{path}" if path else "",
                "author": username,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "points": 0,
                "num_comments": 0,
            })
        except Exception:
            continue

    return tweets
