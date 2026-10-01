"""
database.py
-----------
Database setup and CRUD operations for expenses and incomes.
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
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras  # for RealDictCursor (access columns by name)
else:
    SQLITE_PATH = Path(__file__).parent.parent / "expenses.db"


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
    """Creates the users, expenses and incomes tables if they don't exist."""
    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id              SERIAL PRIMARY KEY,
                        username        TEXT UNIQUE NOT NULL,
                        hashed_password TEXT NOT NULL,
                        is_active       BOOLEAN NOT NULL DEFAULT TRUE
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS expenses (
                        id          SERIAL PRIMARY KEY,
                        user_id     INTEGER     REFERENCES users(id) ON DELETE CASCADE,
                        amount_uyu  REAL        NOT NULL,
                        amount_usd  REAL        NOT NULL,
                        dollar_rate REAL        NOT NULL,
                        category    TEXT        NOT NULL,
                        description TEXT,
                        date        TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                # Migrate tables created before expenses were scoped per user
                cur.execute("""
                    ALTER TABLE expenses ADD COLUMN IF NOT EXISTS
                        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_expenses_user_id"
                    " ON expenses (user_id)"
                )
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS incomes (
                        id          SERIAL PRIMARY KEY,
                        user_id     INTEGER     REFERENCES users(id) ON DELETE CASCADE,
                        amount_uyu  REAL        NOT NULL,
                        amount_usd  REAL        NOT NULL,
                        dollar_rate REAL        NOT NULL,
                        source      TEXT        NOT NULL,
                        description TEXT,
                        date        TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_incomes_user_id"
                    " ON incomes (user_id)"
                )
            conn.commit()
    else:
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    username        TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    is_active       INTEGER NOT NULL DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    amount_uyu  REAL NOT NULL,
                    amount_usd  REAL NOT NULL,
                    dollar_rate REAL NOT NULL,
                    category    TEXT NOT NULL,
                    description TEXT,
                    date        TEXT NOT NULL
                )
            """)
            # Migrate tables created before expenses were scoped per user
            columns = [r["name"] for r in conn.execute("PRAGMA table_info(expenses)")]
            if "user_id" not in columns:
                conn.execute(
                    "ALTER TABLE expenses ADD COLUMN"
                    " user_id INTEGER REFERENCES users(id) ON DELETE CASCADE"
                )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_expenses_user_id ON expenses (user_id)"
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS incomes (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    amount_uyu  REAL NOT NULL,
                    amount_usd  REAL NOT NULL,
                    dollar_rate REAL NOT NULL,
                    source      TEXT NOT NULL,
                    description TEXT,
                    date        TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_incomes_user_id ON incomes (user_id)"
            )
            conn.commit()


# ── Users ─────────────────────────────────────────────────────────────────────


def create_user(username: str, hashed_password: str) -> dict:
    p = _placeholder()
    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"INSERT INTO users (username, hashed_password)"
                    f" VALUES ({p}, {p})"
                    f" RETURNING id, username, is_active",
                    (username, hashed_password),
                )
                row = cur.fetchone()
            conn.commit()
        return dict(row)
    else:
        with get_connection() as conn:
            cursor = conn.execute(
                f"INSERT INTO users (username, hashed_password) VALUES ({p}, {p})",
                (username, hashed_password),
            )
            conn.commit()
            return get_user_by_id(cursor.lastrowid)


def get_user_by_username(username: str) -> dict | None:
    p = _placeholder()
    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"SELECT * FROM users WHERE username = {p}", (username,))
                row = cur.fetchone()
        return dict(row) if row else None
    else:
        with get_connection() as conn:
            row = conn.execute(
                f"SELECT * FROM users WHERE username = {p}", (username,)
            ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    p = _placeholder()
    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"SELECT * FROM users WHERE id = {p}", (user_id,))
                row = cur.fetchone()
        return dict(row) if row else None
    else:
        with get_connection() as conn:
            row = conn.execute(
                f"SELECT * FROM users WHERE id = {p}", (user_id,)
            ).fetchone()
        return dict(row) if row else None


# ── Expenses CRUD ─────────────────────────────────────────────────────────────


def create_expense(
    user_id: int,
    amount_uyu: float,
    amount_usd: float,
    dollar_rate: float,
    category: str,
    description: str | None = None,
    date: datetime | None = None,
) -> dict:
    date_val = date or datetime.now()
    p = _placeholder()

    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"""
                    INSERT INTO expenses (
                        user_id, amount_uyu, amount_usd, dollar_rate,
                        category, description, date
                    )
                    VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
                    RETURNING *
                    """,
                    (
                        user_id,
                        amount_uyu,
                        amount_usd,
                        dollar_rate,
                        category,
                        description,
                        date_val,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        return _serialize(dict(row))
    else:
        with get_connection() as conn:
            cursor = conn.execute(
                f"""
                INSERT INTO expenses (
                    user_id, amount_uyu, amount_usd, dollar_rate,
                    category, description, date
                )
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
                """,
                (
                    user_id,
                    amount_uyu,
                    amount_usd,
                    dollar_rate,
                    category,
                    description,
                    date_val.isoformat(),
                ),
            )
            conn.commit()
            return get_expense(cursor.lastrowid, user_id)


def get_expense(expense_id: int, user_id: int) -> dict | None:
    p = _placeholder()
    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"SELECT * FROM expenses WHERE id = {p} AND user_id = {p}",
                    (expense_id, user_id),
                )
                row = cur.fetchone()
        return _serialize(dict(row)) if row else None
    else:
        with get_connection() as conn:
            row = conn.execute(
                f"SELECT * FROM expenses WHERE id = {p} AND user_id = {p}",
                (expense_id, user_id),
            ).fetchone()
        return dict(row) if row else None


def list_expenses(user_id: int, month: str | None = None) -> list[dict]:
    """
    Lists a user's expenses, optionally filtered by month.

    Args:
        month: format 'YYYY-MM', e.g. '2026-05'
    """
    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if month:
                    cur.execute(
                        "SELECT * FROM expenses"
                        " WHERE user_id = %s AND to_char(date, 'YYYY-MM') = %s"
                        " ORDER BY date DESC",
                        (user_id, month),
                    )
                else:
                    cur.execute(
                        "SELECT * FROM expenses WHERE user_id = %s ORDER BY date DESC",
                        (user_id,),
                    )
                rows = cur.fetchall()
        return [_serialize(dict(r)) for r in rows]
    else:
        with get_connection() as conn:
            if month:
                rows = conn.execute(
                    "SELECT * FROM expenses"
                    " WHERE user_id = ? AND strftime('%Y-%m', date) = ?"
                    " ORDER BY date DESC",
                    (user_id, month),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC",
                    (user_id,),
                ).fetchall()
        return [dict(r) for r in rows]


def monthly_summary(user_id: int, month: str) -> dict:
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
                    WHERE user_id = %s AND to_char(date, 'YYYY-MM') = %s
                    GROUP BY to_char(date, 'YYYY-MM')
                    """,
                    (user_id, month),
                )
                row = cur.fetchone()
        _empty = {"month": month, "count": 0, "total_uyu": 0.0, "total_usd": 0.0}
        return dict(row) if row else _empty
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
                WHERE user_id = ? AND strftime('%Y-%m', date) = ?
                GROUP BY month
                """,
                (user_id, month),
            ).fetchone()
        _empty = {"month": month, "count": 0, "total_uyu": 0.0, "total_usd": 0.0}
        return dict(row) if row else _empty


def summary_by_category(user_id: int, month: str | None = None) -> list[dict]:
    """A user's totals grouped by category, optionally filtered by month."""
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
                        WHERE user_id = %s AND to_char(date, 'YYYY-MM') = %s
                        GROUP BY category ORDER BY total_uyu DESC
                        """,
                        (user_id, month),
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
                        WHERE user_id = %s
                        GROUP BY category ORDER BY total_uyu DESC
                        """,
                        (user_id,),
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
                    WHERE user_id = ? AND strftime('%Y-%m', date) = ?
                    GROUP BY category ORDER BY total_uyu DESC
                    """,
                    (user_id, month),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT
                        category,
                        COUNT(*)                  AS count,
                        ROUND(SUM(amount_uyu), 2) AS total_uyu,
                        ROUND(SUM(amount_usd), 2) AS total_usd
                    FROM expenses
                    WHERE user_id = ?
                    GROUP BY category ORDER BY total_uyu DESC
                    """,
                    (user_id,),
                ).fetchall()
        return [dict(r) for r in rows]


def delete_expense(expense_id: int, user_id: int) -> bool:
    p = _placeholder()
    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM expenses WHERE id = {p} AND user_id = {p}",
                    (expense_id, user_id),
                )
                deleted = cur.rowcount > 0
            conn.commit()
        return deleted
    else:
        with get_connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM expenses WHERE id = {p} AND user_id = {p}",
                (expense_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0


# ── Incomes CRUD ──────────────────────────────────────────────────────────────


def create_income(
    user_id: int,
    amount_uyu: float,
    amount_usd: float,
    dollar_rate: float,
    source: str,
    description: str | None = None,
    date: datetime | None = None,
) -> dict:
    date_val = date or datetime.now()
    p = _placeholder()

    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"""
                    INSERT INTO incomes (
                        user_id, amount_uyu, amount_usd, dollar_rate,
                        source, description, date
                    )
                    VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
                    RETURNING *
                    """,
                    (
                        user_id,
                        amount_uyu,
                        amount_usd,
                        dollar_rate,
                        source,
                        description,
                        date_val,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        return _serialize(dict(row))
    else:
        with get_connection() as conn:
            cursor = conn.execute(
                f"""
                INSERT INTO incomes (
                    user_id, amount_uyu, amount_usd, dollar_rate,
                    source, description, date
                )
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
                """,
                (
                    user_id,
                    amount_uyu,
                    amount_usd,
                    dollar_rate,
                    source,
                    description,
                    date_val.isoformat(),
                ),
            )
            conn.commit()
            return get_income(cursor.lastrowid, user_id)


def get_income(income_id: int, user_id: int) -> dict | None:
    p = _placeholder()
    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"SELECT * FROM incomes WHERE id = {p} AND user_id = {p}",
                    (income_id, user_id),
                )
                row = cur.fetchone()
        return _serialize(dict(row)) if row else None
    else:
        with get_connection() as conn:
            row = conn.execute(
                f"SELECT * FROM incomes WHERE id = {p} AND user_id = {p}",
                (income_id, user_id),
            ).fetchone()
        return dict(row) if row else None


def list_incomes(user_id: int, month: str | None = None) -> list[dict]:
    """
    Lists a user's incomes, optionally filtered by month.

    Args:
        month: format 'YYYY-MM', e.g. '2026-05'
    """
    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if month:
                    cur.execute(
                        "SELECT * FROM incomes"
                        " WHERE user_id = %s AND to_char(date, 'YYYY-MM') = %s"
                        " ORDER BY date DESC",
                        (user_id, month),
                    )
                else:
                    cur.execute(
                        "SELECT * FROM incomes WHERE user_id = %s ORDER BY date DESC",
                        (user_id,),
                    )
                rows = cur.fetchall()
        return [_serialize(dict(r)) for r in rows]
    else:
        with get_connection() as conn:
            if month:
                rows = conn.execute(
                    "SELECT * FROM incomes"
                    " WHERE user_id = ? AND strftime('%Y-%m', date) = ?"
                    " ORDER BY date DESC",
                    (user_id, month),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM incomes WHERE user_id = ? ORDER BY date DESC",
                    (user_id,),
                ).fetchall()
        return [dict(r) for r in rows]


def delete_income(income_id: int, user_id: int) -> bool:
    p = _placeholder()
    if USE_POSTGRES:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM incomes WHERE id = {p} AND user_id = {p}",
                    (income_id, user_id),
                )
                deleted = cur.rowcount > 0
            conn.commit()
        return deleted
    else:
        with get_connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM incomes WHERE id = {p} AND user_id = {p}",
                (income_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0


# ── Helpers ───────────────────────────────────────────────────────────────────


def _serialize(row: dict) -> dict:
    """Converts non-JSON-serializable types (e.g. datetime) to strings."""
    for key, val in row.items():
        if isinstance(val, datetime):
            row[key] = val.isoformat()
    return row
