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
