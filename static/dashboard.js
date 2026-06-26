// 부가새 — 기업용 원료 수급 예측 대시보드
// 데이터는 /api/dashboard 에서 매물(points)을 받아오고,
// 요약·차트·표는 프론트에서 계산한다(필터 시 전체가 함께 갱신됨).

const won = (n) => Number(n || 0).toLocaleString("ko-KR");
const round1 = (n) => Math.round((n || 0) * 10) / 10;

// 작물별 마커 색상 (없는 작물은 FALLBACK에서 순서대로)
const CROP_COLORS = {
  "논벼": "#4A5320", "옥수수": "#C9892A", "콩": "#8A6310", "사과": "#9B4A1F",
  "배": "#6B8E23", "감귤": "#E08A1E", "겉보리": "#A6761D", "쌀보리": "#7D8B3A",
  "맥주보리": "#B5872A",
};
const FALLBACK_COLORS = ["#4A5320", "#C9892A", "#9B4A1F", "#6B8E23", "#8A6310",
  "#E08A1E", "#5C6238", "#A6761D"];

// 도(道) 대표 좌표 — 주소 지오코딩 실패 시 fallback 으로 사용
const DO_COORDS = {
  "서울": [37.5665, 126.9780], "부산": [35.1796, 129.0756], "대구": [35.8714, 128.6014],
  "인천": [37.4563, 126.7052], "광주": [35.1595, 126.8526], "대전": [36.3504, 127.3845],
  "울산": [35.5384, 129.3114], "세종": [36.4800, 127.2890], "경기": [37.4138, 127.5183],
  "강원": [37.8228, 128.1555], "충청북도": [36.6357, 127.4917], "충북": [36.6357, 127.4917],
  "충청남도": [36.5184, 126.8000], "충남": [36.5184, 126.8000],
  "전라북도": [35.7175, 127.1530], "전북": [35.7175, 127.1530],
  "전라남도": [34.8161, 126.4630], "전남": [34.8161, 126.4630],
  "경상북도": [36.4919, 128.8889], "경북": [36.4919, 128.8889],
  "경상남도": [35.4606, 128.2132], "경남": [35.4606, 128.2132],
  "제주": [33.4890, 126.4983],
};

let ALL_POINTS = [];
let MAP_ON = false;       // 카카오 SDK 정상 로드 여부
let map, geocoder, infowindow;
let overlays = [];
let cropChart = null, monthChart = null;
const QUERY = new URLSearchParams(window.location.search);
const FOCUS_ID = QUERY.get("listing_id");


function colorFor(crop, idx) {
  return CROP_COLORS[crop] || FALLBACK_COLORS[idx % FALLBACK_COLORS.length];
}

function doCoords(doName) {
  if (!doName) return null;
  for (const key in DO_COORDS) {
    if (doName.indexOf(key) !== -1) return DO_COORDS[key];
  }
  return null;
}

function escapeHtml(v) {
  return String(v == null ? "" : v)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function kakaoMapUrl(addr) {
  return "https://map.kakao.com/?q=" + encodeURIComponent(addr || "");
}

function makeInfoContent(pt, region) {
  const box = document.createElement("div");
  box.className = "iw";
  box.style.boxSizing = "border-box";
  box.style.width = "260px";
  box.style.maxWidth = "260px";
  box.style.padding = "12px 13px";
  box.style.fontSize = "13px";
  box.style.lineHeight = "1.55";
  box.style.color = "#1A1A17";
  box.style.whiteSpace = "normal";
  box.style.overflowWrap = "break-word";
  box.style.wordBreak = "keep-all";

  const title = document.createElement("b");
  title.textContent = `${pt.crop || "-"} · ${pt.byproduct || "-"}`;
  title.style.display = "block";
  title.style.fontFamily = "Fraunces, serif";
  title.style.fontSize = "15px";
  title.style.lineHeight = "1.35";
  title.style.marginBottom = "6px";
  box.appendChild(title);

  const lines = [
    `${won(pt.amount_ton)}톤`,
    region || "-",
    `수확 ${pt.harvest_date || "미정"}`,
    `판매자 ${pt.seller_name || "-"}`,
  ];
  lines.forEach((text) => {
    const line = document.createElement("div");
    line.textContent = text;
    line.style.display = "block";
    line.style.marginTop = "4px";
    box.appendChild(line);
  });

  if (region) {
    const a = document.createElement("a");
    a.href = kakaoMapUrl(region);
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = "카카오맵으로 확인하기";
    a.style.display = "block";
    a.style.width = "100%";
    a.style.boxSizing = "border-box";
    a.style.marginTop = "12px";
    a.style.padding = "8px 10px";
    a.style.borderRadius = "6px";
    a.style.background = "#C9892A";
    a.style.color = "#1C1A14";
    a.style.textAlign = "center";
    a.style.textDecoration = "none";
    a.style.fontSize = "12px";
    a.style.fontWeight = "800";
    a.style.lineHeight = "1.35";
    a.style.border = "1px solid rgba(28,26,20,.16)";
    box.appendChild(a);
  }

  return box;
}


// ---------- 진입 ----------
async function initDashboard() {
  let data;
  try {
    data = await (await fetch("/api/dashboard")).json();
  } catch (e) {
    data = { ok: false };
  }
  ALL_POINTS = (data && data.ok && data.points) ? data.points : [];

  buildFilters();
  if (MAP_ON) setupMap();
  bindFilters();
  render();
}

function buildFilters() {
  const crops = [...new Set(ALL_POINTS.map((p) => p.crop).filter(Boolean))].sort();
  const dos = [...new Set(ALL_POINTS.map((p) => p.do).filter(Boolean))].sort();
  const cSel = document.getElementById("d-crop");
  const dSel = document.getElementById("d-do");
  crops.forEach((c) => cSel.add(new Option(c, c)));
  dos.forEach((d) => dSel.add(new Option(d, d)));
}

function bindFilters() {
  document.getElementById("d-crop").addEventListener("change", render);
  document.getElementById("d-do").addEventListener("change", render);
  document.getElementById("d-reset").addEventListener("click", () => {
    document.getElementById("d-crop").value = "";
    document.getElementById("d-do").value = "";
    render();
  });
}

function filteredPoints() {
  const crop = document.getElementById("d-crop").value;
  const doVal = document.getElementById("d-do").value;
  return ALL_POINTS.filter((p) =>
    (!crop || p.crop === crop) && (!doVal || p.do === doVal));
}

// ---------- 전체 렌더 ----------
function render() {
  const pts = filteredPoints();
  renderSummary(pts);
  renderLegend(pts);
  renderCropChart(pts);
  renderMonthChart(pts);
  renderTable(pts);
  if (MAP_ON) renderMarkers(pts);
}

function renderSummary(pts) {
  const count = pts.length;
  const ton = pts.reduce((s, p) => s + (p.amount_ton || 0), 0);
  const now = new Date();
  const ym = now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0");
  const monthTon = pts.reduce((s, p) => {
    if (p.harvest_date && p.harvest_date.slice(0, 7) === ym) return s + (p.amount_ton || 0);
    return s;
  }, 0);
  document.getElementById("s-count").textContent = won(count);
  document.getElementById("s-ton").textContent = won(round1(ton));
  document.getElementById("s-month").textContent = won(round1(monthTon));
}

function renderLegend(pts) {
  const crops = [...new Set(pts.map((p) => p.crop).filter(Boolean))];
  const box = document.getElementById("legend");
  box.innerHTML = "";
  crops.forEach((c, i) => {
    const el = document.createElement("div");
    el.className = "item";
    el.innerHTML = `<span class="swatch" style="background:${colorFor(c, i)}"></span>${c}`;
    box.appendChild(el);
  });
}

// ---------- 차트 ----------
function aggBy(pts, keyFn) {
  const m = {};
  pts.forEach((p) => {
    const k = keyFn(p);
    if (k == null) return;
    m[k] = (m[k] || 0) + (p.amount_ton || 0);
  });
  return m;
}

function renderCropChart(pts) {
  const agg = aggBy(pts, (p) => p.crop || "기타");
  const labels = Object.keys(agg).sort((a, b) => agg[b] - agg[a]);
  const values = labels.map((l) => round1(agg[l]));
  const colors = labels.map((l, i) => colorFor(l, i));

  if (cropChart) cropChart.destroy();
  cropChart = new Chart(document.getElementById("cropChart"), {
    type: "bar",
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderRadius: 4 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false },
        tooltip: { callbacks: { label: (c) => won(c.parsed.y) + " 톤" } } },
      scales: { y: { beginAtZero: true, ticks: { callback: (v) => won(v) } } },
    },
  });
}

function renderMonthChart(pts) {
  const agg = aggBy(pts, (p) => (p.harvest_date ? p.harvest_date.slice(0, 7) : null));
  const labels = Object.keys(agg).sort();
  const values = labels.map((l) => round1(agg[l]));
  const disp = labels.map((l) => {
    const [y, m] = l.split("-");
    return y.slice(2) + "." + parseInt(m, 10);
  });

  if (monthChart) monthChart.destroy();
  monthChart = new Chart(document.getElementById("monthChart"), {
    type: "bar",
    data: { labels: disp, datasets: [{ data: values, backgroundColor: "#C9892A", borderRadius: 4 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false },
        tooltip: { callbacks: { label: (c) => won(c.parsed.y) + " 톤" } } },
      scales: { y: { beginAtZero: true, ticks: { callback: (v) => won(v) } } },
    },
  });
}

// ---------- 표 ----------
function renderTable(pts) {
  const body = document.getElementById("table-body");
  const cnt = document.getElementById("table-count");
  const sorted = [...pts].sort((a, b) => (b.amount_ton || 0) - (a.amount_ton || 0));
  cnt.textContent = `총 ${won(pts.length)}건`;
  if (!sorted.length) {
    body.innerHTML = `<tr><td colspan="6" class="dash-empty">조건에 맞는 매물이 없습니다.</td></tr>`;
    return;
  }
  body.innerHTML = "";
  sorted.forEach((p) => {
    const region = p.farm_location || [p.do, p.sigun].filter(Boolean).join(" ") || "-";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="font-weight:600;">${p.crop || "-"}</td>
      <td>${p.byproduct || "-"}</td>
      <td class="ton">${won(p.amount_ton)} 톤</td>
      <td>${region}</td>
      <td>${p.harvest_date || "미정"}</td>
      <td>${p.seller_name || "-"}</td>`;
    body.appendChild(tr);
  });
}

// ---------- 지도 ----------
function setupMap() {
  const container = document.getElementById("map");
  map = new kakao.maps.Map(container, {
    center: new kakao.maps.LatLng(36.5, 127.8),
    level: 13,
  });
  geocoder = new kakao.maps.services.Geocoder();
  infowindow = new kakao.maps.InfoWindow({ removable: true });
}

function clearOverlays() {
  overlays.forEach((o) => o.setMap(null));
  overlays = [];
}

function placeDot(pt, latlng, color) {
  const el = document.createElement("div");
  el.className = "map-dot";
  el.style.background = color;
  el.title = `${pt.crop} ${pt.byproduct} ${won(pt.amount_ton)}톤`;

  const ov = new kakao.maps.CustomOverlay({
    position: latlng, content: el, xAnchor: 0.5, yAnchor: 0.5, zIndex: 3,
  });
  ov.setMap(map);
  overlays.push(ov);

  function openInfo() {
    const region = pt.farm_location || [pt.do, pt.sigun].filter(Boolean).join(" ") || "";
    infowindow.setContent(makeInfoContent(pt, region));
    infowindow.setPosition(latlng);
    infowindow.open(map);
  }

  el.addEventListener("click", openInfo);

  if (FOCUS_ID && String(pt.id) === String(FOCUS_ID)) {
    setTimeout(() => {
      map.setLevel(8);
      map.panTo(latlng);
      openInfo();
    }, 120);
  }
}

function fallbackPlace(pt, color) {
  const c = doCoords(pt.do);
  if (!c) return;
  // 같은 도에 여러 매물이 겹치지 않도록 약간의 흔들림 추가
  const lat = c[0] + (Math.random() - 0.5) * 0.18;
  const lng = c[1] + (Math.random() - 0.5) * 0.18;
  placeDot(pt, new kakao.maps.LatLng(lat, lng), color);
}

function renderMarkers(pts) {
  clearOverlays();
  if (infowindow) infowindow.close();
  // 작물별 색상을 전체 작물 기준으로 고정 (필터해도 색 유지)
  const allCrops = [...new Set(ALL_POINTS.map((p) => p.crop).filter(Boolean))].sort();
  pts.forEach((pt) => {
    const idx = Math.max(0, allCrops.indexOf(pt.crop));
    const color = colorFor(pt.crop, idx);
    const addr = pt.farm_location || [pt.do, pt.sigun].filter(Boolean).join(" ").trim();
    if (addr) {
      geocoder.addressSearch(addr, (result, status) => {
        if (status === kakao.maps.services.Status.OK && result[0]) {
          placeDot(pt, new kakao.maps.LatLng(result[0].y, result[0].x), color);
        } else {
          fallbackPlace(pt, color);
        }
      });
    } else {
      fallbackPlace(pt, color);
    }
  });
}

// ---------- 부팅 ----------
(function start() {
  if (typeof kakao !== "undefined" && kakao.maps && kakao.maps.load) {
    MAP_ON = true;
    kakao.maps.load(initDashboard);
  } else {
    // 카카오 키 미설정/오류 → 지도 영역만 안내, 나머지는 정상 렌더
    MAP_ON = false;
    const m = document.getElementById("map");
    const err = document.getElementById("map-error");
    if (m) m.style.display = "none";
    if (err) err.style.display = "block";
    initDashboard();
  }
})();
