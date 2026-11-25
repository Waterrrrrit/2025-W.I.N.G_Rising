# api/index.py
# Vercel 서버리스(Python)용 Flask 앱. streamlit_app.py 의 기능을 그대로 옮김.
import os
import hmac
import secrets
from datetime import datetime, timezone
from functools import wraps

import bcrypt
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("VERCEL")),
)

FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSejzhM-jkAS82RVcVkwfB2voKb14iinPqdIyYx4MB0F2JbFrQ/viewform"
MAIN_IMAGES = [f"/images/main{i}.png" for i in range(1, 8)]

ADMIN_ID = os.environ.get("ADMIN_ID")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

# -------------------------------------------------------------------
# 0. DB 연결 (Supabase PostgreSQL)
#    DATABASE_URL 예: postgresql://postgres.xxxx:비밀번호@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres
# -------------------------------------------------------------------
_engine = None
_db_ready = False


def get_engine():
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL 환경변수가 설정되지 않았습니다.")
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg2://" + url[len("postgresql://"):]
        if "sslmode=" not in url:
            url += ("&" if "?" in url else "?") + "sslmode=require"
        # 서버리스 환경: 커넥션 풀은 Supabase pooler 에 맡기고 앱에서는 풀링하지 않음
        _engine = create_engine(url, poolclass=NullPool)
    return _engine


def init_db():
    global _db_ready
    if _db_ready:
        return
    with get_engine().begin() as conn:
        conn.execute(text("""
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
        """))
        conn.execute(text("""
            create table if not exists public.umbrellas (
                id bigserial primary key,
                user_id bigint not null references public.users(id),
                status text not null,
                rented_at timestamptz,
                returned_at timestamptz
            );
        """))
    _db_ready = True


# -------------------------------------------------------------------
# CSRF 토큰
# -------------------------------------------------------------------
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def check_csrf():
    if request.method == "POST":
        sent = request.form.get("_csrf", "")
        if not hmac.compare_digest(sent, session.get("_csrf", "")):
            abort(400)


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("auth"))
        return f(*args, **kwargs)
    return wrapper


# -------------------------------------------------------------------
# 1. 회원가입 / 로그인
# -------------------------------------------------------------------
def register_user(user_id, password, name, phone, org):
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    try:
        with get_engine().begin() as conn:
            conn.execute(
                text("""
                    insert into public.users (user_id, password_hash, name, phone, org)
                    values (:user_id, :password_hash, :name, :phone, :org);
                """),
                {"user_id": user_id, "password_hash": password_hash, "name": name,
                 "phone": phone or None, "org": org or None},
            )
        return True, "회원가입이 완료되었습니다."
    except IntegrityError:
        return False, "이미 존재하는 아이디입니다."


def login_user(user_id, password):
    if ADMIN_ID and ADMIN_PASSWORD and hmac.compare_digest(user_id, ADMIN_ID) \
            and hmac.compare_digest(password, ADMIN_PASSWORD):
        return True, {"id": 0, "user_id": ADMIN_ID, "name": "관리자",
                      "phone": None, "org": "관리자", "is_admin": True}

    with get_engine().begin() as conn:
        row = conn.execute(
            text("select id, user_id, password_hash, name, phone, org from public.users where user_id = :u"),
            {"u": user_id},
        ).mappings().first()

    if row is None:
        return False, "존재하지 않는 아이디입니다."
    if bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")):
        return True, {"id": row["id"], "user_id": row["user_id"], "name": row["name"],
                      "phone": row["phone"], "org": row["org"], "is_admin": False}
    return False, "비밀번호가 올바르지 않습니다."


# -------------------------------------------------------------------
# 2. 대여 / 반납
# -------------------------------------------------------------------
def get_current_rental(conn, user_db_id):
    return conn.execute(
        text("""
            select id from public.umbrellas
            where user_id = :u and returned_at is null
            order by rented_at desc limit 1;
        """),
        {"u": user_db_id},
    ).first()


def rent_umbrella(user_db_id):
    with get_engine().begin() as conn:
        # 동시 요청 시 중복 대여 방지
        conn.execute(text("select id from public.users where id = :u for update"), {"u": user_db_id})
        if get_current_rental(conn, user_db_id) is not None:
            return False, "이미 대여 중인 우산이 있습니다."
        conn.execute(
            text("insert into public.umbrellas (user_id, status, rented_at) values (:u, 'RENTED', :t)"),
            {"u": user_db_id, "t": datetime.now(timezone.utc)},
        )
        conn.execute(text("update public.users set rental_count = rental_count + 1 where id = :u"),
                     {"u": user_db_id})
    return True, "우산 대여가 완료되었습니다."


def return_umbrella(user_db_id):
    with get_engine().begin() as conn:
        current = get_current_rental(conn, user_db_id)
        if current is None:
            return False, "대여 중인 우산이 없습니다."
        conn.execute(
            text("update public.umbrellas set status = 'RETURNED', returned_at = :t where id = :id"),
            {"t": datetime.now(timezone.utc), "id": current[0]},
        )
    return True, "반납이 완료되었습니다."


# -------------------------------------------------------------------
# 3. 라우트
# -------------------------------------------------------------------
@app.route("/")
def home():
    if session.get("user"):
        return redirect(url_for("mypage"))
    return render_template("home.html", images=MAIN_IMAGES, form_url=FORM_URL)


@app.route("/auth", methods=["GET"])
def auth():
    if session.get("user"):
        return redirect(url_for("mypage"))
    return render_template("auth.html", tab=request.args.get("tab", "login"), form={})


@app.route("/login", methods=["POST"])
def login():
    init_db()
    ok, result = login_user(request.form.get("user_id", ""), request.form.get("password", ""))
    if ok:
        session.clear()
        session["user"] = result
        flash("로그인 성공!", "success")
        return redirect(url_for("mypage"))
    flash(result, "error")
    return render_template("auth.html", tab="login", form=request.form)


@app.route("/register", methods=["POST"])
def register():
    init_db()
    f = request.form
    user_id = f.get("user_id", "").strip()
    pw, pw2 = f.get("password", ""), f.get("password2", "")
    name = f.get("name", "").strip()
    if pw != pw2:
        flash("비밀번호가 서로 다릅니다.", "error")
    elif not user_id or not pw or not name:
        flash("아이디, 비밀번호, 이름은 필수입니다.", "error")
    else:
        ok, msg = register_user(user_id, pw, name, f.get("phone", "").strip(), f.get("org", "").strip())
        flash(msg, "success" if ok else "error")
        if ok:
            return redirect(url_for("auth", tab="login"))
    return render_template("auth.html", tab="register", form=f)


@app.route("/me")
@login_required
def mypage():
    user = session["user"]
    rental_count, has_umbrella = None, False
    if not user.get("is_admin"):
        init_db()
        with get_engine().begin() as conn:
            rental_count = conn.execute(text("select rental_count from public.users where id = :u"),
                                        {"u": user["id"]}).scalar()
            if rental_count is None:  # 계정이 삭제된 경우
                session.clear()
                return redirect(url_for("auth"))
            has_umbrella = get_current_rental(conn, user["id"]) is not None
    return render_template("me.html", user=user, rental_count=rental_count, has_umbrella=has_umbrella)


@app.route("/rent", methods=["POST"])
@login_required
def rent():
    user = session["user"]
    if not user.get("is_admin"):
        init_db()
        ok, msg = rent_umbrella(user["id"])
        flash(msg, "success" if ok else "error")
    return redirect(url_for("mypage"))


@app.route("/return", methods=["POST"])
@login_required
def return_():
    user = session["user"]
    if not user.get("is_admin"):
        init_db()
        ok, msg = return_umbrella(user["id"])
        flash(msg, "success" if ok else "error")
    return redirect(url_for("mypage"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.errorhandler(RuntimeError)
def runtime_error(e):
    return render_template("error.html", message=str(e)), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
