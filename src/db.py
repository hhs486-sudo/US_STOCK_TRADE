"""
데이터베이스 연결 및 캐시 유틸리티.

DATABASE_URL 환경변수가 있으면 PostgreSQL(운영),
없으면 SQLite(로컬 개발) 자동 선택.
"""
import json
import os
from datetime import datetime, timedelta

import config

# ── 드라이버 선택 ──────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_PG = bool(DATABASE_URL)

if USE_PG:
    import psycopg2
    import psycopg2.extras
    PH = "%s"   # PostgreSQL 플레이스홀더
else:
    import sqlite3
    PH = "?"    # SQLite 플레이스홀더


# ── 연결 ──────────────────────────────────────
def get_conn():
    if USE_PG:
        # PostgreSQL: RealDictCursor로 dict 형식 행 반환
        conn = psycopg2.connect(DATABASE_URL)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn
    else:
        # SQLite: 로컬 파일 DB
        os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


# ── 테이블 초기화 ──────────────────────────────
def init_db():
    conn = get_conn()
    try:
        cur = conn.cursor()
        if USE_PG:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id          SERIAL PRIMARY KEY,
                    ticker      TEXT NOT NULL UNIQUE,
                    name        TEXT,
                    asset_type  TEXT DEFAULT 'stock',
                    memo        TEXT DEFAULT '',
                    added_at    TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key         TEXT PRIMARY KEY,
                    data        TEXT NOT NULL,
                    updated_at  TIMESTAMP DEFAULT NOW()
                )
            """)
        else:
            cur.executescript("""
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
        conn.commit()
    finally:
        conn.close()


# ── 캐시 조회 ──────────────────────────────────
def cache_get(key: str, ttl_seconds: int) -> dict | None:
    """캐시에서 데이터 조회. TTL 초과 시 None 반환."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT data, updated_at FROM cache WHERE key = {PH}", (key,)
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    updated = row["updated_at"]
    # SQLite는 문자열 반환, PostgreSQL은 datetime 반환
    if isinstance(updated, str):
        updated = datetime.fromisoformat(updated)
    if datetime.utcnow() - updated.replace(tzinfo=None) > timedelta(seconds=ttl_seconds):
        return None

    return json.loads(row["data"])


# ── 캐시 저장 ──────────────────────────────────
def cache_set(key: str, data: dict):
    """캐시에 데이터 저장 (upsert)."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        serialized = json.dumps(data, ensure_ascii=False, default=str)
        if USE_PG:
            cur.execute(
                """INSERT INTO cache (key, data, updated_at)
                   VALUES (%s, %s, NOW())
                   ON CONFLICT (key) DO UPDATE SET
                       data = EXCLUDED.data,
                       updated_at = EXCLUDED.updated_at""",
                (key, serialized),
            )
        else:
            cur.execute(
                """INSERT INTO cache (key, data, updated_at)
                   VALUES (?, ?, datetime('now'))
                   ON CONFLICT(key) DO UPDATE SET
                       data = excluded.data,
                       updated_at = excluded.updated_at""",
                (key, serialized),
            )
        conn.commit()
    finally:
        conn.close()


# ── 캐시 원본 조회 (TTL 무시) ──────────────────
def cache_get_raw(key: str) -> dict | None:
    """TTL 무시하고 캐시 데이터 조회 (fallback용)."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT data FROM cache WHERE key = {PH}", (key,))
        row = cur.fetchone()
    finally:
        conn.close()
    return json.loads(row["data"]) if row else None
