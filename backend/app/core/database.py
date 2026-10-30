"""
PostgreSQL via Neon — stores conversation history per session.

Table: conversations
  id          UUID  PK
  session_id  TEXT  (user/browser session identifier)
  tenant      TEXT  (which policy namespace)
  role        TEXT  ('user' | 'assistant')
  content     TEXT
  created_at  TIMESTAMPTZ
"""

import uuid
import logging
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

from .config import settings

_conn = None
logger = logging.getLogger(__name__)


def get_conn():
    global _conn
    if _conn is None or _conn.closed:
        logger.info("Opening PostgreSQL connection for PolicyPal")
        _conn = psycopg2.connect(settings.database_url, cursor_factory=RealDictCursor)
        _conn.autocommit = True
    return _conn


def init_db():
    """Create table if it doesn't exist."""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id  TEXT NOT NULL,
                tenant      TEXT NOT NULL DEFAULT 'default',
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id, created_at);
        """)
    logger.info("PolicyPal conversation table is ready")


def append_message(session_id: str, tenant: str, role: str, content: str) -> str:
    conn = get_conn()
    with conn.cursor() as cur:
        msg_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO conversations(id, session_id, tenant, role, content) VALUES(%s,%s,%s,%s,%s)",
            (msg_id, session_id, tenant, role, content),
        )
    logger.info("Stored %s message for tenant '%s' session '%s'", role, tenant, session_id)
    return msg_id


def get_history(session_id: str, tenant: str, limit: int = 10) -> list[dict]:
    """Return the most recent `limit` messages for a session."""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT role, content FROM conversations
            WHERE session_id=%s AND tenant=%s
            ORDER BY created_at DESC LIMIT %s
            """,
            (session_id, tenant, limit),
        )
        rows = cur.fetchall()
    return list(reversed([dict(r) for r in rows]))  # chronological order


def clear_history(session_id: str, tenant: str) -> int:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM conversations WHERE session_id=%s AND tenant=%s",
            (session_id, tenant),
        )
        deleted = cur.rowcount
    logger.info("Deleted %d messages for tenant '%s' session '%s'", deleted, tenant, session_id)
    return deleted
