"""SQLite storage for accounts, saved study sets, the generation cache and the daily-generation counter.

Standard library only. To move to Postgres later, only this file changes.
Set DATABASE_PATH to a persistent disk when deploying.
Timestamps use SQLite's CURRENT_TIMESTAMP (UTC, "YYYY-MM-DD HH:MM:SS"), which the frontend expects.
"""
import json
import os
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Optional

DB_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "learn_it.db"))
MAX_SETS_PER_USER = int(os.getenv("MAX_SETS_PER_USER", "200"))
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _open(isolation="DEFERRED"):
    con = sqlite3.connect(DB_PATH, timeout=10, isolation_level=isolation)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


@contextmanager
def connect():
    con = _open()
    try:
        with con:  # commit on success, roll back on error
            yield con
    finally:
        con.close()


def init_db():
    with connect() as con:
        con.execute("PRAGMA journal_mode = WAL")
        con.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        con.execute("CREATE TABLE IF NOT EXISTS study_sets (id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, filename TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_sets_user ON study_sets(user_id, created_at)")
        # same file + same options = reuse the stored result, zero AI tokens
        con.execute("CREATE TABLE IF NOT EXISTS generation_cache (key TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        # one row per AI call, used for the daily limit (removed again if the call fails)
        con.execute("CREATE TABLE IF NOT EXISTS generations (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, created_at REAL NOT NULL)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_gen_user ON generations(user_id, created_at)")


# ---- users ----
def create_user(email: str, password_hash: str) -> Optional[int]:
    """Returns the new user id, or None if the email is already registered. Other constraint errors are raised."""
    try:
        with connect() as con:
            return con.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, password_hash)).lastrowid
    except sqlite3.IntegrityError as exc:
        if "UNIQUE constraint failed: users.email" in str(exc):
            return None
        raise


def get_user_by_email(email: str):
    with connect() as con:
        row = con.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_user(user_id: int):
    with connect() as con:
        row = con.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


# ---- study sets ----
def _row_to_set(row):
    data = json.loads(row["payload"])
    data.update({"id": row["id"], "filename": row["filename"], "createdAt": row["created_at"]})
    return data


def list_sets(user_id: int):
    with connect() as con:
        rows = con.execute("SELECT * FROM study_sets WHERE user_id = ? ORDER BY created_at DESC, rowid DESC", (user_id,)).fetchall()
        return [_row_to_set(r) for r in rows]


def save_set(user_id: int, data: dict):
    """Create or update a set. A client id is kept if it is free or already this user's, never another user's."""
    payload = json.dumps({k: data[k] for k in ("flashcards", "quiz", "diagram")}, ensure_ascii=False)
    with connect() as con:
        wanted = data.get("id") if SAFE_ID.match(str(data.get("id") or "")) else None
        owner = con.execute("SELECT user_id FROM study_sets WHERE id = ?", (wanted,)).fetchone() if wanted else None
        if owner and owner["user_id"] == user_id:
            con.execute("UPDATE study_sets SET filename = ?, payload = ? WHERE id = ?", (data["filename"], payload, wanted))
            set_id = wanted
        else:
            count = con.execute("SELECT COUNT(*) FROM study_sets WHERE user_id = ?", (user_id,)).fetchone()[0]
            if count >= MAX_SETS_PER_USER:
                raise ValueError("You have reached the limit of saved sets. Remove one to save another.")
            set_id = wanted if wanted and not owner else uuid.uuid4().hex
            con.execute("INSERT INTO study_sets (id, user_id, filename, payload) VALUES (?, ?, ?, ?)", (set_id, user_id, data["filename"], payload))
        return _row_to_set(con.execute("SELECT * FROM study_sets WHERE id = ?", (set_id,)).fetchone())


def delete_set(user_id: int, set_id: str) -> bool:
    with connect() as con:
        return con.execute("DELETE FROM study_sets WHERE id = ? AND user_id = ?", (set_id, user_id)).rowcount > 0


# ---- cache ----
def cache_get(key: str):
    with connect() as con:
        row = con.execute("SELECT payload FROM generation_cache WHERE key = ?", (key,)).fetchone()
        return json.loads(row["payload"]) if row else None


def cache_put(key: str, pack: dict):
    with connect() as con:
        con.execute("INSERT OR REPLACE INTO generation_cache (key, payload) VALUES (?, ?)", (key, json.dumps(pack, ensure_ascii=False)))


# ---- daily limit ----
def reserve_generation(user_id: int, limit: int) -> Optional[int]:
    """Atomically count one new AI generation for this user. Returns its id, or None if the 24-hour limit is used up."""
    con = _open(isolation=None)  # manual transaction so the check and the insert cannot interleave
    try:
        con.execute("BEGIN IMMEDIATE")
        used = con.execute("SELECT COUNT(*) FROM generations WHERE user_id = ? AND created_at > ?", (user_id, time.time() - 86400)).fetchone()[0]
        if used >= limit:
            con.execute("ROLLBACK")
            return None
        gen_id = con.execute("INSERT INTO generations (user_id, created_at) VALUES (?, ?)", (user_id, time.time())).lastrowid
        con.execute("COMMIT")
        return gen_id
    finally:
        con.close()


def refund_generation(gen_id: int):
    with connect() as con:
        con.execute("DELETE FROM generations WHERE id = ?", (gen_id,))