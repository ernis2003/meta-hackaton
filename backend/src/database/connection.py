import sqlite3
from contextlib import closing

from src.config import DATABASE_PATH


def connect():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # A request's sync dependency and endpoint may run on different pool threads.
    # Keep one connection per request; never share it across concurrent requests.
    db = sqlite3.connect(DATABASE_PATH, timeout=10, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    return db


def init_db():
    with closing(connect()) as db, db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                name TEXT NOT NULL,
                surname TEXT NOT NULL,
                organization TEXT NOT NULL DEFAULT '',
                hashed_password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user', 'admin')),
                is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        from src.database.migrations import migrate
        migrate(db)

def get_db():
    db = connect()
    try:
        yield db
    finally:
        db.close()
