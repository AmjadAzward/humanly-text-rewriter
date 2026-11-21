import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("DATABASE_PATH", "rewriter.db"))

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rewrites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_text TEXT NOT NULL,
                rewritten_text TEXT NOT NULL,
                tone TEXT NOT NULL,
                strength TEXT NOT NULL,
                previous_text TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
