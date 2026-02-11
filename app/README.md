# 🔍 SignalScout v2

**AI-powered B2B lead detection dashboard.** Monitors public signals to find companies likely to buy your product RIGHT NOW.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the dashboard
python3 app.py
# → Open http://localhost:8080
```

## Features

- **Multi-source scanning** — Hacker News, Reddit, Twitter/X
- **AI-powered scoring** — Claude analyzes buying intent, suggests responses
- **Heuristic fallback** — Works without an API key using keyword/pain-point matching
- **Real-time dashboard** — Dark-themed SPA with filtering, sorting, lead management
- **Lead pipeline** — Track leads from discovery → contacted → converted

## Architecture

- **Backend:** FastAPI (Python)
- **Frontend:** Tailwind CSS + Alpine.js (no build step)
- **Database:** SQLite
- **AI:** Anthropic Claude (optional, user provides API key)

## Configuration

Edit `config.yaml` to set your ICP, keywords, and scoring preferences. Or use the Settings panel in the dashboard.

### AI Scoring

To enable AI-powered intent classification:
1. Get an API key from [console.anthropic.com](https://console.anthropic.com)
2. Add it in Settings → AI Scoring → API Key
3. Set mode to "hybrid" or "ai"

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard |
| GET | `/api/leads` | List leads (filterable) |
| GET | `/api/leads/{id}` | Get single lead |
| PATCH | `/api/leads/{id}` | Update lead status/notes |
| POST | `/api/scan` | Trigger new scan |
| GET | `/api/scans` | List past scans |
| GET | `/api/scan/status` | Check if scan is running |
| GET | `/api/stats` | Dashboard statistics |
| GET | `/api/config` | Get configuration |
| PUT | `/api/config` | Update configuration |

## Project Structure

```
signalscout/
├── app.py              # FastAPI app
├── config.yaml         # ICP configuration
├── database.py         # SQLite schema + CRUD
├── scorer.py           # Heuristic + AI scoring
├── pipeline.py         # Scan orchestrator
├── sources/
│   ├── hackernews.py   # HN Algolia API
│   ├── reddit.py       # Reddit JSON API
│   └── twitter.py      # Twitter/Nitter
├── templates/
│   └── index.html      # Dashboard SPA
└── requirements.txt
```

---

Built by **Apex Corp** 🏢
