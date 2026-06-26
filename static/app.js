// 부가새 서비스 페이지 — 역할별(비로그인/농가/기업) 분기

let OPTIONS = null;
let ME = { authenticated: false };
let LAST_PRED = null;

const won = (n) => Number(n || 0).toLocaleString("ko-KR");
const kg = (t) => Math.round((t || 0) * 1000).toLocaleString("ko-KR");
const PRED_YEAR = 2026; // 수확 연도 고정

// ---------- 진입점 ----------
async function boot() {
  try { ME = await (await fetch("/api/me")).json(); }
  catch (e) { ME = { authenticated: false }; }

  const gate = document.getElementById("gate");
  const farmerView = document.getElementById("farmer-view");
  const companyView = document.getElementById("company-view");
  const heading = document.getElementById("service-heading");

  // 비로그인: 농가 예측 화면을 보여주되, 예측 버튼을 누르면 로그인 요구
  if (!ME.authenticated) {
    OPTIONS = await (await fetch("/api/options")).json();
    farmerView.style.display = "block";
    heading.innerHTML = "지금 바로 <em>예측</em>해보세요";
    initFarmer();
    return;
  }

  OPTIONS = await (await fetch("/api/options")).json();

  if (ME.user_type === "farmer") {
    farmerView.style.display = "block";
    heading.innerHTML = "내 부산물 <em>등록하기</em>";
    initFarmer();
  } else {
    companyView.style.display = "block";
    heading.innerHTML = "부산물 <em>검색하기</em>";
    initCompany();
  }
}

/* ============================================================
   농가: 예측 + 판매 등록
   ============================================================ */
function initFarmer() {
  const fCrop = document.getElementById("f-crop");
  OPTIONS.crops.forEach((c) => fCrop.add(new Option(c.name, c.code)));
  syncFarmerRegions();
  fCrop.addEventListener("change", syncFarmerRegions);
  document.getElementById("f-do").addEventListener("change", syncSigun);
  document.getElementById("f-submit").addEventListener("click", runFarmerPredict);
  // 면적 단위 변경 시 안내 문구 갱신
  const unitSel = document.getElementById("f-area-unit");
  if (unitSel) {
    const notes = {
      pyeong: "평 단위로 입력하세요 · 1평 ≈ 3.3㎡ (자동 환산)",
      m2: "제곱미터(㎡)로 입력하세요 · 1㏊ = 10,000㎡ (자동 환산)",
      ha: "헥타르(㏊)로 입력하세요 · 1㏊ = 10,000㎡ = 약 3,025평",
    };
    const defaults = { pyeong: 3000, m2: 10000, ha: 1 };
    unitSel.addEventListener("change", () => {
      const u = unitSel.value;
      const note = document.getElementById("f-area-note");
      if (note) note.textContent = notes[u] || "";
      const areaInput = document.getElementById("f-area");
      if (areaInput) areaInput.value = defaults[u];
    });
  }
}

function syncFarmerRegions() {
  const code = document.getElementById("f-crop").value;
  const name = OPTIONS.crops.find((c) => c.code === code)?.name;
  const fDo = document.getElementById("f-do");
  const sigunGroup = document.getElementById("f-sigun-group");
  fDo.innerHTML = "";
  let dos = [];
  if (name === "논벼") { dos = OPTIONS.rice_dos; sigunGroup.style.display = "block"; }
  else { dos = OPTIONS.crop_regions[code] || []; sigunGroup.style.display = "none"; }
  dos.forEach((d) => fDo.add(new Option(d, d)));
  syncSigun();
}

function syncSigun() {
  const code = document.getElementById("f-crop").value;
  const name = OPTIONS.crops.find((c) => c.code === code)?.name;
  const fSigun = document.getElementById("f-sigun");
  fSigun.innerHTML = "";
  if (name !== "논벼") return;
  const doVal = document.getElementById("f-do").value;
  const list = (OPTIONS.rice_sigun[doVal] || []);
  fSigun.add(new Option("— 도 전체 —", ""));
  list.forEach((s) => fSigun.add(new Option(s, s)));
}

async function runFarmerPredict() {
  // 비로그인이면 예측을 막고 로그인/회원가입 안내
  if (!ME.authenticated) {
    showLoginPrompt();
    return;
  }

  const card = document.getElementById("f-result");
  card.classList.add("is-loading");
  const code = document.getElementById("f-crop").value;
  const name = OPTIONS.crops.find((c) => c.code === code)?.name;
  // 선택한 단위를 ㎡로 환산 (서버는 ㎡ → ㏊로 처리)
  const areaVal = parseFloat(document.getElementById("f-area").value) || 0;
  const unit = (document.getElementById("f-area-unit") || {}).value || "pyeong";
  const toM2 = { pyeong: 3.305785, m2: 1, ha: 10000 };
  const areaM2 = areaVal * (toM2[unit] || 1);
  const payload = {
    crop: code,
    do: document.getElementById("f-do").value,
    sigun: name === "논벼" ? document.getElementById("f-sigun").value : null,
    year: PRED_YEAR,
    area_m2: areaM2,
  };
  try {
    const res = await fetch("/api/predict", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    renderFarmerResult(data, name);
  } catch (e) {
    showFarmerError("서버 통신에 실패했습니다. 잠시 후 다시 시도해주세요.");
  } finally {
    card.classList.remove("is-loading");
  }
}

function showLoginPrompt() {
  document.getElementById("f-empty").style.display = "none";
  const out = document.getElementById("f-output");
  out.style.display = "block";
  out.innerHTML = `
    <div style="text-align:center; padding:32px 16px;">
      <h3 style="font-family:'Fraunces',serif; font-size:22px; margin:0 0 10px;">로그인이 필요합니다</h3>
      <p style="color:var(--olive-soft); font-size:14px; line-height:1.7; margin:0 0 24px;">
        AI 예측과 부산물 거래는 회원 전용입니다.<br>로그인하거나 회원가입 후 이용해주세요.</p>
      <div style="display:flex; gap:10px; justify-content:center;">
        <a href="/login" class="btn-primary">로그인</a>
        <a href="/signup" class="btn-ghost">회원가입</a>
      </div>
    </div>`;
}

function showFarmerError(msg) {
  document.getElementById("f-empty").style.display = "none";
  const out = document.getElementById("f-output");
  out.style.display = "block";
  out.innerHTML = `<div class="error-msg">${msg}</div>`;
}

function renderFarmerResult(data, cropName) {
  document.getElementById("f-empty").style.display = "none";
  const out = document.getElementById("f-output");

  if (!data.ok) {
    let msg = `예측을 제공할 수 없습니다 — <b>${data.사유 || "사유 미상"}</b>`;
    if (data.사유 === "주산지아님" && data.주산지?.length) {
      msg += `<br>${cropName} 주산지: ${data.주산지.join(", ")}`;
    }
    showFarmerError(msg);
    return;
  }

  out.innerHTML = `
    <h3 id="f-result-title">${data.연도}년 ${data.작물} 수확기 예측</h3>
    <div class="result-main"><span id="f-amount"></span><span class="unit">kg</span></div>
    <div class="result-sub" id="f-desc"></div>
    <div id="f-byproducts"></div>
    <div class="price-row" style="margin-top:8px;">
      <span class="key">예측 단수</span>
      <span class="val"><span id="f-yield"></span> kg/10a</span>
    </div>
    <div class="price-row">
      <span class="key">예상 총 수익</span>
      <span class="val highlight">₩ <span id="f-revenue"></span></span>
    </div>
    <div class="price-row">
      <span class="key">소각·폐기 시 비용</span>
      <span class="val" style="color: var(--rust);">- ₩ <span id="f-disposal"></span></span>
    </div>
    <div class="tiny-note" id="f-via"></div>`;
  out.style.display = "block";

  document.getElementById("f-amount").textContent = won(data.부산물합계_kg);
  const names = data.부산물.map((b) => b.이름).join(" · ");
  document.getElementById("f-desc").textContent =
    `${names} 예상 발생량 (생산량 ${data.예측생산량_톤.toLocaleString("ko-KR")}톤 기준)`;

  const bpBox = document.getElementById("f-byproducts");
  bpBox.innerHTML = "";
  data.부산물.forEach((b) => {
    const div = document.createElement("div");
    div.className = "byproduct-line";
    div.innerHTML = `<span>${b.이름} <span style="color:var(--olive-soft)">×${b.계수}</span></span>
                     <b>${kg(b.발생량_톤)} kg</b>`;
    bpBox.appendChild(div);
  });

  document.getElementById("f-yield").textContent = won(data.예측단수_kg_10a);
  document.getElementById("f-revenue").textContent = won(data.예상수익_원);
  document.getElementById("f-disposal").textContent = won(data.폐기비용_원);

  let via = `예측 경로: ${data.예측경로}`;
  if (data.mode === "sample") via += " · ⚠ 샘플 데모 모드 (data/ 파일 미연결)";
  if (data.날씨정보) {
    const w = data.날씨정보;
    via += `<br>🌦 날씨: ${w.방식 || ""}`;
    if (w.실측구간 && w.실측구간 !== "실측없음") via += ` · 실측 ${w.실측일수}일`;
    if (w.평년일수) via += ` · 평년 ${w.평년일수}일`;
    if (w.생육기간) via += ` (생육기간 ${w.생육기간})`;
  }
  document.getElementById("f-via").innerHTML = via;

  LAST_PRED = data;
  renderSellSection(data);
}

function renderSellSection(data) {
  const out = document.getElementById("f-output");
  const box = document.createElement("div");
  box.style.marginTop = "20px";
  box.style.paddingTop = "18px";
  box.style.borderTop = "1px solid var(--line)";

  const opts = data.부산물.map((b, i) =>
    `<option value="${i}">${b.이름} — ${b.발생량_톤.toLocaleString("ko-KR")}톤</option>`).join("");
  const loc = data.시군 ? `${data.도} ${data.시군}` : data.도;

  box.innerHTML = `
    <button class="submit-btn" id="sell-open" style="margin-top:0;">이 부산물 기업에 판매 등록하기 →</button>
    <div id="sell-form" style="display:none; margin-top:16px;">
      <div class="form-group"><label>판매할 부산물</label><select id="sell-bp">${opts}</select></div>
      <div class="form-group"><label>수확 예정일</label><input type="date" id="sell-date" /></div>
      <div class="form-group"><label>희망 가격 (원, 선택)</label><input type="number" id="sell-price" placeholder="예: 3000000" /></div>
      <div class="form-group"><label>농장 위치 (주소)</label>
        <input type="text" id="sell-loc" value="${loc}" placeholder="예: 전북 김제시 ○○면 ○○리" />
        <div class="tiny-note">정확한 주소를 입력하면 기업이 지도에서 위치를 확인할 수 있습니다.</div></div>
      <div class="form-group"><label>추가 설명 (선택)</label><input type="text" id="sell-note" placeholder="예: 건조 완료, 상차 가능" /></div>
      <button class="submit-btn" id="sell-submit" style="margin-top:4px;">판매 등록 완료</button>
      <div class="tiny-note" id="sell-msg"></div>
    </div>`;
  out.appendChild(box);

  document.getElementById("sell-open").addEventListener("click", () => {
    document.getElementById("sell-open").style.display = "none";
    document.getElementById("sell-form").style.display = "block";
  });
  document.getElementById("sell-submit").addEventListener("click", submitListing);
}

async function submitListing() {
  const data = LAST_PRED;
  const idx = parseInt(document.getElementById("sell-bp").value);
  const bp = data.부산물[idx];
  const msg = document.getElementById("sell-msg");
  const btn = document.getElementById("sell-submit");
  btn.disabled = true; msg.textContent = "등록 중…";

  const payload = {
    crop: data.작물, do: data.도, sigun: data.시군,
    byproduct: bp.이름, amount_ton: bp.발생량_톤,
    price_won: document.getElementById("sell-price").value || null,
    harvest_date: document.getElementById("sell-date").value || null,
    farm_location: document.getElementById("sell-loc").value || null,
    note: document.getElementById("sell-note").value || null,
  };
  try {
    const res = await fetch("/api/listings", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const r = await res.json();
    if (r.ok) {
      document.getElementById("sell-form").innerHTML =
        `<div style="padding:14px;border:1px solid var(--olive);border-radius:5px;
         color:var(--olive);font-size:14px;">✓ 매물이 등록되었습니다! 기업이 검색해서 볼 수 있어요.
         <br><b>${bp.이름} ${bp.발생량_톤.toLocaleString("ko-KR")}톤</b> · ${payload.farm_location || ""}</div>`;
    } else { msg.textContent = "등록 실패: " + (r.사유 || "오류"); btn.disabled = false; }
  } catch (e) { msg.textContent = "서버 통신 실패"; btn.disabled = false; }
}

/* ============================================================
   기업: 실제 농가 매물 검색 + 구매 신청
   ============================================================ */
function initCompany() {
  const sc = document.getElementById("mk-crop");
  OPTIONS.crops.forEach((x) => sc.add(new Option(x.name, x.name)));
  const sd = document.getElementById("mk-do");
  [...new Set([...OPTIONS.rice_dos, ...Object.values(OPTIONS.crop_regions).flat()])]
    .sort().forEach((d) => sd.add(new Option(d, d)));
  searchMarket();
}

async function searchMarket() {
  const crop = document.getElementById("mk-crop").value;
  const doval = document.getElementById("mk-do").value;
  const qs = new URLSearchParams();
  if (crop) qs.set("crop", crop);
  if (doval) qs.set("do", doval);
  const box = document.getElementById("mk-results");
  box.innerHTML = `<div class="mk-empty">불러오는 중…</div>`;
  const r = await (await fetch("/api/listings?" + qs.toString())).json();
  if (!r.listings || !r.listings.length) {
    box.innerHTML = `<div class="mk-empty">조건에 맞는 매물이 없습니다.</div>`; return;
  }
  box.innerHTML = "";
  r.listings.forEach((L) => {
    const card = document.createElement("div");
    card.className = "mk-card";
    const mapBtn = L.farm_location
      ? `<button class="mk-btn map" onclick="goDashboard(${L.id})">부산물 지도에서 보기</button>` : "";
    let actions;
    if (L.my_request_status) {
      const label = {pending:"신청함 (대기중)",accepted:"거래 중",paid:"입금 확인 대기",settled:"거래 완료",rejected:"거절됨"}[L.my_request_status] || L.my_request_status;
      actions = `<div class="mk-actions">${mapBtn}<span class="mk-badge ${L.my_request_status}">${label}</span></div>`;
    } else {
      actions = `<input class="mk-msg" id="mk-offer-${L.id}" type="number" min="1" placeholder="제안 가격 (원, 총액)" />
        <div class="mk-note" style="margin-top:8px;">수락 시 거래 규모에 따라 구매 기업 수수료가 별도로 더해집니다.</div>
        <input class="mk-msg" id="mk-msg-${L.id}" placeholder="농가에 남길 메시지 (예: 전량 구매 희망)" />
        <div class="mk-actions">${mapBtn}<button class="mk-btn" onclick="sendMarketRequest(${L.id})">구매 신청</button></div>`;
    }
    const noteHtml = L.note
      ? `<div class="mk-note">📝 ${L.note}</div>` : "";
    card.innerHTML = `
      <div class="row1"><span class="crop">${L.crop} · ${L.byproduct}</span>
        <span class="amt">${won(L.amount_ton)}톤</span></div>
      <div class="meta">${L.farm_location || L.do} · 수확 ${L.harvest_date || "미정"}
        ${L.price_won ? " · 희망가 ₩" + won(L.price_won) : " · 가격 협의"} · 판매자 ${L.seller_name}</div>
      ${noteHtml}
      ${actions}`;
    box.appendChild(card);
  });
}

function goDashboard(listingId) {
  // 서비스 밖의 새 카카오맵 창으로 바로 보내지 않고, 부가새의 부산물 지도에서 먼저 확인한다.
  location.href = "/dashboard?listing_id=" + encodeURIComponent(listingId);
}

function openMap(encodedAddr) {
  // 이전 버전 호환용: 직접 카카오맵을 여는 대신 부가새 부산물 지도로 이동한다.
  location.href = "/dashboard";
}

async function sendMarketRequest(id) {
  const msg = document.getElementById("mk-msg-" + id).value;
  const offer = document.getElementById("mk-offer-" + id).value;
  if (!offer || Number(offer) <= 0) { alert("제안 가격(원)을 입력하세요."); return; }
  const r = await (await fetch(`/api/listings/${id}/request`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: msg, offer_price: offer }),
  })).json();
  if (r.ok) { alert("구매 신청을 보냈습니다. 농가가 수락하면 가상계좌가 발급됩니다."); searchMarket(); }
  else alert("신청 실패: " + (r.사유 || "오류"));
}

boot();
