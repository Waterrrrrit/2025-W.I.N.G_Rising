# init_db.py
import sqlite3

def init_db():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()

    # 1) users 테이블 (기존 그대로)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            password_hash BLOB NOT NULL,
            name TEXT NOT NULL,
            phone TEXT,
            org TEXT,
            created_at TEXT NOT NULL
        );
    """)

    # 2) umbrellas 테이블 (우산 대여/반납 기록)
    #   - user_id : 어떤 회원이
    #   - status  : 'RENTED' / 'RETURNED'
    #   - rented_at / returned_at : 시각 기록
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

    conn.commit()
    conn.close()
    print("✅ users.db / users, umbrellas 테이블이 준비되었습니다.")

if __name__ == "__main__":
    init_db()
