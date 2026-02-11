"""
SignalScout Database — SQLite schema + CRUD operations.
"""

import sqlite3
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "signalscout.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            author TEXT,
            text TEXT,
            score REAL,
            ai_score REAL,
            ai_reasoning TEXT,
            intent_category TEXT,
            suggested_response TEXT,
            engagement_upvotes INTEGER DEFAULT 0,
            engagement_comments INTEGER DEFAULT 0,
            status TEXT DEFAULT 'new',
            notes TEXT,
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            contacted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            total_signals INTEGER DEFAULT 0,
            leads_found INTEGER DEFAULT 0,
            sources_used TEXT,
            status TEXT DEFAULT 'running'
        );

        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
        CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source);
        CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score DESC);
        CREATE INDEX IF NOT EXISTS idx_leads_intent ON leads(intent_category);
    """)
    conn.commit()
    conn.close()


# --- Lead CRUD ---

def upsert_lead(lead: dict) -> int:
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO leads (source, title, url, author, text, score, ai_score, ai_reasoning,
                             intent_category, suggested_response, engagement_upvotes, engagement_comments,
                             status, discovered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', CURRENT_TIMESTAMP)
            ON CONFLICT(url) DO UPDATE SET
                score = excluded.score,
                ai_score = excluded.ai_score,
                ai_reasoning = excluded.ai_reasoning,
                intent_category = excluded.intent_category,
                suggested_response = excluded.suggested_response,
                engagement_upvotes = excluded.engagement_upvotes,
                engagement_comments = excluded.engagement_comments
        """, (
            lead.get("source", ""),
            lead.get("title", ""),
            lead.get("url", ""),
            lead.get("author", ""),
            lead.get("text", ""),
            lead.get("score"),
            lead.get("ai_score"),
            lead.get("ai_reasoning"),
            lead.get("intent_category"),
            lead.get("suggested_response"),
            lead.get("engagement_upvotes", 0),
            lead.get("engagement_comments", 0),
        ))
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


def get_leads(status=None, source=None, min_score=None, intent_category=None,
              sort_by="score", sort_order="desc", limit=100, offset=0) -> list[dict]:
    conn = get_connection()
    query = "SELECT * FROM leads WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if source:
        query += " AND source = ?"
        params.append(source)
    if min_score is not None:
        query += " AND score >= ?"
        params.append(min_score)
    if intent_category:
        query += " AND intent_category = ?"
        params.append(intent_category)

    allowed_sorts = {"score", "ai_score", "discovered_at", "created_at", "engagement_upvotes", "title"}
    if sort_by not in allowed_sorts:
        sort_by = "score"
    order = "DESC" if sort_order.lower() == "desc" else "ASC"
    query += f" ORDER BY {sort_by} {order} NULLS LAST"
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_lead(lead_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_lead(lead_id: int, updates: dict) -> bool:
    conn = get_connection()
    allowed = {"status", "notes", "contacted_at"}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        conn.close()
        return False

    if fields.get("status") == "contacted" and "contacted_at" not in fields:
        fields["contacted_at"] = datetime.now(timezone.utc).isoformat()

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [lead_id]
    conn.execute(f"UPDATE leads SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return True


# --- Scan CRUD ---

def create_scan(sources_used: list[str]) -> int:
    conn = get_connection()
    conn.execute("INSERT INTO scans (sources_used, status) VALUES (?, 'running')",
                 (json.dumps(sources_used),))
    conn.commit()
    scan_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return scan_id


def complete_scan(scan_id: int, total_signals: int, leads_found: int, status: str = "completed"):
    conn = get_connection()
    conn.execute("""
        UPDATE scans SET completed_at = CURRENT_TIMESTAMP, total_signals = ?,
               leads_found = ?, status = ? WHERE id = ?
    """, (total_signals, leads_found, status, scan_id))
    conn.commit()
    conn.close()


def get_scans(limit: int = 20) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM scans ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Stats ---

def get_stats() -> dict:
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    today = conn.execute("SELECT COUNT(*) FROM leads WHERE date(discovered_at) = date('now')").fetchone()[0]
    by_status = {}
    for row in conn.execute("SELECT status, COUNT(*) as cnt FROM leads GROUP BY status").fetchall():
        by_status[row["status"]] = row["cnt"]
    by_source = {}
    for row in conn.execute("SELECT source, COUNT(*) as cnt FROM leads GROUP BY source").fetchall():
        by_source[row["source"]] = row["cnt"]
    avg_score = conn.execute("SELECT AVG(score) FROM leads").fetchone()[0] or 0
    by_intent = {}
    for row in conn.execute("SELECT intent_category, COUNT(*) as cnt FROM leads WHERE intent_category IS NOT NULL GROUP BY intent_category").fetchall():
        by_intent[row["intent_category"]] = row["cnt"]

    converted = by_status.get("converted", 0)
    contacted = by_status.get("contacted", 0) + by_status.get("replied", 0) + converted
    conversion_rate = (converted / contacted * 100) if contacted > 0 else 0

    conn.close()
    return {
        "total_leads": total,
        "new_today": today,
        "by_status": by_status,
        "by_source": by_source,
        "by_intent": by_intent,
        "avg_score": round(avg_score, 1),
        "conversion_rate": round(conversion_rate, 1),
    }


# --- Config ---

def get_config_value(key: str) -> str | None:
    conn = get_connection()
    row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def set_config_value(key: str, value: str):
    conn = get_connection()
    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


# Initialize on import
init_db()
