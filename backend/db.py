"""Minimal DB helpers for PoC using psycopg2 (sync) to run migrations and simple queries.

This keeps dependencies tiny and is sufficient for the initial PoC. For production
you may want async DB access (asyncpg/sqlx) and prepared statements.
"""
import os
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

MIGRATION_PATH = os.path.join(os.path.dirname(__file__), "migrations", "001_init.sql")


def get_conn() -> psycopg2.extensions.connection:
    dsn = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/tomo")
    return psycopg2.connect(dsn)


def run_migrations() -> None:
    with open(MIGRATION_PATH, "r", encoding="utf-8") as fh:
        sql = fh.read()
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
    finally:
        conn.close()


def insert_memory(pet_id: Optional[str], content: str, embedding_literal: str, category: Optional[str] = None,
                  importance: int = 0) -> Dict[str, Any]:
    """Insert a memory and return the created row (id and created_at).

    embedding_literal must be a string like '[0.1,0.2,...]' matching vector dim.
    """
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO memories (pet_id, embedding, content, category, importance)
                    VALUES (%s, %s::vector, %s, %s, %s)
                    RETURNING id, created_at
                    """,
                    (pet_id, embedding_literal, content, category, importance),
                )
                row = cur.fetchone()
                return dict(row)
    finally:
        conn.close()


def search_memories(embedding_literal: str, pet_id: Optional[str] = None, k: int = 5) -> List[Dict[str, Any]]:
    """Search nearest memories by L2 distance using pgvector operator <->.

    Returns list of rows with fields: id, content, distance, created_at, category
    """
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if pet_id:
                    cur.execute(
                        """
                        SELECT id, content, category, importance, created_at,
                               (embedding <-> %s::vector) AS distance
                        FROM memories
                        WHERE pet_id = %s
                        ORDER BY embedding <-> %s::vector
                        LIMIT %s
                        """,
                        (embedding_literal, pet_id, embedding_literal, k),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, content, category, importance, created_at,
                               (embedding <-> %s::vector) AS distance
                        FROM memories
                        ORDER BY embedding <-> %s::vector
                        LIMIT %s
                        """,
                        (embedding_literal, embedding_literal, k),
                    )
                rows = cur.fetchall()
                return [dict(r) for r in rows]
    finally:
        conn.close()
