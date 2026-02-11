"""
SignalScout Pipeline v2 — orchestrates source fetching, scoring, and database storage.
"""

import json
import os
import sys
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from sources import hackernews, reddit, twitter
from scorer import score_signals
import database as db


def load_config(path: str = None) -> dict:
    if path is None:
        path = str(Path(__file__).parent / "config.yaml")
    with open(path) as f:
        return yaml.safe_load(f)


def deduplicate(signals: list[dict]) -> list[dict]:
    seen = {}
    deduped = []
    for s in signals:
        key = _normalize(s.get("title", ""))
        if key and key in seen:
            if s.get("score", 0) > seen[key].get("score", 0):
                deduped = [x for x in deduped if x.get("id") != seen[key].get("id")]
                deduped.append(s)
                seen[key] = s
        else:
            if key:
                seen[key] = s
            deduped.append(s)
    return deduped


def _normalize(text: str) -> str:
    return re.sub(r'[^a-z0-9 ]', '', text.lower()).strip()


def run_scan(config: dict = None) -> dict:
    """Run a full scan pipeline. Returns scan summary."""
    if config is None:
        config = load_config()

    # Determine active sources
    sources_used = []
    if config["sources"].get("hackernews", {}).get("enabled"):
        sources_used.append("hackernews")
    if config["sources"].get("reddit", {}).get("enabled"):
        sources_used.append("reddit")
    if config.get("sources", {}).get("twitter", {}).get("enabled"):
        sources_used.append("twitter")

    scan_id = db.create_scan(sources_used)
    print(f"\n🔍 Scan #{scan_id} started — sources: {', '.join(sources_used)}")

    try:
        all_signals = []

        if "hackernews" in sources_used:
            print("  → Fetching Hacker News...")
            all_signals.extend(hackernews.fetch_signals(config))

        if "reddit" in sources_used:
            print("  → Fetching Reddit...")
            all_signals.extend(reddit.fetch_signals(config))

        if "twitter" in sources_used:
            print("  → Fetching Twitter...")
            all_signals.extend(twitter.fetch_signals(config))

        print(f"  📥 Total raw signals: {len(all_signals)}")

        if not all_signals:
            db.complete_scan(scan_id, 0, 0, "completed")
            return {"scan_id": scan_id, "total_signals": 0, "leads_found": 0, "status": "completed"}

        # Score
        print("  🎯 Scoring...")
        scored = score_signals(all_signals, config)

        # Filter
        min_score = config["scoring"].get("min_score", 3)
        filtered = [s for s in scored if s.get("score", 0) >= min_score]

        # Deduplicate
        deduped = deduplicate(filtered)
        max_leads = config.get("output", {}).get("max_leads", 50)
        final = deduped[:max_leads]

        # Store in DB
        leads_stored = 0
        for signal in final:
            try:
                db.upsert_lead({
                    "source": signal.get("source", ""),
                    "title": signal.get("title", ""),
                    "url": signal.get("url", ""),
                    "author": signal.get("author", ""),
                    "text": signal.get("content", ""),
                    "score": signal.get("score"),
                    "ai_score": signal.get("ai_score"),
                    "ai_reasoning": signal.get("ai_reasoning"),
                    "intent_category": signal.get("intent_category"),
                    "suggested_response": signal.get("suggested_response"),
                    "engagement_upvotes": signal.get("points", 0),
                    "engagement_comments": signal.get("num_comments", 0),
                })
                leads_stored += 1
            except Exception as e:
                print(f"  ⚠️ Failed to store lead: {e}")

        db.complete_scan(scan_id, len(all_signals), leads_stored, "completed")
        print(f"  ✅ Scan #{scan_id} complete — {leads_stored} leads stored")

        return {"scan_id": scan_id, "total_signals": len(all_signals), "leads_found": leads_stored, "status": "completed"}

    except Exception as e:
        print(f"  ❌ Scan failed: {e}")
        db.complete_scan(scan_id, 0, 0, "failed")
        return {"scan_id": scan_id, "total_signals": 0, "leads_found": 0, "status": "failed", "error": str(e)}


def main():
    print("=" * 60)
    print("🔍 SignalScout Pipeline v2")
    print("=" * 60)

    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    config = load_config(config_path)
    print(f"📋 ICP: {config['icp']['description']}")

    result = run_scan(config)
    print(f"\n📊 Result: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    main()
