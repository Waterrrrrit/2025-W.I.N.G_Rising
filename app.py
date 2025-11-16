# app.py
import streamlit as st
import sqlite3
import bcrypt
from datetime import datetime

# ---------- DB 연결 ----------
def get_conn():
    return sqlite3.connect("users.db")

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

    if bcrypt.checkpw(password.encode("utf-8"), db_password_hash):
        user_info = {
            "id": db_id,
            "user_id": db_user_id,
            "name": db_name,
            "phone": db_phone,
            "org": db_org,
        }
        return True, user_info
    else:
        return False, "비밀번호가 올바르지 않습니다."

# ---------- Streamlit 메인 ----------
def main():
    st.set_page_config(page_title="회원 관리 MVP", page_icon="🔐")

    if "user" not in st.session_state:
        st.session_state["user"] = None

    st.title("🔐 SQLite + Streamlit 회원 시스템 (MVP)")

    # 로그인된 상태
    if st.session_state["user"] is not None:
        user = st.session_state["user"]

        st.success(f"{user['name']}({user['user_id']})님, 환영합니다! 🎉")

        st.markdown("### 👤 내 정보")
        st.write(f"- 이름: **{user['name']}**")
        st.write(f"- 아이디: **{user['user_id']}**")
        st.write(f"- 연락처: **{user['phone'] or '미등록'}**")
        st.write(f"- 소속: **{user['org'] or '미등록'}**")

        st.markdown("---")
        st.write("여기 아래부터는 **로그인한 회원만** 사용할 기능들을 붙이면 됩니다.")

        if st.button("로그아웃"):
            st.session_state["user"] = None
            st.rerun()
        return

    # 로그인 / 회원가입 탭
    tab_login, tab_register = st.tabs(["로그인", "회원가입"])

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

    with tab_register:
        st.subheader("회원가입")

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
                ok, msg = register_user(reg_user_id, reg_pw, reg_name, reg_phone, reg_org)
                if ok:
                    st.success(msg)
                    st.info("이제 '로그인' 탭에서 로그인해 주세요.")
                else:
                    st.error(msg)

if __name__ == "__main__":
    main()
