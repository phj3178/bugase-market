# -*- coding: utf-8 -*-
"""
회원가입 / 로그인 / 로그아웃 기능 (Blueprint).

app.py 에서 register_auth(app) 으로 등록한다.
"""
import re
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, jsonify)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from models_db import db, User

auth = Blueprint("auth", __name__)
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "로그인이 필요합니다."

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def register_auth(app):
    """app.py 에서 호출: 로그인 매니저 + 인증 라우트 등록."""
    login_manager.init_app(app)
    app.register_blueprint(auth)


# ---------------------------------------------------------
# 회원가입
# ---------------------------------------------------------
@auth.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        password2 = request.form.get("password2") or ""
        user_type = request.form.get("user_type") or ""
        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        region = (request.form.get("region") or "").strip()

        # --- 입력 검증 ---
        err = None
        if not EMAIL_RE.match(email):
            err = "이메일 형식이 올바르지 않습니다."
        elif len(password) < 6:
            err = "비밀번호는 6자 이상이어야 합니다."
        elif password != password2:
            err = "비밀번호가 서로 일치하지 않습니다."
        elif user_type not in ("farmer", "company"):
            err = "회원 유형(농가/기업)을 선택하세요."
        elif not name:
            err = "이름 또는 상호명을 입력하세요."
        elif User.query.filter_by(email=email).first():
            err = "이미 가입된 이메일입니다."

        if err:
            flash(err, "error")
            return render_template("signup.html", form=request.form)

        user = User(email=email, user_type=user_type, name=name,
                    phone=phone, region=region)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(f"{name}님, 가입을 환영합니다!", "success")
        return redirect(url_for("index"))

    return render_template("signup.html", form={})


# ---------------------------------------------------------
# 로그인
# ---------------------------------------------------------
@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
            return render_template("login.html", form=request.form)

        login_user(user)
        nxt = request.args.get("next")
        return redirect(nxt or url_for("index"))

    return render_template("login.html", form={})


# ---------------------------------------------------------
# 로그아웃
# ---------------------------------------------------------
@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("로그아웃되었습니다.", "success")
    return redirect(url_for("index"))


# ---------------------------------------------------------
# 계정 관리 API (마이페이지에서 호출)
# ---------------------------------------------------------
@auth.route("/api/account", methods=["GET"])
@login_required
def get_account():
    u = current_user
    return jsonify({"ok": True, "account": {
        "email": u.email, "name": u.name, "phone": u.phone or "",
        "region": u.region or "", "user_type": u.user_type,
        "bank_name": u.bank_name or "", "bank_account": u.bank_account or "",
        "account_holder": u.account_holder or "",
        "is_admin": u.is_admin,
    }})


@auth.route("/api/account/profile", methods=["POST"])
@login_required
def update_profile():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "사유": "이름/상호명을 입력하세요."}), 400
    current_user.name = name
    current_user.phone = (data.get("phone") or "").strip()
    current_user.region = (data.get("region") or "").strip()
    # 농가 정산 계좌 (기업 회원은 보내지 않으면 그대로 유지)
    if "bank_name" in data:
        current_user.bank_name = (data.get("bank_name") or "").strip() or None
    if "bank_account" in data:
        current_user.bank_account = (data.get("bank_account") or "").strip() or None
    if "account_holder" in data:
        current_user.account_holder = (data.get("account_holder") or "").strip() or None
    db.session.commit()
    return jsonify({"ok": True, "name": current_user.name})


@auth.route("/api/account/password", methods=["POST"])
@login_required
def change_password():
    data = request.get_json(force=True, silent=True) or {}
    current = data.get("current") or ""
    new = data.get("new") or ""
    new2 = data.get("new2") or ""

    if not current_user.check_password(current):
        return jsonify({"ok": False, "사유": "현재 비밀번호가 올바르지 않습니다."}), 400
    if len(new) < 6:
        return jsonify({"ok": False, "사유": "새 비밀번호는 6자 이상이어야 합니다."}), 400
    if new != new2:
        return jsonify({"ok": False, "사유": "새 비밀번호가 서로 일치하지 않습니다."}), 400

    current_user.set_password(new)
    db.session.commit()
    return jsonify({"ok": True})


@auth.route("/api/account/delete", methods=["POST"])
@login_required
def delete_account():
    data = request.get_json(force=True, silent=True) or {}
    if not current_user.check_password(data.get("password") or ""):
        return jsonify({"ok": False, "사유": "비밀번호가 올바르지 않습니다."}), 400
    # 로그아웃 전에 실제 User 객체를 확보 (current_user는 프록시라 로그아웃 후 풀림)
    user = db.session.get(User, current_user.id)
    logout_user()
    # cascade 설정으로 매물·신청도 함께 삭제됨
    db.session.delete(user)
    db.session.commit()
    return jsonify({"ok": True})
