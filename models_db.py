# -*- coding: utf-8 -*-
"""
부가새 거래 플랫폼 데이터베이스 구조.

테이블 3개:
  - User           회원 (농부 / 기업)
  - Listing        부산물 매물 (농부가 등록)
  - PurchaseRequest 구매 신청 (기업이 매물에 신청)
"""
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """회원. user_type 으로 농부('farmer')와 기업('company')을 구분."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    user_type = db.Column(db.String(10), nullable=False)   # 'farmer' | 'company'
    name = db.Column(db.String(80), nullable=False)         # 이름 또는 상호명
    phone = db.Column(db.String(30))                        # 연락처
    region = db.Column(db.String(80))                       # 기본 지역(선택)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 관계: 농부가 등록한 매물 / 기업이 넣은 구매신청
    listings = db.relationship("Listing", backref="seller", lazy=True,
                               cascade="all, delete-orphan")
    requests = db.relationship("PurchaseRequest", backref="buyer", lazy=True,
                               cascade="all, delete-orphan")

    def set_password(self, raw):
        # 비밀번호는 원문 저장 금지 → 해시(암호화)해서 저장
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    @property
    def is_farmer(self):
        return self.user_type == "farmer"

    @property
    def is_company(self):
        return self.user_type == "company"


class Listing(db.Model):
    """부산물 매물. 농부가 AI 예측 결과를 바탕으로 등록."""
    __tablename__ = "listings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    crop = db.Column(db.String(20), nullable=False)        # 작물 (예: 논벼)
    do = db.Column(db.String(30), nullable=False)          # 도
    sigun = db.Column(db.String(30))                       # 시군 (논벼 등)
    byproduct = db.Column(db.String(30), nullable=False)   # 부산물 종류 (예: 볏짚)
    amount_ton = db.Column(db.Float, nullable=False)       # 예상 발생량(톤)
    price_won = db.Column(db.Integer)                      # 희망 가격(원)
    farm_location = db.Column(db.String(200))              # 농장 위치/주소
    harvest_date = db.Column(db.Date)                      # 수확 예정일
    note = db.Column(db.String(500))                       # 추가 설명(선택)

    status = db.Column(db.String(12), default="selling")   # 'selling' | 'done'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    requests = db.relationship("PurchaseRequest", backref="listing", lazy=True,
                               cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "crop": self.crop,
            "do": self.do,
            "sigun": self.sigun,
            "byproduct": self.byproduct,
            "amount_ton": self.amount_ton,
            "price_won": self.price_won,
            "farm_location": self.farm_location,
            "harvest_date": self.harvest_date.isoformat() if self.harvest_date else None,
            "note": self.note,
            "status": self.status,
            "seller_name": self.seller.name if self.seller else None,
            "seller_phone": self.seller.phone if self.seller else None,
            "created_at": self.created_at.strftime("%Y-%m-%d") if self.created_at else None,
            "request_count": len(self.requests),
        }


class PurchaseRequest(db.Model):
    """구매 신청. 기업이 특정 매물에 신청하면 농부의 신청함에 표시된다."""
    __tablename__ = "purchase_requests"

    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listings.id"), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    message = db.Column(db.String(500))                    # 기업이 남기는 메시지
    status = db.Column(db.String(12), default="pending")   # pending|accepted|rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "listing_id": self.listing_id,
            "company_name": self.buyer.name if self.buyer else None,
            "company_phone": self.buyer.phone if self.buyer else None,
            "message": self.message,
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else None,
        }
