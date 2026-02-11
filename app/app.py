"""
SignalScout v2 — FastAPI application serving API + dashboard.
"""

import json
import threading
from pathlib import Path
from typing import Optional

import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database as db
from pipeline import run_scan, load_config

app = FastAPI(title="SignalScout", version="2.0")

TEMPLATES_DIR = Path(__file__).parent / "templates"
CONFIG_PATH = Path(__file__).parent / "config.yaml"

# Track running scans
_scan_lock = threading.Lock()
_scan_running = False


# --- Dashboard ---

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html_path = TEMPLATES_DIR / "index.html"
    return HTMLResponse(html_path.read_text())


# --- Leads API ---

@app.get("/api/leads")
async def list_leads(
    status: Optional[str] = None,
    source: Optional[str] = None,
    min_score: Optional[float] = None,
    intent_category: Optional[str] = None,
    sort_by: str = "score",
    sort_order: str = "desc",
    limit: int = Query(100, le=500),
    offset: int = 0,
):
    leads = db.get_leads(
        status=status, source=source, min_score=min_score,
        intent_category=intent_category, sort_by=sort_by,
        sort_order=sort_order, limit=limit, offset=offset
    )
    return {"leads": leads, "count": len(leads)}


@app.get("/api/leads/{lead_id}")
async def get_lead(lead_id: int):
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return lead


class LeadUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


@app.patch("/api/leads/{lead_id}")
async def update_lead(lead_id: int, update: LeadUpdate):
    updates = {k: v for k, v in update.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No updates provided")
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    db.update_lead(lead_id, updates)
    return db.get_lead(lead_id)


# --- Scans API ---

@app.post("/api/scan")
async def trigger_scan():
    global _scan_running
    with _scan_lock:
        if _scan_running:
            return {"status": "already_running", "message": "A scan is already in progress"}
        _scan_running = True

    def _run():
        global _scan_running
        try:
            config = load_config()
            run_scan(config)
        finally:
            with _scan_lock:
                _scan_running = False

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "started", "message": "Scan started in background"}


@app.get("/api/scans")
async def list_scans():
    return {"scans": db.get_scans()}


@app.get("/api/scan/status")
async def scan_status():
    return {"running": _scan_running}


# --- Stats API ---

@app.get("/api/stats")
async def get_stats():
    return db.get_stats()


# --- Config API ---

@app.get("/api/config")
async def get_config():
    config = load_config()
    # Mask API key
    if config.get("scoring", {}).get("ai_api_key"):
        key = config["scoring"]["ai_api_key"]
        config["scoring"]["ai_api_key"] = key[:8] + "..." if len(key) > 8 else "***"
    return config


class ConfigUpdate(BaseModel):
    icp: Optional[dict] = None
    negative_keywords: Optional[list] = None
    scoring: Optional[dict] = None


@app.put("/api/config")
async def update_config(update: ConfigUpdate):
    config = load_config()
    if update.icp:
        config["icp"].update(update.icp)
    if update.negative_keywords is not None:
        config["negative_keywords"] = update.negative_keywords
    if update.scoring:
        # Preserve existing API key if new one is masked/empty
        new_key = update.scoring.get("ai_api_key", "")
        if not new_key or "..." in new_key:
            update.scoring["ai_api_key"] = config.get("scoring", {}).get("ai_api_key", "")
        config["scoring"].update(update.scoring)

    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    return {"status": "updated"}


if __name__ == "__main__":
    import uvicorn
    config = load_config()
    host = config.get("server", {}).get("host", "0.0.0.0")
    port = config.get("server", {}).get("port", 8080)
    print(f"🚀 SignalScout v2 starting on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
