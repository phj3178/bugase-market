# -*- coding: utf-8 -*-
"""
모델을 '한 번만' 학습해서 agriloop_model.pkl 로 저장하는 스크립트.

사용법 (data/ 에 학습용 3개 파일이 있는 상태에서):
    python build_model.py

성공하면 agriloop_model.pkl 파일이 생깁니다.
이 파일만 있으면 서버는 데이터·학습 없이 바로 예측할 수 있습니다.
"""
import os
import pickle
import model

# 혹시 이전에 만든 pkl이 있으면 무시하고 데이터로 새로 학습하기 위해 잠시 비활성화
if os.path.exists(model.PKL):
    os.rename(model.PKL, model.PKL + ".bak")
    print(f"기존 {os.path.basename(model.PKL)} → .bak 로 백업")

mode = model.load_and_train()

if mode != "real":
    print("\n[중단] REAL 모드가 아닙니다.")
    print("data/ 폴더에 아래 3개 파일이 있는지 확인하세요:")
    print("  - AgriLoop_학습표_주산지.csv")
    print("  - 시군별_논벼_생산량_조곡(16년~25년).xlsx")
    print("  - ASOS_일자료.csv")
    raise SystemExit(1)

bundle = {"_R": model._R, "STATE": model.STATE}
with open(model.PKL, "wb") as f:
    pickle.dump(bundle, f)

size_mb = os.path.getsize(model.PKL) / (1024 * 1024)
print(f"\n저장 완료: {os.path.basename(model.PKL)}  ({size_mb:.1f} MB)")
print("이제 python app.py 로 실행하면 '저장된 모델 불러옴' 메시지가 떠야 합니다.")
