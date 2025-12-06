# app.py
import streamlit as st
import bcrypt
import os
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

# -------------------------------------------------------------------
# 0. Supabase(PostgreSQL) 연결 설정
# -------------------------------------------------------------------
# 📌 .streamlit/secrets.toml 또는 Streamlit Cloud Secrets 에서는
# [supabase_db]
# url = "postgresql+psycopg2://postgres:비밀번호@db.ixobrnombelwssyoeohu.supabase.co:5432/postgres?sslmode=require"
# 이런 형태로 저장해 둔다.
db_conf = st.secrets["supabase_db"]

# URL 하나만 사용 (user/host/port 직접 조합 X)
DB_URL = db_conf["postgresql://postgres.ixobrnombelwssyoeohu:dksdkwhdy1#@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres"]

engine = create_engine(DB_URL, pool_pre_ping=True)

# -------------------------------------------------------------------
# 파일 이미지 리스트
# -------------------------------------------------------------------
MAIN_IMAGES = [
    "main1.png",
    "main2.png",
    "main3.png",
    "main4.png",
    "main5.png",
    "main6.png",
    "main7.png"
]

# Google Form URL
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSejzhM-jkAS82RVcVkwfB2voKb14iinPqdIyYx4MB0F2JbFrQ/viewform"

# -------------------------------------------------------------------
# 1. DB 초기화
# -------------------------------------------------------------------
def init_db():
    create_users_sql = """
    create table if not exists public.users (
        id bigserial primary key,
        user_id text not null unique,
        password_hash text not null,
        name text not null,
        phone text,
        org text,
        rental_count integer not null default 0,
        created_at timestamptz not null default now()
    );
    """

    create_umbrellas_sql = """
    create table if not exists public.umbrellas (
        id bigserial primary key,
        user_id bigint not null references public.users(id),
        status text not null,
        rented_at timestamptz,
        returned_at timestamptz
    );
    """

    with engine.begin() as conn:
        conn.execute(text(create_users_sql))
        conn.execute(text(create_umbrellas_sql))

# -------------------------------------------------------------------
# 2. 회원가입
# -------------------------------------------------------------------
def register_user(user_id, password, name, phone, org):
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    sql = """
    insert into public.users (user_id, password_hash, name, phone, org)
    values (:user_id, :password_hash, :name, :phone, :org);
    """

    try:
        with engine.begin() as conn:
            conn.execute(
                text(sql),
                {
                    "user_id": user_id,
                    "password_hash": password_hash,
                    "name": name,
                    "phone": phone or None,
                    "org": org or None,
                },
            )
        return True, "회원가입이 완료되었습니다."
    except IntegrityError:
        return False, "이미 존재하는 아이디입니다."

# -------------------------------------------------------------------
# 3. 로그인
# -------------------------------------------------------------------
def login_user(user_id, password):
    # 관리자 계정 고정
    if user_id == "rising__wing" and password == "2@dou#4ble%AA":
        return True, {
            "id": 0,
            "user_id": "rising__wing",
            "name": "관리자",
            "phone": None,
            "org": "관리자",
            "is_admin": True
        }

    sql = """
    select id, user_id, password_hash, name, phone, org
    from public.users
    where user_id = :user_id;
    """

    with engine.begin() as conn:
        row = conn.execute(text(sql), {"user_id": user_id}).mappings().first()

    if row is None:
        return False, "존재하지 않는 아이디입니다."

    if bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")):
        return True, {
            "id": row["id"],
            "user_id": row["user_id"],
            "name": row["name"],
            "phone": row["phone"],
            "org": row["org"],
            "is_admin": False
        }
    else:
        return False, "비밀번호가 올바르지 않습니다."

# -------------------------------------------------------------------
# 4. 대여/반납
# -------------------------------------------------------------------
def get_current_rental(user_db_id):
    sql = """
    select id, status, rented_at, returned_at
    from public.umbrellas
    where user_id = :user_id and returned_at is null
    order by rented_at desc
    limit 1;
    """
    with engine.begin() as conn:
        return conn.execute(text(sql), {"user_id": user_db_id}).first()

def rent_umbrella(user_db_id):
    if get_current_rental(user_db_id) is not None:
        return False, "이미 대여 중인 우산이 있습니다."

    insert_sql = """
    insert into public.umbrellas (user_id, status, rented_at, returned_at)
    values (:user_id, 'RENTED', :rented_at, null);
    """

    update_count_sql = """
    update public.users
    set rental_count = rental_count + 1
    where id = :id;
    """

    now_ts = datetime.utcnow()

    with engine.begin() as conn:
        conn.execute(text(insert_sql), {"user_id": user_db_id, "rented_at": now_ts})
        conn.execute(text(update_count_sql), {"id": user_db_id})

    return True, "우산 대여가 완료되었습니다."

def return_umbrella(user_db_id):
    current = get_current_rental(user_db_id)
    if current is None:
        return False, "대여 중인 우산이 없습니다."

    sql = """
    update public.umbrellas
    set status = 'RETURNED', returned_at = :returned_at
    where id = :id;
    """

    now_ts = datetime.utcnow()

    with engine.begin() as conn:
        conn.execute(text(sql), {"returned_at": now_ts, "id": current[0]})

    return True, "반납이 완료되었습니다."

# -------------------------------------------------------------------
# 5. Streamlit 메인
# -------------------------------------------------------------------
def main():
    st.set_page_config(page_title="다시펴다", page_icon="🍃")

    init_db()

    if "user" not in st.session_state:
        st.session_state["user"] = None
    if "page" not in st.session_state:
        st.session_state["page"] = "home"
    if "img_index" not in st.session_state:
        st.session_state["img_index"] = 0

    # =============================
    # 로그인 상태
    # =============================
    if st.session_state["user"] is not None:
        user = st.session_state["user"]
        user_db_id = user["id"]

        st.title("🔐 회원 시스템")
        st.success(f"{user['name']}({user['user_id']})님, 환영합니다!")

        st.write(f"**이름:** {user['name']}")
        st.write(f"**아이디:** {user['user_id']}")
        st.write(f"**연락처:** {user['phone'] or '미등록'}")
        st.write(f"**소속:** {user['org'] or '미등록'}")

        with engine.begin() as conn:
            rental_count = conn.execute(
                text("select rental_count from public.users where id = :id"),
                {"id": user_db_id}
            ).scalar_one()

        st.write(f"**우산 대여 횟수:** {rental_count}회")

        st.markdown("---")
        st.subheader("🌂 우산 대여 / 반납")

        current_rental = get_current_rental(user_db_id)
        has_umbrella = current_rental is not None

        if has_umbrella:
            st.info("현재 우산을 **대여 중**입니다.")
        else:
            st.info("대여 중인 우산이 없습니다.")

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

        st.markdown("---")

        if st.button("로그아웃"):
            st.session_state["user"] = None
            st.session_state["page"] = "home"
            st.rerun()
        return

    # =============================
    # 메인 랜딩 페이지
    # =============================
    if st.session_state["page"] == "home":
        st.title("다시펴다 with WING")

        # 제목 바로 아래 설문 버튼
        st.link_button("📝 설문 작성하러 가기", FORM_URL)

        # 메인 이미지
        current_idx = st.session_state["img_index"]
        current_img = MAIN_IMAGES[current_idx % len(MAIN_IMAGES)]

        try:
            st.image(current_img, use_column_width=True)
        except:
            st.info(f"{current_img} 파일이 폴더에 없습니다.")

        if st.button("👉 Next"):
            st.session_state["img_index"] = (st.session_state["img_index"] + 1) % len(MAIN_IMAGES)
            st.rerun()

        st.markdown("---")
        st.write("아직 회원이 아니라면 **회원가입**, 이미 있다면 **로그인**을 진행해주세요.")

        if st.button("🔐 로그인 / 회원가입 하러 가기"):
            st.session_state["page"] = "auth"
            st.rerun()

        return

    # =============================
    # 로그인 / 회원가입 페이지
    # =============================
    if st.session_state["page"] == "auth":
        st.title("🔐 로그인 / 회원가입")

        tab_login, tab_reg = st.tabs(["로그인", "회원가입"])

        # 로그인
        with tab_login:
            login_user_id = st.text_input("아이디")
            login_pw = st.text_input("비밀번호", type="password")

            if st.button("로그인하기"):
                ok, result = login_user(login_user_id, login_pw)
                if ok:
                    st.session_state["user"] = result
                    st.success("로그인 성공!")
                    st.rerun()
                else:
                    st.error(result)

        # 회원가입
        with tab_reg:
            reg_user_id = st.text_input("아이디", key="reg_user_id")
            reg_pw = st.text_input("비밀번호", type="password", key="reg_pw")
            reg_pw2 = st.text_input("비밀번호 확인", type="password", key="reg_pw2")
            reg_name = st.text_input("이름", key="reg_name")
            reg_phone = st.text_input("연락처 (선택)")
            reg_org = st.text_input("소속 (선택)")

            if st.button("회원가입하기"):
                if reg_pw != reg_pw2:
                    st.error("비밀번호가 서로 다릅니다.")
                elif not reg_user_id or not reg_pw or not reg_name:
                    st.error("아이디, 비밀번호, 이름은 필수입니다.")
                else:
                    ok, msg = register_user(reg_user_id, reg_pw, reg_name, reg_phone, reg_org)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

        st.markdown("---")
        if st.button("⬅ 메인 페이지로 돌아가기"):
            st.session_state["page"] = "home"
            st.rerun()


if __name__ == "__main__":
    main()
