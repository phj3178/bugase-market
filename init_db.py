# -*- coding: utf-8 -*-
"""
데이터베이스 파일(bugase.db)을 처음 만드는 스크립트.

사용법:
    python init_db.py

성공하면 bugase.db 파일이 생기고, 만들어진 테이블 목록이 출력됩니다.
이미 있으면 기존 테이블은 그대로 두고 없는 것만 추가합니다.
"""
import os
from flask import Flask
from models_db import db, User, Listing, PurchaseRequest

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "bugase.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()
    # 만들어진 테이블 확인
    from sqlalchemy import inspect
    tables = inspect(db.engine).get_table_names()
    print("데이터베이스 준비 완료: bugase.db")
    print("생성된 테이블:", ", ".join(tables))
    print("회원 수:", User.query.count(),
          "| 매물 수:", Listing.query.count(),
          "| 구매신청 수:", PurchaseRequest.query.count())
