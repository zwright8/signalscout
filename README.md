# 🔍 SignalScout

**AI-powered B2B lead detection.** Monitors public signals to find companies likely to buy your product RIGHT NOW.

## What It Does

SignalScout scans free, public data sources for buying intent signals — people asking for recommendations, complaining about existing tools, or discussing pain points that match your Ideal Customer Profile (ICP).

**Current Sources (no API keys needed):**
- 🟠 **Hacker News** — HN Search API (Algolia)
- 🔴 **Reddit** — Public JSON endpoints

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Edit your ICP config
nano config.yaml

# 3. Run the pipeline
python pipeline.py

# 4. Check your leads
cat output/report.md
```

## Configuration

Edit `config.yaml` to define your Ideal Customer Profile:

```yaml
icp:
  description: "AI tools for small business"
  keywords:
    - "AI tools"
    - "small business"
    - "looking for a tool"
  pain_points:
    - "too expensive"
    - "hard to use"
```

## Output

- **`output/leads.json`** — Machine-readable leads with scores and metadata
- **`output/report.md`** — Human-readable report with top leads, score breakdowns

## Scoring

Each signal is scored 1-10 based on:
| Factor | Weight | What It Measures |
|--------|--------|-----------------|
| Keyword Match | 40% | How many ICP keywords appear |
| Pain Points | 20% | Mentions of frustrations/needs |
| Recency | 20% | How recent the signal is |
| Engagement | 20% | Upvotes + comments |

## Project Structure

```
signalscout/
├── config.yaml          # Your ICP definition
├── pipeline.py          # Main orchestrator
├── scorer.py            # Heuristic scoring engine
├── sources/
│   ├── hackernews.py    # Hacker News source
│   └── reddit.py        # Reddit source
├── output/
│   ├── leads.json       # Raw scored leads
│   └── report.md        # Pretty report
├── requirements.txt
└── README.md
```

## Roadmap

- [ ] Twitter/X source
- [ ] GitHub source
- [ ] Job board source
- [ ] AI-powered scoring (GPT/Claude)
- [ ] Web dashboard
- [ ] Email digest
- [ ] CRM integrations

## Screenshots

*Coming soon — after v1.0 launch*

---

Built by **Apex Corp** 🏢
