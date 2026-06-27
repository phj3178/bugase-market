# -*- coding: utf-8 -*-
"""
부가새 거래 기능 (Blueprint).

- 농가: 매물 등록 / 내 매물 조회
- 공통: 매물 목록·상세 조회 (검색은 다음 단계에서 확장)

app.py 에서 register_market(app) 으로 등록한다.
"""
from datetime import datetime
import random
import json

from flask import Blueprint, request, jsonify, Response
from flask_login import login_required, current_user
from models_db import db, Listing, PurchaseRequest
import config

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


def _make_virtual_account():
    """데모용 가상계좌 번호를 생성한다. 실제 PG/은행 계좌가 아니라 화면 시연용 값이다."""
    chunks = ["".join(str(random.randint(0, 9)) for _ in range(4)) for _ in range(3)]
    return "부가새은행 3333-" + "-".join(chunks)


def _status_label(status):
    return {
        "pending": "대기중",
        "accepted": "거래 중",
        "paid": "입금 확인 대기",
        "settled": "거래 완료",
        "rejected": "거절됨",
    }.get(status, status)


def _admin_required():
    return current_user.is_authenticated and getattr(current_user, "is_admin", False)


def _transaction_dict(pr):
    """관리자 정산 화면에서 쓰는 거래 상세 직렬화."""
    listing = pr.listing
    seller = listing.seller if listing else None
    buyer = pr.buyer
    return {
        **pr.to_dict(),
        "status_label": _status_label(pr.status),
        "listing": listing.to_dict() if listing else None,
        "seller": {
            "name": seller.name if seller else None,
            "phone": seller.phone if seller else None,
            "bank_name": seller.bank_name if seller else None,
            "bank_account": seller.bank_account if seller else None,
            "account_holder": seller.account_holder if seller else None,
        },
        "buyer": {
            "name": buyer.name if buyer else None,
            "phone": buyer.phone if buyer else None,
            "email": buyer.email if buyer else None,
        },
    }


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
    if new_status not in ("selling", "trading", "done"):
        return jsonify({"ok": False, "사유": "잘못된 상태"}), 400
    listing.status = new_status
    db.session.commit()
    return jsonify({"ok": True, "status": listing.status})


# ---------------------------------------------------------
# 매물 정보 수정 (농가 본인 매물만) — 희망가/수확예정일/농장위치/추가설명
# ---------------------------------------------------------
@market.route("/api/listings/<int:listing_id>", methods=["PATCH"])
@login_required
def edit_listing(listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing or listing.user_id != current_user.id:
        return jsonify({"ok": False, "사유": "권한이 없습니다."}), 403
    if listing.status == "deleted":
        return jsonify({"ok": False, "사유": "삭제된 매물은 수정할 수 없습니다."}), 400

    data = request.get_json(force=True, silent=True) or {}

    # 희망가격 (빈 값이면 '가격 협의'로 처리 → None)
    if "price_won" in data:
        price = data.get("price_won")
        try:
            listing.price_won = int(price) if price not in (None, "") else None
        except (TypeError, ValueError):
            return jsonify({"ok": False, "사유": "희망가격 형식이 올바르지 않습니다."}), 400

    # 수확 예정일
    if "harvest_date" in data:
        listing.harvest_date = _parse_date(data.get("harvest_date"))

    # 농장 위치
    if "farm_location" in data:
        loc = (str(data.get("farm_location")).strip() if data.get("farm_location") else "")
        listing.farm_location = loc or None

    # 추가 설명
    if "note" in data:
        note = (str(data.get("note")).strip() if data.get("note") else "")
        listing.note = note[:500] or None

    db.session.commit()
    return jsonify({"ok": True, "listing": listing.to_dict()})


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
# 대시보드 데이터 (기업용 SCM 화면 / 부산물 지도)
# ---------------------------------------------------------
@market.route("/api/dashboard")
@login_required
def dashboard_data():
    """판매 중인 매물을 대시보드용으로 내려준다(집계·차트는 프론트에서 계산)."""
    rows = (Listing.query.filter_by(status="selling")
            .order_by(Listing.created_at.desc()).all())
    points = [{
        "id": r.id,
        "crop": r.crop,
        "byproduct": r.byproduct,
        "amount_ton": r.amount_ton,
        "do": r.do,
        "sigun": r.sigun,
        "farm_location": r.farm_location,
        "harvest_date": r.harvest_date.isoformat() if r.harvest_date else None,
        "seller_name": r.seller.name if r.seller else None,
    } for r in rows]
    return jsonify({"ok": True, "points": points})


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




# ---------------------------------------------------------
# 모바일 앱용 카카오 지도 페이지 (WebView)
# ---------------------------------------------------------
@market.route("/mobile-map")
def mobile_map():
    """React Native WebView에서 로드할 모바일 전용 지도 페이지.

    Kakao Maps JavaScript SDK는 도메인 검증을 하기 때문에 앱에 inline HTML로
    넣기보다 Flask가 직접 페이지를 내려주는 방식이 더 안정적이다.
    """
    q = Listing.query.filter_by(status="selling")
    crop = request.args.get("crop")
    do = request.args.get("do")
    if crop:
        q = q.filter_by(crop=crop)
    if do:
        q = q.filter_by(do=do)

    rows = q.order_by(Listing.created_at.desc()).limit(100).all()
    items = []
    for r in rows:
        address = r.farm_location or " ".join([x for x in [r.do, r.sigun] if x])
        items.append({
            "id": r.id,
            "title": f"{r.crop} · {r.byproduct}",
            "crop": r.crop,
            "byproduct": r.byproduct,
            "amountTon": r.amount_ton,
            "address": address,
            "sellerName": r.seller.name if r.seller else None,
            "priceWon": r.price_won,
        })

    payload = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    kakao_key = config.KAKAO_JS_KEY

    html = f"""<!doctype html>
<html lang=\"ko\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no\" />
  <style>
    html, body, #map {{ width: 100%; height: 100%; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', sans-serif; background: #EBD8B8; }}
    .overlay {{ position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: #EBD8B8; color: #3A3E1F; font-weight: 800; text-align: center; line-height: 1.55; padding: 24px; box-sizing: border-box; z-index: 10; }}
    .info {{ width: 220px; padding: 12px; box-sizing: border-box; color: #1C1A14; }}
    .title {{ font-weight: 900; font-size: 15px; margin-bottom: 6px; }}
    .addr {{ color: #5C6238; font-size: 12px; line-height: 1.45; margin-bottom: 7px; }}
    .meta {{ color: #3A3E1F; font-size: 12px; font-weight: 800; }}
    .fallback {{ position: absolute; left: 14px; right: 14px; bottom: 14px; padding: 10px 12px; border-radius: 14px; background: rgba(251, 250, 245, 0.94); color: #3A3E1F; font-size: 12px; line-height: 1.35; z-index: 20; box-shadow: 0 6px 18px rgba(0,0,0,.12); }}
  </style>
</head>
<body>
  <div id=\"map\"></div>
  <div id=\"overlay\" class=\"overlay\">지도를 불러오는 중입니다.</div>

  <script>
    const items = {payload};
    const overlay = document.getElementById('overlay');
    let finished = false;

    function showMessage(message) {{
      overlay.style.display = 'flex';
      overlay.innerHTML = message;
    }}

    function hideMessage() {{
      overlay.style.display = 'none';
    }}

    function addFallback(message) {{
      const div = document.createElement('div');
      div.className = 'fallback';
      div.innerHTML = message;
      document.body.appendChild(div);
    }}

    function loadKakaoSdk() {{
      return new Promise(function(resolve, reject) {{
        const script = document.createElement('script');
        script.src = 'https://dapi.kakao.com/v2/maps/sdk.js?appkey={kakao_key}&libraries=services&autoload=false';
        script.onload = function() {{ resolve(); }};
        script.onerror = function() {{ reject(new Error('SDK_LOAD_FAILED')); }};
        document.head.appendChild(script);
      }});
    }}

    function initMap() {{
      if (!window.kakao || !kakao.maps) {{
        showMessage('카카오 지도 SDK를 불러오지 못했습니다.<br/>카카오 개발자 콘솔의 Web 플랫폼 도메인을 확인해주세요.');
        return;
      }}

      kakao.maps.load(function () {{
        const defaultCenter = new kakao.maps.LatLng(36.5, 127.8);
        const map = new kakao.maps.Map(document.getElementById('map'), {{
          center: defaultCenter,
          level: 12
        }});

        const geocoder = new kakao.maps.services.Geocoder();
        const bounds = new kakao.maps.LatLngBounds();
        let successCount = 0;
        let doneCount = 0;
        let activeInfoWindow = null;

        function closeActiveInfoWindow() {{
          if (activeInfoWindow) {{
            activeInfoWindow.close();
            activeInfoWindow = null;
          }}
        }}

        kakao.maps.event.addListener(map, 'click', closeActiveInfoWindow);
        kakao.maps.event.addListener(map, 'dragstart', closeActiveInfoWindow);
        kakao.maps.event.addListener(map, 'zoom_changed', closeActiveInfoWindow);

        if (!items.length) {{
          finished = true;
          showMessage('표시할 매물이 없습니다.');
          return;
        }}

        function finishOne() {{
          doneCount += 1;
          if (doneCount >= items.length) {{
            finished = true;
            hideMessage();
            if (successCount > 0) {{
              map.setBounds(bounds);
              if (successCount === 1) map.setLevel(7);
            }} else {{
              showMessage('주소를 좌표로 변환하지 못했습니다.<br/>아래 매물 카드의 카카오맵 버튼을 이용해주세요.');
            }}
          }}
        }}

        items.forEach(function (item) {{
          const address = item.address || '';
          if (!address) {{
            finishOne();
            return;
          }}

          geocoder.addressSearch(address, function (result, status) {{
            if (status === kakao.maps.services.Status.OK && result && result[0]) {{
              const latlng = new kakao.maps.LatLng(result[0].y, result[0].x);
              bounds.extend(latlng);
              successCount += 1;

              const marker = new kakao.maps.Marker({{ map: map, position: latlng }});
              const infoHtml = '<div class=\"info\">'
                + '<div class=\"title\">' + item.title + '</div>'
                + '<div class=\"addr\">' + address + '</div>'
                + '<div class=\"meta\">' + Number(item.amountTon || 0).toLocaleString('ko-KR', {{ maximumFractionDigits: 2 }}) + '톤</div>'
                + '</div>';
              const infowindow = new kakao.maps.InfoWindow({{ content: infoHtml }});
              kakao.maps.event.addListener(marker, 'click', function () {{
                if (activeInfoWindow === infowindow) {{
                  closeActiveInfoWindow();
                  return;
                }}
                closeActiveInfoWindow();
                infowindow.open(map, marker);
                activeInfoWindow = infowindow;
              }});
            }}
            finishOne();
          }});
        }});
      }});
    }}

    setTimeout(function () {{
      if (!finished) {{
        showMessage('지도를 불러오지 못했습니다.<br/>로컬 테스트 중이라면 카카오 개발자 콘솔에 현재 주소를 Web 플랫폼 도메인으로 등록해야 합니다.');
      }}
    }}, 8000);

    loadKakaoSdk().then(initMap).catch(function () {{
      showMessage('카카오 지도 SDK 로딩에 실패했습니다.<br/>네트워크 또는 Web 플랫폼 도메인 설정을 확인해주세요.');
    }});
  </script>
</body>
</html>"""
    return Response(html, mimetype="text/html; charset=utf-8")


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

    data = request.get_json(force=True, silent=True) or {}
    msg = data.get("message", "")

    # 기업 제안 가격(총액, 원) — 필수
    offer = data.get("offer_price")
    try:
        offer = int(offer) if offer not in (None, "") else None
    except (TypeError, ValueError):
        offer = None
    if not offer or offer <= 0:
        return jsonify({"ok": False, "사유": "제안 가격(원)을 입력하세요."}), 400

    pr = PurchaseRequest(listing_id=listing_id, company_id=current_user.id,
                         message=str(msg).strip()[:500], offer_price=offer)
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
        # 직거래 방지를 위해 수락 이후에도 농가 연락처는 공개하지 않는다.
        # 실제 연락/정산은 부가새 에스크로 흐름 안에서 처리한다.
        d["farmer_phone"] = None
        d["farmer_name"] = r.listing.seller.name if r.listing and r.listing.seller else None
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
        # 직거래 방지를 위해 수락 이후에도 기업 연락처는 공개하지 않는다.
        # 가상계좌도 기업 회원에게만 보여주므로 농가 응답에서는 숨긴다.
        d["company_phone"] = None
        d["virtual_account"] = None
        out.append(d)
    return jsonify({"ok": True, "requests": out})


# 기업: 내 구매 신청 삭제 (거절/삭제된 내역 정리용)
@market.route("/api/requests/<int:req_id>", methods=["DELETE"])
@login_required
def delete_request(req_id):
    pr = db.session.get(PurchaseRequest, req_id)
    if not pr or pr.company_id != current_user.id:
        return jsonify({"ok": False, "사유": "권한이 없습니다."}), 403
    listing_deleted = bool(pr.listing and pr.listing.status == "deleted")
    if pr.status not in ("rejected", "pending") and not listing_deleted:
        return jsonify({"ok": False, "사유": "진행 중인 거래 내역은 삭제할 수 없습니다."}), 400
    db.session.delete(pr)
    db.session.commit()
    return jsonify({"ok": True})


# 농가: 신청 수락 / 거절
@market.route("/api/requests/<int:req_id>/decide", methods=["POST"])
@login_required
def decide_request(req_id):
    pr = db.session.get(PurchaseRequest, req_id)
    if not pr or not pr.listing or pr.listing.user_id != current_user.id:
        return jsonify({"ok": False, "사유": "권한이 없습니다."}), 403
    if pr.status != "pending":
        return jsonify({"ok": False, "사유": "이미 처리된 신청입니다."}), 400

    data = request.get_json(force=True, silent=True) or {}
    decision = data.get("decision")
    if decision not in ("accepted", "rejected"):
        return jsonify({"ok": False, "사유": "잘못된 요청"}), 400

    if decision == "accepted":
        if not pr.offer_price or pr.offer_price <= 0:
            return jsonify({"ok": False, "사유": "제안가가 없어 수락할 수 없습니다."}), 400

        # 거래 규모별 수수료: 농민 부담분은 제안가에서 차감, 기업 부담분은 제안가에 더해 입금한다.
        fee_info = config.fee_breakdown_for(pr.listing.amount_ton, pr.offer_price)
        pr.fee = fee_info["total_fee"]
        pr.settle_amount = fee_info["settle_amount"]
        pr.virtual_account = pr.virtual_account or _make_virtual_account()
        pr.status = "accepted"
        pr.reject_reason = None

        # 거래가 시작되면 새 신청이 들어오지 않도록 매물은 거래 중 상태로 잠근다.
        # 최종 입금 확인 및 정산 완료 시점에 거래완료(done)로 전환한다.
        pr.listing.status = "trading"

        # 같은 매물의 다른 대기 신청은 자동 거절 처리한다.
        others = PurchaseRequest.query.filter(
            PurchaseRequest.listing_id == pr.listing_id,
            PurchaseRequest.id != pr.id,
            PurchaseRequest.status == "pending",
        ).all()
        for other in others:
            other.status = "rejected"
            other.reject_reason = "다른 기업과 거래가 진행 중입니다."
    else:
        pr.status = "rejected"
        pr.reject_reason = str(data.get("reason", "")).strip()[:500] or "사유 미기재"

    db.session.commit()
    return jsonify({"ok": True, "status": pr.status, "request": pr.to_dict()})


# 기업: 가상계좌 입금 표시 (데모)
@market.route("/api/requests/<int:req_id>/pay", methods=["POST"])
@login_required
def mark_paid(req_id):
    pr = db.session.get(PurchaseRequest, req_id)
    if not pr or pr.company_id != current_user.id:
        return jsonify({"ok": False, "사유": "권한이 없습니다."}), 403
    if pr.status != "accepted":
        return jsonify({"ok": False, "사유": "입금 표시가 가능한 상태가 아닙니다."}), 400
    pr.status = "paid"
    pr.paid_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True, "status": pr.status, "request": pr.to_dict()})


# 관리자: 입금/정산 거래 목록
@market.route("/api/admin/transactions")
@login_required
def admin_transactions():
    if not _admin_required():
        return jsonify({"ok": False, "사유": "관리자 권한이 필요합니다."}), 403

    status = request.args.get("status", "paid")
    q = PurchaseRequest.query
    if status and status != "all":
        q = q.filter_by(status=status)
    else:
        q = q.filter(PurchaseRequest.status.in_(["accepted", "paid", "settled"]))
    rows = q.order_by(PurchaseRequest.created_at.desc()).all()
    return jsonify({"ok": True, "transactions": [_transaction_dict(r) for r in rows]})


# 관리자: 입금 확인 및 농가 정산 완료 처리 (데모)
@market.route("/api/admin/requests/<int:req_id>/settle", methods=["POST"])
@login_required
def admin_settle(req_id):
    if not _admin_required():
        return jsonify({"ok": False, "사유": "관리자 권한이 필요합니다."}), 403

    pr = db.session.get(PurchaseRequest, req_id)
    if not pr:
        return jsonify({"ok": False, "사유": "거래를 찾을 수 없습니다."}), 404
    if pr.status != "paid":
        return jsonify({"ok": False, "사유": "입금확인 대기중인 거래만 정산할 수 있습니다."}), 400

    pr.status = "settled"
    pr.settled_at = datetime.utcnow()
    if pr.listing:
        pr.listing.status = "done"
    db.session.commit()
    return jsonify({"ok": True, "status": pr.status, "request": pr.to_dict()})
