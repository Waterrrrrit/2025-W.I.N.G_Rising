# init_db.py
import sqlite3

def init_db():
    # 1) users.db라는 SQLite 파일에 연결 (없으면 자동 생성)
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()

    # 2) users 테이블 생성
    #   - user_id    : 로그인용 아이디
    #   - password_hash : 비밀번호 해시 (bcrypt로 저장할 예정)
    #   - name       : 이름
    #   - phone      : 연락처
    #   - org        : 소속
    #   + id, created_at 은 내부 관리용 필드
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

    conn.commit()
    conn.close()
    print("✅ users.db 파일과 users 테이블(아이디/비번/이름/연락처/소속)이 준비되었습니다.")

if __name__ == "__main__":
    init_db()
