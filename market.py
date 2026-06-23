# -*- coding: utf-8 -*-
"""
부가새 거래 기능 (Blueprint).

- 농가: 매물 등록 / 내 매물 조회
- 공통: 매물 목록·상세 조회 (검색은 다음 단계에서 확장)

app.py 에서 register_market(app) 으로 등록한다.
"""
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models_db import db, Listing, PurchaseRequest

market = Blueprint("market", __name__)


def register_market(app):
    app.register_blueprint(market)


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


# ---------------------------------------------------------
# 매물 등록 (농가 전용)
# ---------------------------------------------------------
@market.route("/api/listings", methods=["POST"])
@login_required
def create_listing():
    if not current_user.is_farmer:
        return jsonify({"ok": False, "사유": "농가 회원만 판매 등록할 수 있습니다."}), 403

    data = request.get_json(force=True, silent=True) or {}

    # 필수값 검증
    required = ["crop", "do", "byproduct", "amount_ton"]
    for k in required:
        if data.get(k) in (None, ""):
            return jsonify({"ok": False, "사유": f"필수 항목 누락: {k}"}), 400

    try:
        amount = float(data["amount_ton"])
    except (TypeError, ValueError):
        return jsonify({"ok": False, "사유": "발생량 형식이 올바르지 않습니다."}), 400

    price = data.get("price_won")
    try:
        price = int(price) if price not in (None, "") else None
    except (TypeError, ValueError):
        price = None

    listing = Listing(
        user_id=current_user.id,
        crop=str(data["crop"]).strip(),
        do=str(data["do"]).strip(),
        sigun=(str(data.get("sigun")).strip() or None) if data.get("sigun") else None,
        byproduct=str(data["byproduct"]).strip(),
        amount_ton=round(amount, 2),
        price_won=price,
        farm_location=(str(data.get("farm_location")).strip() or None),
        harvest_date=_parse_date(data.get("harvest_date")),
        note=(str(data.get("note")).strip() or None),
        status="selling",
    )
    db.session.add(listing)
    db.session.commit()
    return jsonify({"ok": True, "listing_id": listing.id, "listing": listing.to_dict()})


# ---------------------------------------------------------
# 내 매물 조회 (농가)
# ---------------------------------------------------------
@market.route("/api/my-listings")
@login_required
def my_listings():
    # 'deleted'(삭제된) 매물은 농가 목록에서 제외
    rows = (Listing.query.filter_by(user_id=current_user.id)
            .filter(Listing.status != "deleted")
            .order_by(Listing.created_at.desc()).all())
    return jsonify({"ok": True, "listings": [r.to_dict() for r in rows]})


# ---------------------------------------------------------
# 매물 상태 변경 / 삭제 (농가)
# ---------------------------------------------------------
@market.route("/api/listings/<int:listing_id>/status", methods=["POST"])
@login_required
def update_status(listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing or listing.user_id != current_user.id:
        return jsonify({"ok": False, "사유": "권한이 없습니다."}), 403
    new_status = (request.get_json(force=True, silent=True) or {}).get("status")
    if new_status not in ("selling", "done"):
        return jsonify({"ok": False, "사유": "잘못된 상태"}), 400
    listing.status = new_status
    db.session.commit()
    return jsonify({"ok": True, "status": listing.status})


@market.route("/api/listings/<int:listing_id>", methods=["DELETE"])
@login_required
def delete_listing(listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing or listing.user_id != current_user.id:
        return jsonify({"ok": False, "사유": "권한이 없습니다."}), 403

    reason = (request.get_json(force=True, silent=True) or {}).get("reason", "")
    reason = str(reason).strip()[:500]

    # 신청 이력이 있으면 완전 삭제 대신 '삭제됨'으로 표시 (기업이 사유를 볼 수 있게)
    if listing.requests:
        listing.status = "deleted"
        listing.delete_reason = reason or "판매자에 의해 삭제되었습니다."
        db.session.commit()
        return jsonify({"ok": True, "soft": True})

    # 신청 이력이 없으면 완전 삭제
    db.session.delete(listing)
    db.session.commit()
    return jsonify({"ok": True, "soft": False})


# ---------------------------------------------------------
# 매물 목록 조회 (공통, 검색은 다음 단계 확장)
# ---------------------------------------------------------
@market.route("/api/listings")
def list_listings():
    q = Listing.query.filter_by(status="selling")
    crop = request.args.get("crop")
    do = request.args.get("do")
    if crop:
        q = q.filter_by(crop=crop)
    if do:
        q = q.filter_by(do=do)
    rows = q.order_by(Listing.created_at.desc()).limit(100).all()

    # 로그인한 기업이면, 각 매물에 '내 신청 상태'를 표시 (중복 신청 버튼 방지)
    my_status = {}
    if current_user.is_authenticated and current_user.is_company:
        reqs = PurchaseRequest.query.filter_by(company_id=current_user.id).all()
        my_status = {r.listing_id: r.status for r in reqs}

    out = []
    for r in rows:
        d = r.to_dict()
        d["my_request_status"] = my_status.get(r.id)  # None|pending|accepted|rejected
        out.append(d)
    return jsonify({"ok": True, "listings": out})


# =========================================================
# 구매 신청 (기업 → 매물)
# =========================================================
@market.route("/api/listings/<int:listing_id>/request", methods=["POST"])
@login_required
def request_purchase(listing_id):
    if not current_user.is_company:
        return jsonify({"ok": False, "사유": "기업 회원만 구매 신청할 수 있습니다."}), 403

    listing = db.session.get(Listing, listing_id)
    if not listing or listing.status != "selling":
        return jsonify({"ok": False, "사유": "판매 중인 매물이 아닙니다."}), 404
    if listing.user_id == current_user.id:
        return jsonify({"ok": False, "사유": "본인 매물에는 신청할 수 없습니다."}), 400

    # 같은 매물에 이미 신청했는지 확인
    dup = PurchaseRequest.query.filter_by(
        listing_id=listing_id, company_id=current_user.id).first()
    if dup:
        return jsonify({"ok": False, "사유": "이미 신청한 매물입니다."}), 400

    msg = (request.get_json(force=True, silent=True) or {}).get("message", "")
    pr = PurchaseRequest(listing_id=listing_id, company_id=current_user.id,
                         message=str(msg).strip()[:500])
    db.session.add(pr)
    db.session.commit()
    return jsonify({"ok": True, "request_id": pr.id})


# 기업: 내가 신청한 목록
@market.route("/api/my-requests")
@login_required
def my_requests():
    if not current_user.is_company:
        return jsonify({"ok": False, "사유": "기업 전용"}), 403
    rows = (PurchaseRequest.query.filter_by(company_id=current_user.id)
            .order_by(PurchaseRequest.created_at.desc()).all())
    out = []
    for r in rows:
        d = r.to_dict()
        d["listing"] = r.listing.to_dict() if r.listing else None
        # 수락된 경우에만 농가 연락처 공개
        if r.status == "accepted" and r.listing and r.listing.seller:
            d["farmer_phone"] = r.listing.seller.phone
            d["farmer_name"] = r.listing.seller.name
        out.append(d)
    return jsonify({"ok": True, "requests": out})


# 농가: 내 매물에 들어온 신청함
@market.route("/api/received-requests")
@login_required
def received_requests():
    if not current_user.is_farmer:
        return jsonify({"ok": False, "사유": "농가 전용"}), 403
    # 내 매물들의 id
    my_ids = [l.id for l in current_user.listings]
    rows = (PurchaseRequest.query.filter(PurchaseRequest.listing_id.in_(my_ids))
            .order_by(PurchaseRequest.created_at.desc()).all()) if my_ids else []
    out = []
    for r in rows:
        d = r.to_dict()
        d["listing"] = r.listing.to_dict() if r.listing else None
        # 수락 시 기업 연락처는 to_dict의 company_phone로 이미 포함
        if r.status != "accepted":
            d["company_phone"] = None  # 수락 전에는 연락처 숨김
        out.append(d)
    return jsonify({"ok": True, "requests": out})


# 농가: 신청 수락 / 거절
@market.route("/api/requests/<int:req_id>/decide", methods=["POST"])
@login_required
def decide_request(req_id):
    pr = db.session.get(PurchaseRequest, req_id)
    if not pr or not pr.listing or pr.listing.user_id != current_user.id:
        return jsonify({"ok": False, "사유": "권한이 없습니다."}), 403
    decision = (request.get_json(force=True, silent=True) or {}).get("decision")
    if decision not in ("accepted", "rejected"):
        return jsonify({"ok": False, "사유": "잘못된 요청"}), 400
    pr.status = decision
    # 수락하면 해당 매물을 거래완료로 변경
    if decision == "accepted":
        pr.listing.status = "done"
    db.session.commit()
    return jsonify({"ok": True, "status": pr.status})
