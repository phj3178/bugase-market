// AgriLoop 프론트엔드 — Flask 백엔드(/api/*)와 통신

let OPTIONS = null;
let ME = { authenticated: false };
let LAST_PRED = null;

const won = (n) => Number(n || 0).toLocaleString("ko-KR");
const kg = (t) => Math.round((t || 0) * 1000).toLocaleString("ko-KR");

// ---------- 패널 토글 ----------
document.querySelectorAll(".toggle-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".toggle-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".demo-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.panel + "-panel").classList.add("active");
  });
});

// ---------- 옵션 로드 ----------
async function loadOptions() {
  try {
    ME = await (await fetch("/api/me")).json();
  } catch (e) { ME = { authenticated: false }; }

  const res = await fetch("/api/options");
  OPTIONS = await res.json();

  const fCrop = document.getElementById("f-crop");
  const cCrop = document.getElementById("c-crop");
  OPTIONS.crops.forEach((c) => {
    fCrop.add(new Option(c.name, c.code));
    cCrop.add(new Option(c.name, c.code));
  });

  // 연도 2017~2026
  const fYear = document.getElementById("f-year");
  const cYear = document.getElementById("c-year");
  for (let y = 2026; y >= 2017; y--) {
    fYear.add(new Option(y + "년", y));
    cYear.add(new Option(y + "년", y));
  }
  fYear.value = 2026;
  cYear.value = 2026;

  syncFarmerRegions();
  fCrop.addEventListener("change", syncFarmerRegions);
  document.getElementById("f-do").addEventListener("change", syncSigun);
}

// 작물에 따라 도 목록·시군 표시 여부 갱신
function syncFarmerRegions() {
  const code = document.getElementById("f-crop").value;
  const name = OPTIONS.crops.find((c) => c.code === code)?.name;
  const fDo = document.getElementById("f-do");
  const sigunGroup = document.getElementById("f-sigun-group");

  fDo.innerHTML = "";
  let dos = [];
  if (name === "논벼") {
    dos = OPTIONS.rice_dos;
    sigunGroup.style.display = "block";
  } else {
    dos = OPTIONS.crop_regions[code] || [];
    sigunGroup.style.display = "none";
  }
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

// ---------- 농가 예측 ----------
document.getElementById("f-submit").addEventListener("click", runFarmerPredict);

async function runFarmerPredict() {
  const card = document.getElementById("f-result");
  card.classList.add("is-loading");

  const code = document.getElementById("f-crop").value;
  const name = OPTIONS.crops.find((c) => c.code === code)?.name;
  const payload = {
    crop: code,
    do: document.getElementById("f-do").value,
    sigun: name === "논벼" ? document.getElementById("f-sigun").value : null,
    year: parseInt(document.getElementById("f-year").value),
    area_m2: parseFloat(document.getElementById("f-area").value) || 0,
  };

  try {
    const res = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    renderFarmerResult(data, name);
  } catch (e) {
    showFarmerError("서버 통신에 실패했습니다. Flask 서버가 실행 중인지 확인하세요.");
  } finally {
    card.classList.remove("is-loading");
  }
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

  // 정상 결과는 원래 레이아웃 복원이 필요할 수 있으므로 다시 구성
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
  if (data.실제단수_kg_10a !== undefined)
    via += ` · 실제 ${data.실제단수_kg_10a} kg/10a (오차율 ${data["오차율_%"]}%)`;
  if (data.날씨정보) {
    const w = data.날씨정보;
    via += `<br>🌦 날씨: ${w.방식 || ""}`;
    if (w.실측구간 && w.실측구간 !== "실측없음") via += ` · 실측 ${w.실측일수}일`;
    if (w.평년일수) via += ` · 평년 ${w.평년일수}일`;
    if (w.생육기간) via += ` (생육기간 ${w.생육기간})`;
  }
  document.getElementById("f-via").innerHTML = via;

  // 농가로 로그인했으면 '판매 등록' UI 추가
  LAST_PRED = data;
  renderSellSection(data);
}

function renderSellSection(data) {
  const out = document.getElementById("f-output");
  const box = document.createElement("div");
  box.style.marginTop = "20px";
  box.style.paddingTop = "18px";
  box.style.borderTop = "1px solid var(--line)";

  if (!ME.authenticated) {
    box.innerHTML = `<div class="tiny-note">이 부산물을 기업에 판매하시겠어요?
      <a href="/login" style="color:var(--olive);font-weight:600;">로그인</a> 후 등록할 수 있습니다.</div>`;
    out.appendChild(box);
    return;
  }
  if (ME.user_type !== "farmer") {
    box.innerHTML = `<div class="tiny-note">판매 등록은 농가 회원만 가능합니다. (현재 기업 회원)</div>`;
    out.appendChild(box);
    return;
  }

  // 부산물 선택지
  const opts = data.부산물.map((b, i) =>
    `<option value="${i}">${b.이름} — ${b.발생량_톤.toLocaleString("ko-KR")}톤</option>`).join("");
  const loc = data.시군 ? `${data.도} ${data.시군}` : data.도;

  box.innerHTML = `
    <button class="submit-btn" id="sell-open" style="margin-top:0;">이 부산물 기업에 판매 등록하기 →</button>
    <div id="sell-form" style="display:none; margin-top:16px;">
      <div class="form-group">
        <label>판매할 부산물</label>
        <select id="sell-bp">${opts}</select>
      </div>
      <div class="form-group">
        <label>수확 예정일</label>
        <input type="date" id="sell-date" />
      </div>
      <div class="form-group">
        <label>희망 가격 (원, 선택)</label>
        <input type="number" id="sell-price" placeholder="예: 3000000" />
      </div>
      <div class="form-group">
        <label>농장 위치</label>
        <input type="text" id="sell-loc" value="${loc}" placeholder="예: 전북 김제시 ○○면" />
      </div>
      <div class="form-group">
        <label>추가 설명 (선택)</label>
        <input type="text" id="sell-note" placeholder="예: 건조 완료, 상차 가능" />
      </div>
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
  btn.disabled = true;
  msg.textContent = "등록 중…";

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
        `<div class="flash-ok" style="padding:14px;border:1px solid var(--olive);border-radius:5px;
         color:var(--olive);font-size:14px;">✓ 매물이 등록되었습니다! 기업이 검색해서 볼 수 있어요.
         <br><b>${bp.이름} ${bp.발생량_톤.toLocaleString("ko-KR")}톤</b> · ${payload.farm_location || ""}</div>`;
    } else {
      msg.textContent = "등록 실패: " + (r.사유 || "오류");
      btn.disabled = false;
    }
  } catch (e) {
    msg.textContent = "서버 통신 실패";
    btn.disabled = false;
  }
}

// ---------- 기업 매칭 ----------
document.getElementById("c-submit").addEventListener("click", runCompanyMatch);

async function runCompanyMatch() {
  const code = document.getElementById("c-crop").value;
  const year = parseInt(document.getElementById("c-year").value);
  const meta = document.getElementById("c-meta");
  const box = document.getElementById("c-results");
  meta.textContent = "검색 중…";
  box.innerHTML = "";

  try {
    const res = await fetch("/api/match", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ crop: code, year: year, area_ha: 10 }),
    });
    const data = await res.json();
    renderCompanyResults(data);
  } catch (e) {
    meta.textContent = "서버 통신 실패";
  }
}

function renderCompanyResults(data) {
  const meta = document.getElementById("c-meta");
  const box = document.getElementById("c-results");
  box.innerHTML = "";

  if (!data.results || !data.results.length) {
    meta.textContent = "공급 가능 지역이 없습니다.";
    return;
  }

  const total = data.results.reduce((s, r) => s + r.부산물합계_톤, 0);
  meta.textContent = `${data.results.length}개 지역 · 예상 공급량 합계 ${total.toLocaleString("ko-KR")}톤 (10㏊ 기준)`;

  const max = data.results[0].부산물합계_톤 || 1;
  data.results.forEach((r, i) => {
    const score = Math.round((r.부산물합계_톤 / max) * 99);
    const cls = score >= 85 ? "high" : score >= 70 ? "mid" : "";
    const names = r.부산물.map((b) => b.이름).join(", ");
    const div = document.createElement("div");
    div.className = "farm-result";
    div.innerHTML = `
      <div class="score-circle ${cls}">${score}</div>
      <div class="farm-info">
        <h4>${r.도}</h4>
        <div class="details">
          <span>${names}</span>
          <span class="dot">·</span>
          <span>${r.연도}년</span>
        </div>
      </div>
      <div class="farm-amount">
        <div class="num">${Math.round(r.부산물합계_톤).toLocaleString("ko-KR")}</div>
        <div class="unit-text">톤</div>
      </div>`;
    box.appendChild(div);
  });
}

loadOptions();
