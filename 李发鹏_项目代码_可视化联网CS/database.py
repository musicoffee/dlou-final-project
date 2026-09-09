"""SQLite 建表与连接。数据库只由服务端访问。"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent / 'data' / 'learning.db'


@contextmanager
def connect(path=DEFAULT_DB):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(path=DEFAULT_DB):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user', 'admin'))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS only_one_admin ON users(role) WHERE role = 'admin';
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            published_at TEXT NOT NULL,
            remark TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS places (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            history TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            place_id INTEGER NOT NULL REFERENCES places(id) ON DELETE RESTRICT,
            created_at TEXT NOT NULL,
            reflection TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS records_user ON records(user_id);
        CREATE INDEX IF NOT EXISTS records_place ON records(place_id);
        ''')
