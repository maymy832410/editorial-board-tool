"""Railway Postgres database client — replaces Supabase."""

import json
import os
from datetime import datetime, timezone
from typing import Optional, Set, Dict, List

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool

from config import DATABASE_URL

_pool: Optional[pool.SimpleConnectionPool] = None


def _get_pool() -> pool.SimpleConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        dsn = DATABASE_URL
        if not dsn:
            raise RuntimeError("DATABASE_URL environment variable is not set")
        _pool = pool.SimpleConnectionPool(minconn=1, maxconn=10, dsn=dsn)
    return _pool


def _conn():
    return _get_pool().getconn()


def _put(conn):
    _get_pool().putconn(conn)


# ─── Schema bootstrap ───────────────────────────────────────────────

def init_db():
    """Create tables if they don't exist (called once on app start)."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sent_invitations (
                    id SERIAL PRIMARY KEY,
                    orcid_id TEXT UNIQUE NOT NULL,
                    author_name TEXT,
                    email TEXT,
                    publisher TEXT,
                    sent_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS bounced_emails (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    bounce_category TEXT,
                    bounce_info TEXT,
                    bounced_at TIMESTAMPTZ
                );
                CREATE TABLE IF NOT EXISTS saved_configs (
                    id SERIAL PRIMARY KEY,
                    config_name TEXT NOT NULL,
                    config_type TEXT NOT NULL,
                    config_data JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS cached_results (
                    id SERIAL PRIMARY KEY,
                    session_key TEXT NOT NULL DEFAULT 'default',
                    authors JSONB NOT NULL DEFAULT '[]',
                    search_params JSONB,
                    resume_state JSONB,
                    total_count INTEGER DEFAULT 0,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_cached_results_key
                    ON cached_results (session_key);
            """)
        conn.commit()
    finally:
        _put(conn)


# ─── Sent invitations ───────────────────────────────────────────────

def mark_sent(orcid_id: str, author_name: str = "", email: str = "", publisher: str = "") -> bool:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO sent_invitations (orcid_id, author_name, email, publisher, sent_at)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (orcid_id) DO UPDATE
                   SET author_name=EXCLUDED.author_name, email=EXCLUDED.email,
                       publisher=EXCLUDED.publisher, sent_at=EXCLUDED.sent_at""",
                (orcid_id, author_name, email, publisher, datetime.now(timezone.utc)),
            )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"mark_sent error: {e}")
        return False
    finally:
        _put(conn)


def is_sent(orcid_id: str) -> bool:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM sent_invitations WHERE orcid_id=%s", (orcid_id,))
            return cur.fetchone() is not None
    finally:
        _put(conn)


def get_all_sent() -> Set[str]:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT orcid_id FROM sent_invitations")
            return {row[0] for row in cur.fetchall()}
    finally:
        _put(conn)


def get_sent_details(limit: int = 500, offset: int = 0) -> List[Dict]:
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM sent_invitations ORDER BY sent_at DESC LIMIT %s OFFSET %s",
                (limit, offset),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        _put(conn)


def get_sent_count() -> int:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM sent_invitations")
            return cur.fetchone()[0]
    finally:
        _put(conn)


def import_sent_csv(rows: list[dict]) -> int:
    """Bulk-import rows (dicts with orcid_id, author_name, email, publisher, sent_at)."""
    conn = _conn()
    imported = 0
    try:
        with conn.cursor() as cur:
            for r in rows:
                try:
                    cur.execute(
                        """INSERT INTO sent_invitations (orcid_id, author_name, email, publisher, sent_at)
                           VALUES (%s,%s,%s,%s,%s) ON CONFLICT (orcid_id) DO NOTHING""",
                        (r.get("orcid_id"), r.get("author_name"), r.get("email"),
                         r.get("publisher"), r.get("sent_at")),
                    )
                    imported += cur.rowcount
                except Exception:
                    conn.rollback()
                    conn = _conn()
                    continue
        conn.commit()
        return imported
    finally:
        _put(conn)


# ─── Bounced emails ─────────────────────────────────────────────────

def add_bounce(email: str, category: str = "", info: str = "", bounced_at: Optional[str] = None) -> bool:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO bounced_emails (email, bounce_category, bounce_info, bounced_at)
                   VALUES (%s,%s,%s,%s) ON CONFLICT (email) DO NOTHING""",
                (email.lower().strip(), category, info, bounced_at),
            )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"add_bounce error: {e}")
        return False
    finally:
        _put(conn)


def is_bounced(email: str) -> bool:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM bounced_emails WHERE email=%s", (email.lower().strip(),))
            return cur.fetchone() is not None
    finally:
        _put(conn)


def get_all_bounced() -> Set[str]:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT email FROM bounced_emails")
            return {row[0] for row in cur.fetchall()}
    finally:
        _put(conn)


def get_bounce_count() -> int:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM bounced_emails")
            return cur.fetchone()[0]
    finally:
        _put(conn)


def import_bounces(rows: list[dict]) -> int:
    """Bulk-import bounce rows (email, bounce_category, bounce_info, bounced_at)."""
    conn = _conn()
    imported = 0
    try:
        with conn.cursor() as cur:
            for r in rows:
                try:
                    cur.execute(
                        """INSERT INTO bounced_emails (email, bounce_category, bounce_info, bounced_at)
                           VALUES (%s,%s,%s,%s) ON CONFLICT (email) DO NOTHING""",
                        (r.get("email", "").lower().strip(), r.get("bounce_category", ""),
                         r.get("bounce_info", ""), r.get("bounced_at")),
                    )
                    imported += cur.rowcount
                except Exception:
                    conn.rollback()
                    conn = _conn()
                    continue
        conn.commit()
        return imported
    finally:
        _put(conn)


# ─── Saved configs (autosave) ───────────────────────────────────────

def save_config(name: str, config_type: str, data: dict) -> bool:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            # Upsert by name + type
            cur.execute(
                """INSERT INTO saved_configs (config_name, config_type, config_data, updated_at)
                   VALUES (%s,%s,%s, NOW())
                   ON CONFLICT ON CONSTRAINT saved_configs_name_type
                   DO UPDATE SET config_data=EXCLUDED.config_data, updated_at=NOW()""",
                (name, config_type, json.dumps(data)),
            )
        conn.commit()
        return True
    except psycopg2.errors.UndefinedObject:
        conn.rollback()
        # Constraint doesn't exist yet — create it and retry
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """ALTER TABLE saved_configs
                       ADD CONSTRAINT saved_configs_name_type UNIQUE (config_name, config_type)"""
                )
            conn.commit()
            return save_config(name, config_type, data)
        except Exception:
            conn.rollback()
            return False
    except Exception as e:
        conn.rollback()
        print(f"save_config error: {e}")
        return False
    finally:
        _put(conn)


def load_configs(config_type: str) -> List[Dict]:
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM saved_configs WHERE config_type=%s ORDER BY updated_at DESC",
                (config_type,),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        _put(conn)


def load_latest_config(config_type: str) -> Optional[Dict]:
    configs = load_configs(config_type)
    if configs:
        data = configs[0].get("config_data")
        if isinstance(data, str):
            return json.loads(data)
        return data
    return None


def delete_config(config_id: int) -> bool:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM saved_configs WHERE id=%s", (config_id,))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        _put(conn)


# ─── DB status ──────────────────────────────────────────────────────

def check_connection() -> Dict:
    """Return DB status dict for UI display."""
    if not DATABASE_URL:
        return {"available": False, "error": "DATABASE_URL not set"}
    try:
        conn = _conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        _put(conn)
        return {"available": True, "error": ""}
    except Exception as e:
        return {"available": False, "error": str(e)[:100]}


# ─── Cached search results ──────────────────────────────────────────

def save_cached_results(
    authors: list,
    search_params: Optional[dict] = None,
    resume_state: Optional[dict] = None,
    total_count: int = 0,
    session_key: str = "default",
) -> bool:
    """Persist current search results to DB so they survive page navigation / browser close."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO cached_results (session_key, authors, search_params, resume_state, total_count, updated_at)
                   VALUES (%s, %s, %s, %s, %s, NOW())
                   ON CONFLICT (session_key)
                   DO UPDATE SET authors=EXCLUDED.authors, search_params=EXCLUDED.search_params,
                                 resume_state=EXCLUDED.resume_state, total_count=EXCLUDED.total_count,
                                 updated_at=NOW()""",
                (session_key, json.dumps(authors), json.dumps(search_params),
                 json.dumps(resume_state), total_count),
            )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"save_cached_results error: {e}")
        return False
    finally:
        _put(conn)


def load_cached_results(session_key: str = "default") -> Optional[Dict]:
    """Load persisted search results."""
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT authors, search_params, resume_state, total_count FROM cached_results WHERE session_key=%s",
                (session_key,),
            )
            row = cur.fetchone()
            if row:
                result = dict(row)
                # Parse JSON strings if needed
                for key in ("authors", "search_params", "resume_state"):
                    if isinstance(result.get(key), str):
                        result[key] = json.loads(result[key])
                return result
        return None
    finally:
        _put(conn)
