# -*- coding: utf-8 -*-
"""
AgriLoop Flask 서버.

실행:
    pip install -r requirements.txt
    python app.py
    -> http://127.0.0.1:5000
"""
from flask import Flask, render_template, request, jsonify

import model
import config

app = Flask(__name__)

# CORS 허용: 아임웹 등 다른 주소의 웹페이지에서 이 백엔드 API를 부를 수 있게 함.
# flask-cors가 설치돼 있으면 켜고, 없으면(로컬 테스트 등) 조용히 넘어간다.
try:
    from flask_cors import CORS
    CORS(app)
except ImportError:
    print("[AgriLoop] flask-cors 미설치 → CORS 비활성 (로컬 테스트는 문제 없음)")

# 앱 시작 시 모델 1회 로드/학습
MODE = model.load_and_train()
print(f"[AgriLoop] 모델 모드: {MODE.upper()}  "
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
    return render_template("index.html", mode=MODE)


@app.route("/api/options")
def api_options():
    return jsonify(model.list_options())


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
