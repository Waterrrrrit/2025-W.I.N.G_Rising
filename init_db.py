# init_db.py
import sqlite3

def get_conn():
    return sqlite3.connect("users.db")

def init_db():
    """users / umbrellas 테이블이 없으면 생성하고, created_at 컬럼이 없으면 추가"""
    conn = get_conn()
    cur = conn.cursor()

    # 1) users 테이블 생성 (없으면만)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            password_hash BLOB NOT NULL,
            name TEXT NOT NULL,
            phone TEXT,
            org TEXT,
            created_at TEXT
        );
    """)

    # 2) umbrellas 테이블 생성 (없으면만)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS umbrellas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            rented_at TEXT,
            returned_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    """)

    # 3) 기존 users 테이블에 created_at 컬럼이 없으면 추가
    cur.execute("PRAGMA table_info(users);")
    cols = [row[1] for row in cur.fetchall()]  # row[1] = column name
    if "created_at" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN created_at TEXT;")

    conn.commit()
    conn.close()
    print("DB 초기화/마이그레이션 완료")

if __name__ == "__main__":
    init_db()
