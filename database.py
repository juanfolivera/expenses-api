"""
database.py
-----------
Database setup and CRUD operations for expenses.
Uses PostgreSQL in production (Railway) and SQLite locally for development.

The database URL is read from the DATABASE_URL environment variable.
If not set, it falls back to a local SQLite file (for local development).
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

# ── Connection strategy ───────────────────────────────────────────────────────
# Railway injects DATABASE_URL automatically when you add a PostgreSQL plugin.
# Locally, we fall back to SQLite so you don't need to install anything extra.

DATABASE_URL = os.getenv("DATABASE_URL")
USE_POSTGRES  = DATABASE_URL is not None

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras  # for RealDictCursor (access columns by name)
else:
    SQLITE_PATH = Path(__file__).parent / "expenses.db"


# ── Connection ────────────────────────────────────────────────────────────────

def get_connection():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def _placeholder(n: int = 1) -> str:
    """
    Returns the right placeholder for parameterized queries.
    PostgreSQL uses %s, SQLite uses ?.
    """
    return "%s" if USE_POSTGRES else "?"


def _row_to_dict(row) -> dict:
    """Converts a DB row to a plain dict regardless of the backend."""
    if USE_POSTGRES:
        return dict(row)
    return dict(row)


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db():
    """Creates the expenses table if it doesn't exist."""
    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS expenses (
                        id          SERIAL PRIMARY KEY,
                        amount_uyu  REAL        NOT NULL,
                        amount_usd  REAL        NOT NULL,
                        dollar_rate REAL        NOT NULL,
                        category    TEXT        NOT NULL,
                        description TEXT,
                        date        TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
            conn.commit()
    else:
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount_uyu  REAL NOT NULL,
                    amount_usd  REAL NOT NULL,
                    dollar_rate REAL NOT NULL,
                    category    TEXT NOT NULL,
                    description TEXT,
                    date        TEXT NOT NULL
                )
            """)
            conn.commit()


# ── CRUD ──────────────────────────────────────────────────────────────────────

def create_expense(
    amount_uyu:  float,
    amount_usd:  float,
    dollar_rate: float,
    category:    str,
    description: str | None = None,
    date:        datetime | None = None,
) -> dict:
    date_val = date or datetime.now()
    p = _placeholder()

    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"""
                    INSERT INTO expenses (amount_uyu, amount_usd, dollar_rate, category, description, date)
                    VALUES ({p}, {p}, {p}, {p}, {p}, {p})
                    RETURNING *
                    """,
                    (amount_uyu, amount_usd, dollar_rate, category, description, date_val),
                )
                row = cur.fetchone()
            conn.commit()
        return _serialize(dict(row))
    else:
        with get_connection() as conn:
            cursor = conn.execute(
                f"""
                INSERT INTO expenses (amount_uyu, amount_usd, dollar_rate, category, description, date)
                VALUES ({p}, {p}, {p}, {p}, {p}, {p})
                """,
                (amount_uyu, amount_usd, dollar_rate, category, description, date_val.isoformat()),
            )
            conn.commit()
            return get_expense(cursor.lastrowid)


def get_expense(expense_id: int) -> dict | None:
    p = _placeholder()
    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"SELECT * FROM expenses WHERE id = {p}", (expense_id,))
                row = cur.fetchone()
        return _serialize(dict(row)) if row else None
    else:
        with get_connection() as conn:
            row = conn.execute(f"SELECT * FROM expenses WHERE id = {p}", (expense_id,)).fetchone()
        return dict(row) if row else None


def list_expenses(month: str | None = None) -> list[dict]:
    """
    Lists all expenses, optionally filtered by month.

    Args:
        month: format 'YYYY-MM', e.g. '2026-05'
    """
    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if month:
                    cur.execute(
                        "SELECT * FROM expenses WHERE to_char(date, 'YYYY-MM') = %s ORDER BY date DESC",
                        (month,),
                    )
                else:
                    cur.execute("SELECT * FROM expenses ORDER BY date DESC")
                rows = cur.fetchall()
        return [_serialize(dict(r)) for r in rows]
    else:
        with get_connection() as conn:
            if month:
                rows = conn.execute(
                    "SELECT * FROM expenses WHERE strftime('%Y-%m', date) = ? ORDER BY date DESC",
                    (month,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM expenses ORDER BY date DESC").fetchall()
        return [dict(r) for r in rows]


def monthly_summary(month: str) -> dict:
    """Returns totals in UYU and USD for a given month (format 'YYYY-MM')."""
    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        to_char(date, 'YYYY-MM')  AS month,
                        COUNT(*)                   AS count,
                        ROUND(SUM(amount_uyu)::numeric, 2) AS total_uyu,
                        ROUND(SUM(amount_usd)::numeric, 2) AS total_usd
                    FROM expenses
                    WHERE to_char(date, 'YYYY-MM') = %s
                    GROUP BY to_char(date, 'YYYY-MM')
                    """,
                    (month,),
                )
                row = cur.fetchone()
        return dict(row) if row else {"month": month, "count": 0, "total_uyu": 0.0, "total_usd": 0.0}
    else:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    strftime('%Y-%m', date)   AS month,
                    COUNT(*)                  AS count,
                    ROUND(SUM(amount_uyu), 2) AS total_uyu,
                    ROUND(SUM(amount_usd), 2) AS total_usd
                FROM expenses
                WHERE strftime('%Y-%m', date) = ?
                GROUP BY month
                """,
                (month,),
            ).fetchone()
        return dict(row) if row else {"month": month, "count": 0, "total_uyu": 0.0, "total_usd": 0.0}


def summary_by_category(month: str | None = None) -> list[dict]:
    """Totals grouped by category, optionally filtered by month."""
    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if month:
                    cur.execute(
                        """
                        SELECT
                            category,
                            COUNT(*)                          AS count,
                            ROUND(SUM(amount_uyu)::numeric, 2) AS total_uyu,
                            ROUND(SUM(amount_usd)::numeric, 2) AS total_usd
                        FROM expenses
                        WHERE to_char(date, 'YYYY-MM') = %s
                        GROUP BY category ORDER BY total_uyu DESC
                        """,
                        (month,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT
                            category,
                            COUNT(*)                          AS count,
                            ROUND(SUM(amount_uyu)::numeric, 2) AS total_uyu,
                            ROUND(SUM(amount_usd)::numeric, 2) AS total_usd
                        FROM expenses
                        GROUP BY category ORDER BY total_uyu DESC
                        """
                    )
                rows = cur.fetchall()
        return [dict(r) for r in rows]
    else:
        with get_connection() as conn:
            if month:
                rows = conn.execute(
                    """
                    SELECT
                        category,
                        COUNT(*)                  AS count,
                        ROUND(SUM(amount_uyu), 2) AS total_uyu,
                        ROUND(SUM(amount_usd), 2) AS total_usd
                    FROM expenses
                    WHERE strftime('%Y-%m', date) = ?
                    GROUP BY category ORDER BY total_uyu DESC
                    """,
                    (month,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT
                        category,
                        COUNT(*)                  AS count,
                        ROUND(SUM(amount_uyu), 2) AS total_uyu,
                        ROUND(SUM(amount_usd)::numeric, 2) AS total_usd
                    FROM expenses
                    GROUP BY category ORDER BY total_uyu DESC
                    """
                ).fetchall()
        return [dict(r) for r in rows]


def delete_expense(expense_id: int) -> bool:
    p = _placeholder()
    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM expenses WHERE id = {p}", (expense_id,))
                deleted = cur.rowcount > 0
            conn.commit()
        return deleted
    else:
        with get_connection() as conn:
            cursor = conn.execute(f"DELETE FROM expenses WHERE id = {p}", (expense_id,))
            conn.commit()
            return cursor.rowcount > 0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _serialize(row: dict) -> dict:
    """Converts non-JSON-serializable types (e.g. datetime) to strings."""
    for key, val in row.items():
        if isinstance(val, datetime):
            row[key] = val.isoformat()
    return row
