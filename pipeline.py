#!/usr/bin/env python3
"""
SignalScout Pipeline — orchestrates source fetching, scoring, deduplication, and output.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from sources import hackernews, reddit
from scorer import score_signals


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def deduplicate(signals: list[dict]) -> list[dict]:
    """Remove duplicate signals by normalized title similarity."""
    seen = {}
    deduped = []
    for s in signals:
        key = _normalize(s.get("title", ""))
        if key and key in seen:
            # Keep the higher-scored one
            if s.get("score", 0) > seen[key].get("score", 0):
                deduped = [x for x in deduped if x["id"] != seen[key]["id"]]
                deduped.append(s)
                seen[key] = s
        else:
            if key:
                seen[key] = s
            deduped.append(s)
    return deduped


def _normalize(text: str) -> str:
    import re
    return re.sub(r'[^a-z0-9 ]', '', text.lower()).strip()


def write_leads_json(leads: list[dict], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(), "count": len(leads), "leads": leads}, f, indent=2, default=str)
    print(f"  [Output] Wrote {len(leads)} leads to {path}")


def write_report(leads: list[dict], config: dict, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# 🔍 SignalScout Report",
        f"**Generated:** {now}",
        f"**ICP:** {config['icp']['description']}",
        f"**Total Leads Found:** {len(leads)}",
        "",
        "---",
        "",
    ]

    # Summary by source
    source_counts = {}
    for l in leads:
        src = l.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
    lines.append("## 📊 Summary")
    for src, count in sorted(source_counts.items()):
        lines.append(f"- **{src.title()}:** {count} signals")
    lines.append("")

    # Top leads
    top = leads[:20]
    if top:
        lines.append("## 🏆 Top Leads")
        lines.append("")
        for i, lead in enumerate(top, 1):
            score = lead.get("score", 0)
            emoji = "🔥" if score >= 7 else "⭐" if score >= 5 else "📌"
            title = lead.get("title", "Untitled")[:80]
            url = lead.get("url", "#")
            source = lead.get("source", "unknown")
            author = lead.get("author", "unknown")

            lines.append(f"### {i}. {emoji} [{title}]({url})")
            lines.append(f"**Score:** {score}/10 | **Source:** {source} | **Author:** {author}")
            bd = lead.get("score_breakdown", {})
            if bd:
                lines.append(f"*Keyword: {bd.get('keyword',0)} | Pain: {bd.get('pain_point',0)} | Recency: {bd.get('recency',0)} | Engagement: {bd.get('engagement',0)}*")
            content_preview = lead.get("content", "")[:200].replace("\n", " ")
            if content_preview:
                lines.append(f"> {content_preview}")
            lines.append("")

    # All leads table
    if len(leads) > 20:
        lines.append("## 📋 All Leads")
        lines.append("")
        lines.append("| # | Score | Source | Title |")
        lines.append("|---|-------|--------|-------|")
        for i, lead in enumerate(leads, 1):
            title = lead.get("title", "Untitled")[:60]
            lines.append(f"| {i} | {lead.get('score',0)} | {lead.get('source','')} | {title} |")
        lines.append("")

    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"  [Output] Wrote report to {path}")


def main():
    print("=" * 60)
    print("🔍 SignalScout Pipeline")
    print("=" * 60)

    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    config = load_config(config_path)
    print(f"\n📋 ICP: {config['icp']['description']}")
    print(f"📋 Keywords: {', '.join(config['icp']['keywords'][:5])}...")

    # Fetch signals from all sources
    print("\n🔌 Fetching signals...")
    all_signals = []

    if config["sources"].get("hackernews", {}).get("enabled"):
        print("  → Hacker News")
        all_signals.extend(hackernews.fetch_signals(config))

    if config["sources"].get("reddit", {}).get("enabled"):
        print("  → Reddit")
        all_signals.extend(reddit.fetch_signals(config))

    print(f"\n📥 Total raw signals: {len(all_signals)}")

    if not all_signals:
        print("⚠️  No signals found. Check your config or network connection.")
        # Still write empty output
        write_leads_json([], config["output"]["leads_file"])
        write_report([], config, config["output"]["report_file"])
        return

    # Score
    print("\n🎯 Scoring signals...")
    scored = score_signals(all_signals, config)

    # Filter by min score
    min_score = config["scoring"].get("min_score", 3)
    filtered = [s for s in scored if s["score"] >= min_score]
    print(f"  Filtered: {len(filtered)} signals above min score {min_score}")

    # Deduplicate
    print("\n🔄 Deduplicating...")
    deduped = deduplicate(filtered)
    print(f"  After dedup: {len(deduped)} unique leads")

    # Limit
    max_leads = config["output"].get("max_leads", 50)
    final = deduped[:max_leads]

    # Output
    print("\n💾 Writing output...")
    write_leads_json(final, config["output"]["leads_file"])
    write_report(final, config, config["output"]["report_file"])

    print(f"\n✅ Done! {len(final)} leads generated.")
    print(f"   → {config['output']['leads_file']}")
    print(f"   → {config['output']['report_file']}")


if __name__ == "__main__":
    main()
