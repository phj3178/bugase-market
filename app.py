# -*- coding: utf-8 -*-
"""
부가새 (Bugase) Flask 서버 — 거래 플랫폼 버전.

실행:
    pip install -r requirements.txt
    python init_db.py     # 최초 1회 (DB 생성)
    python app.py
    -> http://127.0.0.1:5000
"""
import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, abort

import model
import config
from models_db import db
from auth import register_auth
from market import register_market

app = Flask(__name__)

# --- 기본 설정 ---
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "bugase-dev-secret-change-me")

# DB 주소: 환경변수 DATABASE_URL 이 있으면 그것(배포: PostgreSQL),
# 없으면 로컬 SQLite 파일을 사용한다.
db_url = os.environ.get("DATABASE_URL")
if db_url:
    # Render/Heroku는 'postgres://'로 주는데 SQLAlchemy는 'postgresql://'를 요구
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
else:
    db_url = "sqlite:///" + os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "bugase.db")
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# --- 데이터베이스 + 로그인 연결 ---
db.init_app(app)
register_auth(app)
register_market(app)
with app.app_context():
    db.create_all()  # 테이블 없으면 생성
    # 기존 테이블에 새 컬럼이 없으면 추가 (데이터 보존 마이그레이션)
    from sqlalchemy import inspect, text
    try:
        cols = [c["name"] for c in inspect(db.engine).get_columns("listings")]
        if "delete_reason" not in cols:
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE listings ADD COLUMN delete_reason VARCHAR(500)"))
            print("[부가새] listings.delete_reason 컬럼 추가됨")
        pcols = [c["name"] for c in inspect(db.engine).get_columns("purchase_requests")]
        if "reject_reason" not in pcols:
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE purchase_requests ADD COLUMN reject_reason VARCHAR(500)"))
            print("[부가새] purchase_requests.reject_reason 컬럼 추가됨")

        # --- 에스크로(안심결제) 관련 신규 컬럼 ---
        ucols = [c["name"] for c in inspect(db.engine).get_columns("users")]
        user_new = {
            "bank_name": "VARCHAR(40)",
            "bank_account": "VARCHAR(40)",
            "account_holder": "VARCHAR(40)",
        }
        for col, typ in user_new.items():
            if col not in ucols:
                with db.engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {typ}"))
                print(f"[부가새] users.{col} 컬럼 추가됨")

        pr_new = {
            "offer_price": "INTEGER",
            "virtual_account": "VARCHAR(60)",
            "fee": "INTEGER",
            "settle_amount": "INTEGER",
            "paid_at": "TIMESTAMP",
            "settled_at": "TIMESTAMP",
        }
        for col, typ in pr_new.items():
            if col not in pcols:
                with db.engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE purchase_requests ADD COLUMN {col} {typ}"))
                print(f"[부가새] purchase_requests.{col} 컬럼 추가됨")
    except Exception as e:
        print("[부가새] 스키마 점검 건너뜀:", e)

# CORS 허용: 아임웹 등 다른 주소의 웹페이지에서 이 백엔드 API를 부를 수 있게 함.
try:
    from flask_cors import CORS
    CORS(app)
except ImportError:
    print("[부가새] flask-cors 미설치 → CORS 비활성 (로컬 테스트는 문제 없음)")

# 앱 시작 시 모델 1회 로드/학습
MODE = model.load_and_train()
print(f"[부가새] 모델 모드: {MODE.upper()}  "
      f"({'실제 XGBoost 모델' if MODE == 'real' else 'data/ 파일 없음 → 샘플 데모'})")


def _attach_price(result):
    """예측 결과에 부산물 단가·수익 추정을 덧붙인다(가격은 config 기준값)."""
    if not result.get("ok"):
        return result
    total_revenue = 0
    total_disposal = 0
    for bp in result["부산물"]:
        kg = bp["발생량_톤"] * 1000
        price = config.price_of(bp["이름"])
        disp = config.disposal_of(bp["이름"])
        bp["단가_원_kg"] = price
        bp["예상수익_원"] = round(kg * price)
        bp["폐기비용_원"] = round(kg * disp)
        total_revenue += kg * price
        total_disposal += kg * disp
    result["예상수익_원"] = round(total_revenue)
    result["폐기비용_원"] = round(total_disposal)
    result["부산물합계_kg"] = round(result["부산물합계_톤"] * 1000)
    return result


@app.route("/")
def index():
    return render_template("home.html", mode=MODE, active="home")






@app.route("/about")
def about():
    return render_template("about.html", mode=MODE, active="about")



@app.route("/service")
def service():
    return render_template("service.html", mode=MODE, active="service")


@app.route("/faq")
def faq():
    return render_template("faq.html", mode=MODE, active="faq")


@app.route("/api/options")
def api_options():
    return jsonify(model.list_options())


@app.route("/api/me")
def api_me():
    """프론트가 현재 로그인 상태/유형을 알 수 있게 한다."""
    from flask_login import current_user
    if current_user.is_authenticated:
        return jsonify({"authenticated": True, "user_type": current_user.user_type,
                        "name": current_user.name, "is_admin": current_user.is_admin})
    return jsonify({"authenticated": False})


@app.route("/mypage")
def mypage():
    from flask_login import current_user
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next="/mypage"))
    return render_template("mypage.html", mode=MODE, active="mypage")


@app.route("/dashboard")
def dashboard():
    """기업용 원료 수급 예측 대시보드 (로그인 회원 전용)."""
    from flask_login import current_user
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next="/dashboard"))
    return render_template("dashboard.html", mode=MODE, active="dashboard",
                           kakao_key=config.KAKAO_JS_KEY)




@app.route("/admin")
def admin():
    """부가새 운영자 정산 관리 화면."""
    from flask_login import current_user
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next="/admin"))
    if not current_user.is_admin:
        abort(403)
    return render_template("admin.html", mode=MODE, active="admin")


@app.route("/api/predict", methods=["POST"])
def api_predict():
    data = request.get_json(force=True, silent=True) or {}
    code = data.get("crop")
    작물 = model.CROP_CODES.get(code, code)  # 영문코드 → 한글명
    도 = data.get("do")
    시군 = data.get("sigun") or None
    연도 = data.get("year", 2026)
    면적_ha = data.get("area_ha")

    # 면적을 ㎡로 받으면 ha로 환산
    if 면적_ha is None and data.get("area_m2") is not None:
        면적_ha = float(data["area_m2"]) / 10000.0
    if 면적_ha is None:
        면적_ha = 0

    if not 작물 or not 도:
        return jsonify({"ok": False, "사유": "작물/지역을 선택하세요"}), 400

    result = model.predict(도, 작물, 면적_ha, 연도, 시군=시군)
    result = _attach_price(result)
    return jsonify(result)


@app.route("/api/match", methods=["POST"])
def api_match():
    """기업용: 작물 기준 주산지를 예측 발생량 순으로 정렬."""
    data = request.get_json(force=True, silent=True) or {}
    code = data.get("crop")
    작물 = model.CROP_CODES.get(code, code)
    연도 = data.get("year", 2026)
    면적_ha = float(data.get("area_ha", 10))

    rows = model.rank_regions(작물, 연도, 면적_ha=면적_ha, top=8)
    rows = [_attach_price(r) for r in rows]
    return jsonify({"ok": True, "crop": 작물, "results": rows})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
