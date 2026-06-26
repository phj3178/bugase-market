# -*- coding: utf-8 -*-
"""
AgriLoop 설정값.

여기 있는 가격은 'AI 예측값이 아니라' 수익 추정을 위해 팀이 정하는 기준 단가입니다.
실제 시세에 맞게 자유롭게 수정하세요. (단위: 원/kg)
"""
import os

# data.go.kr ASOS 일자료 Decoding 인증키.
# 보안을 위해 환경변수로 주입하는 것을 권장합니다.
#   (mac/linux)  export ASOS_SERVICE_KEY="여기에_키"
#   (windows)    set ASOS_SERVICE_KEY=여기에_키
# 환경변수가 없으면 아래 기본값을 사용합니다. (없으면 평년값으로만 예측)
ASOS_SERVICE_KEY = os.environ.get(
    "ASOS_SERVICE_KEY",
    "8fc2bfa0688fb452667c4c69f7d478aaf0dabe1f41a16d06ea453dc39a193a7e",
)

# 카카오 지도 JavaScript 키 (developers.kakao.com → 내 앱 → JavaScript 키).
# 보안을 위해 환경변수 KAKAO_JS_KEY 로 주입하는 것을 권장합니다.
#   (mac/linux)  export KAKAO_JS_KEY="발급받은_JavaScript_키"
#   (windows)    set KAKAO_JS_KEY=발급받은_JavaScript_키
# 로컬에서 빠르게 테스트하려면 아래 따옴표 안에 키를 직접 붙여넣어도 됩니다.
KAKAO_JS_KEY = os.environ.get("KAKAO_JS_KEY", "b146800051ab794e054f1ec9695ed9aa")

# 부산물별 기준 단가 (원/kg). AI가 아니라 팀이 정하는 추정 시세.
BYPRODUCT_PRICE = {
    "볏짚": 130,
    "왕겨": 80,
    "보릿짚": 120,
    "옥수수대": 90,
    "콩대": 100,
    "콩깍지": 90,
    "전정가지": 70,
}

# 부산물별 소각·폐기 시 비용 (원/kg). 수익 비교용 추정값.
BYPRODUCT_DISPOSAL = {
    "볏짚": 60,
    "왕겨": 40,
    "보릿짚": 60,
    "옥수수대": 55,
    "콩대": 55,
    "콩깍지": 50,
    "전정가지": 80,
}

DEFAULT_PRICE = 100
DEFAULT_DISPOSAL = 60


def price_of(byproduct):
    return BYPRODUCT_PRICE.get(byproduct, DEFAULT_PRICE)


def disposal_of(byproduct):
    return BYPRODUCT_DISPOSAL.get(byproduct, DEFAULT_DISPOSAL)


# =========================================================
# 에스크로(안심결제) 데모 설정
# =========================================================

# 관리자(부가새 운영) 계정 이메일. 이 계정으로 로그인하면 정산 관리 화면(/admin)이 보인다.
# 환경변수 ADMIN_EMAILS 로 콤마 구분해 여러 개 지정 가능.
ADMIN_EMAILS = [
    e.strip().lower() for e in
    os.environ.get("ADMIN_EMAILS", "bugase2026@gmail.com").split(",")
    if e.strip()
]


def is_admin_email(email):
    return (email or "").strip().lower() in ADMIN_EMAILS


# 거래 규모별 수수료 구간 (데모).
# 농민 : 구매 기업 = 1 : 3 비율로 분담한다.
# 구간 판정은 "미만" 기준이다. 예: 0.5톤 미만은 1단계, 0.5톤 이상은 2단계.
# 항목: (상한_톤_미만, 농민_수수료율, 기업_수수료율, 표시문구)
FEE_TIERS = [
    (0.5, 0.015, 0.045, "0.5톤 미만"),
    (2.5, 0.012, 0.036, "0.5톤 이상 ~ 2.5톤 미만"),
    (5.5, 0.009, 0.027, "2.5톤 이상 ~ 5.5톤 미만"),
    (27.5, 0.007, 0.021, "5.5톤 이상 ~ 27.5톤 미만"),
    (float("inf"), 0.005, 0.015, "27.5톤 이상"),
]


def fee_rates_for(amount_ton):
    """중량(톤)에 따른 농민/기업 수수료율 정보를 반환한다."""
    t = float(amount_ton or 0)
    for limit, farmer_rate, buyer_rate, label in FEE_TIERS:
        if t < limit:
            return {
                "farmer_rate": farmer_rate,
                "buyer_rate": buyer_rate,
                "total_rate": farmer_rate + buyer_rate,
                "label": label,
            }
    limit, farmer_rate, buyer_rate, label = FEE_TIERS[-1]
    return {
        "farmer_rate": farmer_rate,
        "buyer_rate": buyer_rate,
        "total_rate": farmer_rate + buyer_rate,
        "label": label,
    }


def fee_breakdown_for(amount_ton, offer_price):
    """제안가 기준 수수료·입금액·정산액을 계산한다."""
    price = int(offer_price or 0)
    rates = fee_rates_for(amount_ton)
    farmer_fee = round(price * rates["farmer_rate"])
    buyer_fee = round(price * rates["buyer_rate"])
    return {
        **rates,
        "farmer_fee": farmer_fee,
        "buyer_fee": buyer_fee,
        "total_fee": farmer_fee + buyer_fee,
        "pay_amount": price + buyer_fee,
        "settle_amount": max(0, price - farmer_fee),
    }


def farmer_fee_rate_for(amount_ton):
    return fee_rates_for(amount_ton)["farmer_rate"]


def buyer_fee_rate_for(amount_ton):
    return fee_rates_for(amount_ton)["buyer_rate"]


def fee_rate_for(amount_ton):
    """기존 코드 호환용: 농민+기업 합산 수수료율을 반환한다."""
    return fee_rates_for(amount_ton)["total_rate"]
