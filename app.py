# app.py
import streamlit as st
import sqlite3
import bcrypt
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")
# 메인 페이지에서 사용할 이미지들 (원하는 파일명으로 바꾸기)
MAIN_IMAGES = [
    "main1.png",
    "main2.png",
    "main3.png",
    "main4.png",
    "main5.png",
    "main6.png",
    "main7.png"
]

# ---------- DB 연결 ----------

def get_conn():
    return sqlite3.connect(DB_PATH)

# ---------- DB 초기화 (스키마만 보정, 데이터 삭제 없음) ----------
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
    cols = [row[1] for row in cur.fetchall()]
    if "created_at" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN created_at TEXT;")

    conn.commit()
    conn.close()

# ---------- 회원가입 ----------
def register_user(user_id, password, name, phone, org):
    conn = get_conn()
    cur = conn.cursor()

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    try:
        cur.execute(
            """
            INSERT INTO users (user_id, password_hash, name, phone, org, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (user_id, password_hash, name, phone, org, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        return True, "회원가입이 완료되었습니다."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "이미 존재하는 아이디입니다."

# ---------- 로그인 ----------
def login_user(user_id, password):
    # 관리자 계정 체크
    if user_id == "rising__wing" and password == "2@dou#4ble%AA":
        # DB에서 찾지 않고 바로 관리자 정보 반환
        return True, {
            "id": 0,  # DB에 없는 가짜 값
            "user_id": "rising__wing",
            "name": "관리자",
            "phone": None,
            "org": "관리자",
            "is_admin": True
        }

    # ---- 일반 사용자 로그인 ----
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, user_id, password_hash, name, phone, org
        FROM users
        WHERE user_id = ?;
        """,
        (user_id,)
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        return False, "존재하지 않는 아이디입니다."

    db_id, db_user_id, db_password_hash, db_name, db_phone, db_org = row

    if isinstance(db_password_hash, str):
        db_password_hash = db_password_hash.encode("utf-8")

    if bcrypt.checkpw(password.encode("utf-8"), db_password_hash):
        return True, {
            "id": db_id,
            "user_id": db_user_id,
            "name": db_name,
            "phone": db_phone,
            "org": db_org,
            "is_admin": False
        }
    else:
        return False, "비밀번호가 올바르지 않습니다."


# ---------- 우산 대여/반납 관련 함수 ----------
def get_current_rental(user_db_id):
    """해당 회원이 현재 대여 중인 우산이 있는지 조회"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, status, rented_at, returned_at
        FROM umbrellas
        WHERE user_id = ? AND returned_at IS NULL
        ORDER BY rented_at DESC
        LIMIT 1;
        """,
        (user_db_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row  # 없으면 None

def rent_umbrella(user_db_id):
    """우산 대여 처리"""
    if get_current_rental(user_db_id) is not None:
        return False, "이미 대여 중인 우산이 있습니다."

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO umbrellas (user_id, status, rented_at, returned_at)
        VALUES (?, ?, ?, NULL);
        """,
        (user_db_id, "RENTED", datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return True, "우산 대여가 완료되었습니다."

def return_umbrella(user_db_id):
    """우산 반납 처리"""
    current = get_current_rental(user_db_id)
    if current is None:
        return False, "현재 대여 중인 우산이 없습니다."

    rental_id = current[0]

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE umbrellas
        SET status = ?, returned_at = ?
        WHERE id = ?;
        """,
        ("RETURNED", datetime.now().isoformat(), rental_id)
    )
    conn.commit()
    conn.close()
    return True, "우산 반납이 완료되었습니다."

# ---------- Streamlit 메인 ----------
def main():
    st.set_page_config(page_title="다시펴다", page_icon="🍃")

    # ✅ DB 스키마 준비 (데이터 삭제 아님)
    init_db()
    # 세션 상태 초기화
    if "user" not in st.session_state:
        st.session_state["user"] = None
    if "page" not in st.session_state:
        st.session_state["page"] = "home"   # home, auth
    if "img_index" not in st.session_state:
        st.session_state["img_index"] = 0   # 메인 이미지 인덱스

    # 1) 로그인된 상태 -----------------------------
    if st.session_state["user"] is not None:
        user = st.session_state["user"]
        user_db_id = user["id"]  # umbrellas 테이블에서 사용할 PK

        st.title("🔐 회원 시스템 ")
        st.success(f"{user['name']}({user['user_id']})님, 환영합니다! 🎉")

        st.markdown("### 👤 내 정보")
        st.write(f"- 이름: **{user['name']}**")
        st.write(f"- 아이디: **{user['user_id']}**")
        st.write(f"- 연락처: **{user['phone'] or '미등록'}**")
        st.write(f"- 소속: **{user['org'] or '미등록'}**")

        st.markdown("---")

                # ---- 관리자 전용 DB 다운로드 ----
        if user.get("is_admin", False):
            st.markdown("### 🛠 관리자 메뉴")

            st.info("관리자 전용 기능입니다.")

            # DB 다운로드 버튼 활성화
            with open(DB_PATH, "rb") as f:
                st.download_button(
                    label="📥 Cloud DB 다운로드 (users.db)",
                    data=f,
                    file_name="users.db",
                    mime="application/octet-stream"
                )

        # 🌂 우산 대여 / 반납 기능
        st.markdown("### 🌂 우산 대여 / 반납")

        current_rental = get_current_rental(user_db_id)
        has_umbrella = current_rental is not None

        if has_umbrella:
            st.info("현재 상태: **우산 대여 중**입니다.")
        else:
            st.info("현재 상태: 대여 중인 우산이 없습니다.")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("우산 대여하기", disabled=has_umbrella):
                ok, msg = rent_umbrella(user_db_id)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        with col2:
            if st.button("우산 반납하기", disabled=not has_umbrella):
                ok, msg = return_umbrella(user_db_id)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)


        
 

        if st.button("로그아웃"):
            st.session_state["user"] = None
            st.session_state["page"] = "home"
            st.rerun()
        return


    # 2) 메인(랜딩) 페이지 ------------------------
    if st.session_state["page"] == "home":
        st.title("다시펴다 with WING")

        # 현재 보여줄 이미지 선택
        current_idx = st.session_state["img_index"]
        current_img = None
        if MAIN_IMAGES:
            current_img = MAIN_IMAGES[current_idx % len(MAIN_IMAGES)]

        # 이미지 + 클릭 안내
        if current_img is not None:
            try:
                st.image(
                    current_img,
                    use_column_width=True,
                    caption="아래 버튼을 눌러 다음 이미지를 볼 수 있습니다.",
                )
            except Exception:
                st.info(
                    f"{current_img} 파일을 프로젝트 폴더(app.py와 같은 위치)에 넣으면 여기 표시됩니다."
                )
        else:
            st.info("표시할 메인 이미지가 없습니다. MAIN_IMAGES 리스트를 확인해 주세요.")

        # 이미지를 '넘기는' 버튼
        if st.button("👉 Next"):
            st.session_state["img_index"] = (st.session_state["img_index"] + 1) % len(
                MAIN_IMAGES
            )
            st.rerun()


        st.markdown("---")
        st.write("아직 회원이 아니라면 먼저 **회원가입**, 이미 계정이 있다면 **로그인**을 진행해 주세요.")

        if st.button("🔐 로그인 / 회원가입 하러 가기"):
            st.session_state["page"] = "auth"
            st.rerun()
        return

    # 3) 로그인 / 회원가입 페이지 -----------------
    if st.session_state["page"] == "auth":
        st.title("🔐 로그인 / 회원가입")

        tab_login, tab_register = st.tabs(["로그인", "회원가입"])

        # 로그인 탭
        with tab_login:
            st.subheader("로그인")
            login_user_id = st.text_input("아이디", key="login_user_id")
            login_pw = st.text_input("비밀번호", type="password", key="login_pw")

            if st.button("로그인하기"):
                ok, result = login_user(login_user_id, login_pw)
                if ok:
                    st.session_state["user"] = result
                    st.success("로그인 성공!")
                    st.rerun()
                else:
                    st.error(result)

        # 회원가입 탭
        with tab_register:
            st.subheader("회원가입")
            st.write("다시펴다 서비스에서는 더 나은 우산 대여 경험을 위해 사용자 데이터를 수집하고 있습니다. " \
                    "수집된 데이터는RIS-ING 사업 외의 용도로 쓰이지 않으니, 안심하고 회원가입해주세요.")
            reg_user_id = st.text_input("아이디", key="reg_user_id")
            reg_pw = st.text_input("비밀번호", type="password", key="reg_pw")
            reg_pw2 = st.text_input("비밀번호 확인", type="password", key="reg_pw2")
            reg_name = st.text_input("이름", key="reg_name")
            reg_phone = st.text_input("연락처 (선택)", key="reg_phone")
            reg_org = st.text_input("소속 (선택)", key="reg_org")

            if st.button("회원가입하기"):
                if reg_pw != reg_pw2:
                    st.error("비밀번호가 서로 다릅니다.")
                elif not reg_user_id.strip() or not reg_pw.strip() or not reg_name.strip():
                    st.error("아이디, 비밀번호, 이름은 필수입니다.")
                else:
                    ok, msg = register_user(
                        reg_user_id, reg_pw, reg_name, reg_phone, reg_org
                    )
                    if ok:
                        st.success(msg)
                        st.info("이제 '로그인' 탭에서 로그인해 주세요.")
                    else:
                        st.error(msg)

        st.markdown("---")
        if st.button("⬅ 메인 페이지로 돌아가기"):
            st.session_state["page"] = "home"
            st.rerun()

if __name__ == "__main__":
    main()
