import json
import sqlite3
from datetime import datetime, timedelta

import config


def get_conn():
    import os
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker      TEXT NOT NULL UNIQUE,
                name        TEXT,
                asset_type  TEXT DEFAULT 'stock',
                memo        TEXT DEFAULT '',
                added_at    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS cache (
                key         TEXT PRIMARY KEY,
                data        TEXT NOT NULL,
                updated_at  TEXT DEFAULT (datetime('now'))
            );
        """)


def cache_get(key: str, ttl_seconds: int) -> dict | None:
    """캐시에서 데이터 조회. TTL 초과 시 None 반환."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT data, updated_at FROM cache WHERE key = ?", (key,)
        ).fetchone()

    if row is None:
        return None

    updated = datetime.fromisoformat(row["updated_at"])
    if datetime.utcnow() - updated > timedelta(seconds=ttl_seconds):
        return None

    return json.loads(row["data"])


def cache_set(key: str, data: dict):
    """캐시에 데이터 저장."""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO cache (key, data, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET
                   data = excluded.data,
                   updated_at = excluded.updated_at""",
            (key, json.dumps(data, ensure_ascii=False, default=str)),
        )


def cache_get_raw(key: str) -> dict | None:
    """TTL 무시하고 캐시 데이터 조회 (fallback용)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT data FROM cache WHERE key = ?", (key,)
        ).fetchone()
    return json.loads(row["data"]) if row else None
