"""
Database module — SQLite met standaard SQL (PostgreSQL-ready)
"""
import sqlite3
import os

DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(__file__), '..', 'data', 'boekhouding.db'))

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def init_db():
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'schema.sql')
    conn = get_db()
    with open(schema_path, 'r') as f:
        conn.executescript(f.read())
    # Migraties voor bestaande databases
    try:
        conn.execute("ALTER TABLE grootboeken ADD COLUMN snelboeken INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except Exception:
        pass  # kolom bestaat al
    conn.close()

def query(sql, params=(), one=False):
    conn = get_db()
    try:
        cur = conn.execute(sql, params)
        rv = cur.fetchall()
        conn.commit()
        return (rv[0] if rv else None) if one else rv
    finally:
        conn.close()

def execute(sql, params=()):
    conn = get_db()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def execute_many(sql, params_list):
    conn = get_db()
    try:
        conn.executemany(sql, params_list)
        conn.commit()
    finally:
        conn.close()
