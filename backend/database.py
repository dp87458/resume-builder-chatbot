import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "sessions.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            messages TEXT NOT NULL,
            resume_data TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_session(session_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT messages, resume_data FROM sessions WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "messages": json.loads(row[0]),
        "resume_data": json.loads(row[1]) if row[1] else {}
    }

def save_session(session_id, messages, resume_data=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sessions (session_id, messages, resume_data)
        VALUES (?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            messages = excluded.messages,
            resume_data = excluded.resume_data
    """, (
        session_id,
        json.dumps(messages),
        json.dumps(resume_data) if resume_data else None
    ))
    conn.commit()
    conn.close()

def session_exists(session_id):
    return get_session(session_id) is not None