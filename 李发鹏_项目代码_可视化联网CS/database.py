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
    # 旧版本把管理员保存在 users 表中。升级时只保留普通用户和他们的打卡记录。
    legacy = sqlite3.connect(path)
    try:
        table = legacy.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
        columns = [row[1] for row in legacy.execute('PRAGMA table_info(users)')] if table else []
        if 'role' in columns:
            legacy.execute('PRAGMA foreign_keys = OFF')
            legacy.executescript('''
            BEGIN;
            CREATE TABLE users_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL
            );
            INSERT INTO users_new(id,username,password_hash,salt)
                SELECT id,username,password_hash,salt FROM users WHERE role='user';
            CREATE TABLE records_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                place_id INTEGER NOT NULL REFERENCES places(id) ON DELETE RESTRICT,
                created_at TEXT NOT NULL,
                reflection TEXT NOT NULL
            );
            INSERT INTO records_new(id,user_id,place_id,created_at,reflection)
                SELECT r.id,r.user_id,r.place_id,r.created_at,r.reflection
                FROM records r JOIN users u ON u.id=r.user_id WHERE u.role='user';
            DROP TABLE records;
            DROP TABLE users;
            ALTER TABLE users_new RENAME TO users;
            ALTER TABLE records_new RENAME TO records;
            COMMIT;
            ''')
    finally:
        legacy.close()
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL
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
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            published_at TEXT NOT NULL,
            remark TEXT NOT NULL DEFAULT ''
        );
        ''')
