# -*- coding: utf-8 -*-
"""
AgriLoop 부산물 예측 모델.

- data/ 에 학습용 3개 파일이 있으면  => REAL 모드 (XGBoost, 원본 노트북 로직)
- 파일이 없으면                        => SAMPLE 모드 (기준 단수 × 계수, 데모용)

두 모드의 predict() 반환 형식은 동일하므로 프론트엔드/Flask는 모드를 신경 쓰지 않습니다.
"""
import os
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
F_TABLE = os.path.join(DATA_DIR, "AgriLoop_학습표_주산지.csv")
F_RICE = os.path.join(DATA_DIR, "시군별_논벼_생산량_조곡(16년~25년).xlsx")
F_ASOS = os.path.join(DATA_DIR, "ASOS_일자료.csv")

# 미리 학습해 저장해 둔 모델 묶음. 있으면 데이터 로딩/학습 없이 이것만 불러온다.
PKL = os.path.join(os.path.dirname(__file__), "agriloop_model.pkl")

# =========================================================
# 공통 상수 (원본 노트북과 동일)
# =========================================================
ASOS_DO = {
    90: "강원도", 93: "강원도", 95: "강원도", 98: "경기도", 99: "경기도",
    100: "강원도", 101: "강원도", 102: "인천광역시", 104: "강원도", 105: "강원도",
    106: "강원도", 108: "서울특별시", 112: "인천광역시", 114: "강원도",
    115: "경상북도", 119: "경기도", 121: "강원도", 127: "충청북도",
    129: "충청남도", 130: "경상북도", 131: "충청북도", 133: "대전광역시",
    135: "충청북도", 136: "경상북도", 137: "경상북도", 138: "경상북도",
    140: "전라북도", 143: "대구광역시", 146: "전라북도", 152: "울산광역시",
    155: "경상남도", 156: "광주광역시", 159: "부산광역시", 162: "경상남도",
    165: "전라남도", 168: "전라남도", 169: "전라남도", 170: "전라남도",
    172: "전라북도", 174: "전라남도", 177: "충청남도",
    184: "제주특별자치도", 185: "제주특별자치도", 188: "제주특별자치도",
    189: "제주특별자치도", 192: "경상남도", 201: "인천광역시",
    202: "경기도", 203: "경기도", 211: "강원도", 212: "강원도",
    216: "강원도", 217: "강원도", 221: "충청북도", 226: "충청북도",
    232: "충청남도", 235: "충청남도", 236: "충청남도", 238: "충청남도",
    239: "세종특별자치시", 243: "전라북도", 244: "전라북도",
    245: "전라북도", 247: "전라북도", 248: "전라북도", 251: "전라북도",
    252: "전라남도", 253: "경상남도", 254: "전라북도", 255: "경상남도",
    257: "경상남도", 258: "전라남도", 259: "전라남도", 260: "전라남도",
    261: "전라남도", 262: "전라남도", 263: "경상남도", 264: "경상남도",
    266: "전라남도", 268: "전라남도", 271: "경상북도", 272: "경상북도",
    273: "경상북도", 276: "경상북도", 277: "경상북도", 278: "경상북도",
    279: "경상북도", 281: "경상북도", 283: "경상북도", 284: "경상남도",
    285: "경상남도", 288: "경상남도", 289: "경상남도", 294: "경상남도",
    295: "경상남도",
}

WEA = ["평균기온", "평균최고기온", "평균최저기온", "평균습도", "평균풍속",
       "누적강수", "누적일사", "누적일조"]

# 생육기간 집계 시: 앞 5개는 '평균', 뒤 3개는 '합계'
AVG_WEA = ["평균기온", "평균최고기온", "평균최저기온", "평균습도", "평균풍속"]
SUM_WEA = ["누적강수", "누적일사", "누적일조"]

# 작물별 생육기간 (mode: 'same'=같은해, 'prev'=전년부터)
CROP_PERIODS = {
    "논벼":   ("same", (5, 1),  (10, 31)),
    "겉보리": ("prev", (10, 1), (6, 30)),
    "쌀보리": ("prev", (10, 1), (6, 30)),
    "맥주보리": ("prev", (10, 1), (6, 30)),
    "옥수수": ("same", (4, 1),  (9, 30)),
    "콩":     ("same", (6, 1),  (10, 31)),
    "사과":   ("same", (3, 1),  (10, 31)),
    "배":     ("same", (3, 1),  (10, 31)),
    "감귤":   ("same", (3, 1),  (12, 31)),
}

ASOS_API_URL = "http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"

GRAINS = ["겉보리", "쌀보리", "맥주보리", "옥수수", "콩"]
FRUIT = ["사과", "배", "감귤"]

COEF = {
    "논벼": [("볏짚", 1.02), ("왕겨", 0.177)],
    "겉보리": [("보릿짚", 1.23)],
    "쌀보리": [("보릿짚", 0.662)],
    "맥주보리": [("보릿짚", 0.69)],
    "옥수수": [("옥수수대", 1.189)],
    "콩": [("콩대", 1.0), ("콩깍지", 0.417)],
    "사과": [("전정가지", 1.316)],
    "배": [("전정가지", 0.656)],
    "감귤": [("전정가지", 0.088)],
}

# 작물 코드(영문) <-> 한글명. 프론트 select value 로 영문 코드를 씁니다.
CROP_CODES = {
    "rice": "논벼",
    "barley_hull": "겉보리",
    "barley_naked": "쌀보리",
    "barley_beer": "맥주보리",
    "corn": "옥수수",
    "soybean": "콩",
    "apple": "사과",
    "pear": "배",
    "citrus": "감귤",
}
CROP_TO_CODE = {v: k for k, v in CROP_CODES.items()}

ALL_CROPS = ["논벼"] + GRAINS + FRUIT

P = dict(n_estimators=500, max_depth=4, learning_rate=0.04, subsample=0.8,
         colsample_bytree=0.8, reg_lambda=1.0, min_child_weight=3, random_state=42)

TRAIN_END = 2023
VALID_YEARS = [2024, 2025]


def norm_do(s):
    m = {"강원특별자치도": "강원도", "전북특별자치도": "전라북도", "제주도": "제주특별자치도"}
    return m.get(str(s).strip(), str(s).strip())


# =========================================================
# 모델 상태 (한 번만 로드/학습)
# =========================================================
STATE = {
    "mode": None,          # "real" | "sample"
    "ready": False,
    "main_regions": {},    # 작물 -> [도...]
    "rice_sigun": {},      # 도 -> [시군...]
    "rice_dos": [],        # 논벼 도 목록
}

# REAL 모드용 핸들
_R = {}

# -------- SAMPLE 모드 기준값 --------
SAMPLE_단수 = {  # kg/10a
    "논벼": 520, "겉보리": 350, "쌀보리": 330, "맥주보리": 360,
    "옥수수": 500, "콩": 180, "사과": 2100, "배": 2300, "감귤": 3500,
}
SAMPLE_REGIONS = {
    "논벼": ["경기도", "강원도", "충청북도", "충청남도", "전라북도", "전라남도",
            "경상북도", "경상남도"],
    "겉보리": ["전라남도", "전라북도", "경상남도", "경상북도"],
    "쌀보리": ["전라남도", "전라북도", "경상남도"],
    "맥주보리": ["전라남도", "경상남도", "경상북도"],
    "옥수수": ["강원도", "경상북도", "충청북도"],
    "콩": ["전라남도", "경상북도", "충청남도", "강원도"],
    "사과": ["경상북도", "충청북도", "경상남도", "전라북도"],
    "배": ["전라남도", "충청남도", "경기도", "울산광역시"],
    "감귤": ["제주특별자치도"],
}
SAMPLE_SIGUN = {
    "전라북도": ["김제시", "익산시", "정읍시", "군산시", "부안군"],
    "전라남도": ["해남군", "나주시", "영광군", "고흥군", "장흥군"],
    "충청남도": ["당진시", "서산시", "논산시", "부여군", "예산군"],
    "경상북도": ["상주시", "안동시", "의성군", "예천군", "영주시"],
    "경상남도": ["진주시", "합천군", "창녕군", "밀양시"],
    "충청북도": ["청주시", "충주시", "음성군"],
    "경기도": ["이천시", "여주시", "평택시", "안성시"],
    "강원도": ["철원군", "원주시", "강릉시"],
}


# =========================================================
# REAL 모드 로딩/학습 (원본 노트북 로직)
# =========================================================
def _read_csv_smart(path):
    try:
        return pd.read_csv(path)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="cp949")


def _clean_num(v):
    if pd.isna(v):
        return np.nan
    if isinstance(v, str):
        v = v.strip().replace(",", "")
        if v in ("", "-", "nan", "NaN"):
            return np.nan
    return pd.to_numeric(v, errors="coerce")


def _make_rice_table(records):
    out = pd.DataFrame(records, columns=["도", "시군", "연도", "metric", "값"])
    out = out.pivot_table(index=["도", "시군", "연도"], columns="metric",
                          values="값", aggfunc="first").reset_index()
    out = out.dropna(subset=["단수"])
    out = out.query("면적 > 0 and 단수 > 0")
    return out


def _load_real():
    from xgboost import XGBRegressor

    # --- 도 단위 작물 테이블 ---
    df = _read_csv_smart(F_TABLE)
    df["도"] = df["도"].apply(norm_do)
    if "누적일사" in df.columns:
        df.loc[df["누적일사"] == 0, "누적일사"] = np.nan
    df = df.sort_values(["작물", "도", "연도"])
    df["전년단수"] = df.groupby(["작물", "도"])["단수"].shift(1)
    main_regions = {c: sorted(df[df["작물"] == c]["도"].unique())
                    for c in GRAINS + FRUIT}

    # --- 논벼 시군 데이터 ---
    raw = pd.read_excel(F_RICE, header=None)
    yrs, labs = raw.iloc[0], raw.iloc[1]
    d = raw.iloc[2:].reset_index(drop=True)
    d[0] = d[0].ffill()

    rec_city, rec_total = [], []
    for _, r in d.iterrows():
        sido, se = r[0], r[1]
        if not isinstance(se, str):
            continue
        if str(sido).strip() == "전국":
            continue
        do = norm_do(sido)
        se = se.strip()
        if se == "소계":
            target, sg = rec_total, f"{do} 전체"
        else:
            target, sg = rec_city, se
        for c in range(2, raw.shape[1]):
            lab = labs[c]
            if not isinstance(lab, str) or ":" not in lab:
                continue
            rest = lab.split(":", 1)[1]
            if "면적" in rest:
                mt = "면적"
            elif "10a" in rest:
                mt = "단수"
            elif "생산량" in rest:
                mt = "생산량"
            else:
                continue
            try:
                yr = int(float(yrs[c]))
            except Exception:
                continue
            target.append((do, sg, yr, mt, _clean_num(r[c])))

    rice = _make_rice_table(rec_city)
    rice_total = _make_rice_table(rec_total)

    # --- ASOS 날씨 ---
    a = _read_csv_smart(F_ASOS)
    a["일시"] = pd.to_datetime(a["일시"], errors="coerce")
    a["연도"] = a["일시"].dt.year
    a["월"] = a["일시"].dt.month
    a["도"] = a["지점번호"].map(ASOS_DO)
    a = a.rename(columns={
        "평균기온(°C)": "기온", "최고기온(°C)": "최고기온", "최저기온(°C)": "최저기온",
        "평균상대습도(%)": "습도", "평균풍속(m/s)": "풍속", "일강수량(mm)": "강수",
        "합계일사량(MJ/m²)": "일사", "합계일조시간(hr)": "일조",
    })
    sub = a[a["월"].isin([5, 6, 7, 8, 9, 10])].copy()
    g = sub.groupby(["지점번호", "도", "연도"])
    st = (g[["기온", "최고기온", "최저기온", "습도", "풍속"]].mean()
          .join(g[["강수", "일사", "일조"]].sum(min_count=1)).reset_index())
    st = st.rename(columns={"강수": "누적강수", "일사": "누적일사", "일조": "누적일조"})
    W = (st.groupby(["도", "연도"])[
            ["기온", "최고기온", "최저기온", "습도", "풍속",
             "누적강수", "누적일사", "누적일조"]].mean().reset_index()
         .rename(columns={"기온": "평균기온", "최고기온": "평균최고기온",
                          "최저기온": "평균최저기온", "습도": "평균습도",
                          "풍속": "평균풍속"}))

    # --- 평년값(CLIMO) 일별 테이블: 도 × (월,일) 평균 ---
    # 미래 연도 예측 시 '아직 안 온 날'을 이 값으로 채운다. (서버는 이것만 있으면 됨)
    ad = a.copy()
    ad["월"] = ad["일시"].dt.month
    ad["일"] = ad["일시"].dt.day
    ad = ad.rename(columns={
        "기온": "평균기온", "최고기온": "평균최고기온", "최저기온": "평균최저기온",
        "습도": "평균습도", "풍속": "평균풍속",
        "강수": "누적강수", "일사": "누적일사", "일조": "누적일조",
    })
    ad["누적강수"] = ad["누적강수"].fillna(0)
    climo_daily = ad.groupby(["도", "월", "일"])[WEA].mean().reset_index()

    # --- 날씨 병합 ---
    rice = rice.merge(W, on=["도", "연도"], how="left")
    rice.loc[rice["누적일사"] == 0, "누적일사"] = np.nan
    rice = rice.sort_values(["도", "시군", "연도"])
    rice["전년단수"] = rice.groupby(["도", "시군"])["단수"].shift(1)

    rice_total = rice_total.merge(W, on=["도", "연도"], how="left")
    rice_total.loc[rice_total["누적일사"] == 0, "누적일사"] = np.nan
    rice_total = rice_total.sort_values(["도", "연도"])
    rice_total["전년단수"] = rice_total.groupby(["도"])["단수"].shift(1)

    # --- 학습 ---
    gd_all = df[df["작물"].isin(GRAINS)].dropna(subset=["전년단수", "평균기온"]).copy()
    gd_train = gd_all[gd_all["연도"] <= TRAIN_END].copy()
    Xg_train = pd.concat([gd_train[WEA + ["전년단수", "연도"]],
                          pd.get_dummies(gd_train[["도", "작물"]],
                                         prefix=["도", "작물"])], axis=1)
    GCOLS = list(Xg_train.columns)
    grain_model = XGBRegressor(**P).fit(Xg_train, gd_train["단수"].values)

    rm_all = rice.dropna(subset=["전년단수", "평균기온"]).copy()
    rm_train = rm_all[rm_all["연도"] <= TRAIN_END].copy()
    rm_train["시군"] = rm_train["시군"].astype("category")
    RCOLS = WEA + ["전년단수", "연도", "시군"]
    rice_model = XGBRegressor(**P, enable_categorical=True, tree_method="hist").fit(
        rm_train[RCOLS], rm_train["단수"].values)
    RICE_CATS = list(rm_train["시군"].cat.categories)

    rt_all = rice_total.dropna(subset=["전년단수", "평균기온"]).copy()
    rt_train = rt_all[rt_all["연도"] <= TRAIN_END].copy()
    rt_train["도"] = rt_train["도"].astype("category")
    RTCOLS = WEA + ["전년단수", "연도", "도"]
    rice_total_model = XGBRegressor(**P, enable_categorical=True, tree_method="hist").fit(
        rt_train[RTCOLS], rt_train["단수"].values)
    RICE_DO_CATS = list(rt_train["도"].cat.categories)

    _R.update(dict(
        df=df, rice=rice, rice_total=rice_total,
        grain_model=grain_model, GCOLS=GCOLS,
        rice_model=rice_model, RCOLS=RCOLS, RICE_CATS=RICE_CATS,
        rice_total_model=rice_total_model, RTCOLS=RTCOLS, RICE_DO_CATS=RICE_DO_CATS,
        climo_daily=climo_daily,
        hist_max_year=int(max(int(df["연도"].max()),
                              int(rice_total["연도"].max()))),
    ))

    STATE["main_regions"] = main_regions
    STATE["rice_dos"] = sorted(rice_total["도"].unique())
    STATE["rice_sigun"] = {
        do: sorted(rice[rice["도"] == do]["시군"].dropna().unique())
        for do in STATE["rice_dos"]
    }


# =========================================================
# 실시간 ASOS(실측) + 평년(CLIMO) 날씨 엔진
#   - 생육기간 중 '지난 날'은 기상청 ASOS API 실측
#   - '아직 안 온 날'은 pkl 안의 평년 테이블로 보완
# =========================================================
from datetime import date, datetime, timedelta

_WX_CACHE = {}            # (도, start, end, 날짜키) -> 실측 daily DataFrame
_LAST_WX_INFO = {}        # 직전 예측의 날씨 처리 정보 (응답에 표시용)
_LIVE_ENABLED = True      # False면 미래 연도라도 실시간 ASOS를 쓰지 않음(지역 비교용)


def _service_key():
    """ASOS 인증키: 환경변수 우선, 없으면 config 기본값."""
    try:
        import config
        return getattr(config, "ASOS_SERVICE_KEY", None)
    except Exception:
        return os.environ.get("ASOS_SERVICE_KEY")


def _kst_now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Seoul"))
    except Exception:
        return datetime.utcnow() + timedelta(hours=9)


def _asos_available_end(now=None):
    """ASOS 일자료는 전일(D-1)까지, 보통 11시 이후 제공."""
    now = now or _kst_now()
    if now.hour >= 11:
        return now.date() - timedelta(days=1)
    return now.date() - timedelta(days=2)


def _crop_period(작물, 연도):
    mode, (sm, sd), (em, ed) = CROP_PERIODS[작물]
    if mode == "prev":
        return date(int(연도) - 1, sm, sd), date(int(연도), em, ed)
    return date(int(연도), sm, sd), date(int(연도), em, ed)


def _station_ids_for_do(도):
    도 = norm_do(도)
    return sorted([int(k) for k, v in ASOS_DO.items() if norm_do(v) == 도])


def _fetch_asos_station(stn_id, start_date, end_date, key, num_rows=999):
    import requests
    items_all, page = [], 1
    while True:
        params = {
            "serviceKey": key, "dataType": "JSON", "dataCd": "ASOS",
            "dateCd": "DAY", "startDt": start_date.strftime("%Y%m%d"),
            "endDt": end_date.strftime("%Y%m%d"), "stnIds": str(stn_id),
            "numOfRows": str(num_rows), "pageNo": str(page),
        }
        r = requests.get(ASOS_API_URL, params=params, timeout=20)
        r.raise_for_status()
        resp = r.json().get("response", {})
        code = str(resp.get("header", {}).get("resultCode", ""))
        if code not in ("00", "0", "NORMAL_SERVICE"):
            raise RuntimeError(f"ASOS API code={code}")
        body = resp.get("body", {})
        total = int(body.get("totalCount", 0) or 0)
        items = body.get("items", {}).get("item", [])
        if isinstance(items, dict):
            items = [items]
        items_all.extend(items)
        if page * num_rows >= total or not items:
            break
        page += 1

    if not items_all:
        return pd.DataFrame(columns=["일시"] + WEA)

    out = pd.DataFrame(items_all).rename(columns={
        "tm": "일시", "avgTa": "평균기온", "maxTa": "평균최고기온",
        "minTa": "평균최저기온", "avgRhm": "평균습도", "avgWs": "평균풍속",
        "sumRn": "누적강수", "sumGsr": "누적일사", "sumSsHr": "누적일조",
    })
    out["일시"] = pd.to_datetime(out["일시"], errors="coerce")
    for c in WEA:
        if c not in out.columns:
            out[c] = np.nan
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out["누적강수"] = out["누적강수"].fillna(0)
    return out[["일시"] + WEA]


def _asos_actual_daily(도, start_date, end_date, key):
    """도 단위 실측 일별 날씨(지점 평균). 메모리 캐시 사용."""
    도 = norm_do(도)
    if end_date < start_date:
        return pd.DataFrame(columns=["일시"] + WEA)
    ck = (도, start_date.isoformat(), end_date.isoformat(),
          _kst_now().strftime("%Y%m%d%H"))
    if ck in _WX_CACHE:
        return _WX_CACHE[ck]

    frames = []
    for stn in _station_ids_for_do(도):
        try:
            one = _fetch_asos_station(stn, start_date, end_date, key)
            if not one.empty:
                frames.append(one)
        except Exception as e:
            print(f"[ASOS] 지점 {stn} 실패: {e}")
    if frames:
        allrows = pd.concat(frames, ignore_index=True)
        daily = allrows.groupby("일시")[WEA].mean().reset_index()
    else:
        daily = pd.DataFrame(columns=["일시"] + WEA)
    _WX_CACHE[ck] = daily
    return daily


def _climo_daily_range(도, start_date, end_date):
    """평년 테이블에서 [start,end] 구간의 일별 평년값."""
    도 = norm_do(도)
    if end_date < start_date:
        return pd.DataFrame(columns=["일시"] + WEA)
    climo = _R["climo_daily"]
    climo = climo[climo["도"] == 도]
    if climo.empty:
        return pd.DataFrame(columns=["일시"] + WEA)
    tgt = pd.DataFrame({"일시": pd.date_range(start_date, end_date, freq="D")})
    tgt["월"] = tgt["일시"].dt.month
    tgt["일"] = tgt["일시"].dt.day
    out = tgt.merge(climo, on=["월", "일"], how="left")
    return out[["일시"] + WEA]


def _aggregate_period(daily):
    if daily is None or daily.empty:
        return None
    row = {}
    for c in AVG_WEA:
        row[c] = float(pd.to_numeric(daily[c], errors="coerce").mean())
    for c in SUM_WEA:
        row[c] = float(pd.to_numeric(daily[c], errors="coerce").sum(min_count=1))
    return pd.Series(row)


def _live_weather(도, 작물, 연도):
    """미래/현재 연도용 날씨 Series 생성. 실패 시 None.
    처리 정보는 _LAST_WX_INFO 에 기록."""
    global _LAST_WX_INFO
    도 = norm_do(도)
    try:
        start, end = _crop_period(작물, 연도)
    except Exception:
        return None

    key = _service_key()
    today = _kst_now().date()
    api_end = _asos_available_end()
    actual_start = start
    actual_end = min(end, api_end)

    actual = pd.DataFrame(columns=["일시"] + WEA)
    actual_note = "실측없음"
    if key and str(key).strip() and actual_end >= actual_start and today >= actual_start:
        try:
            actual = _asos_actual_daily(도, actual_start, actual_end, key)
            if not actual.empty:
                actual_note = f"{actual_start:%Y-%m-%d}~{actual_end:%Y-%m-%d} 실측"
        except Exception as e:
            print(f"[ASOS] 실측 수집 실패 → 평년만 사용: {e}")

    climo_start = (actual_end + timedelta(days=1)) if not actual.empty else start
    climo = _climo_daily_range(도, climo_start, end)
    climo_note = (f"{climo_start:%Y-%m-%d}~{end:%Y-%m-%d} 평년"
                  if not climo.empty else "평년없음")

    combined = pd.concat([actual, climo], ignore_index=True)
    wx = _aggregate_period(combined)
    if wx is None:
        _LAST_WX_INFO = {"방식": "날씨생성실패"}
        return None

    method = ("실측+평년" if not actual.empty and not climo.empty
              else "실측" if not actual.empty else "평년")
    _LAST_WX_INFO = {
        "방식": method,
        "생육기간": f"{start:%Y-%m-%d}~{end:%Y-%m-%d}",
        "실측구간": actual_note,
        "평년구간": climo_note,
        "실측일수": int(actual["일시"].nunique()) if not actual.empty else 0,
        "평년일수": int(climo["일시"].nunique()) if not climo.empty else 0,
    }
    return wx


def _is_future(연도):
    return _LIVE_ENABLED and int(연도) > int(_R.get("hist_max_year", 9999))


# =========================================================
# REAL 모드 예측 헬퍼 (원본 노트북 로직 일부)
# =========================================================
def _lag(도, 작물, 연도):
    df = _R["df"]
    s = df[(df["도"] == 도) & (df["작물"] == 작물) & (df["연도"] == 연도 - 1)]
    if not s.empty:
        return float(s.iloc[0]["단수"])
    cand = df[(df["도"] == 도) & (df["작물"] == 작물) & (df["연도"] < 연도)] \
        .dropna(subset=["단수"]).sort_values("연도")
    return None if cand.empty else float(cand.iloc[-1]["단수"])


def _weather_row(도, 작물, 연도):
    df = _R["df"]
    # 미래 연도(학습표 이후) -> 실시간 ASOS + 평년
    if _is_future(연도):
        wx = _live_weather(도, 작물, 연도)
        if wx is not None:
            return wx
    src = df[(df["도"] == 도) & (df["작물"] == 작물) & (df["연도"] == 연도)]
    if not src.empty:
        return src.iloc[0]
    # 학습표에 없는 연도 -> 해당 도/작물의 최근 연도 날씨로 근사
    src = df[(df["도"] == 도) & (df["작물"] == 작물)].dropna(subset=["평균기온"]) \
        .sort_values("연도")
    return None if src.empty else src.iloc[-1]


def _rice_weather(도, 연도):
    rt, rc = _R["rice_total"], _R["rice"]
    # 미래 연도 -> 실시간 ASOS + 평년
    if _is_future(연도):
        wx = _live_weather(도, "논벼", 연도)
        if wx is not None:
            return wx
    s = rt[(rt["도"] == 도) & (rt["연도"] == 연도)]
    if not s.empty:
        return s.iloc[0]
    s = rt[(rt["도"] == 도)].dropna(subset=["평균기온"]).sort_values("연도")
    if not s.empty:
        return s.iloc[-1]
    s = rc[(rc["도"] == 도)].dropna(subset=["평균기온"]).sort_values("연도")
    return None if s.empty else s.iloc[-1]


def _rice_city_lag(도, 시군, 연도):
    rc = _R["rice"]
    s = rc[(rc["도"] == 도) & (rc["시군"] == 시군) & (rc["연도"] == 연도 - 1)]
    if not s.empty:
        return float(s.iloc[0]["단수"])
    cand = rc[(rc["도"] == 도) & (rc["시군"] == 시군) & (rc["연도"] < 연도)] \
        .dropna(subset=["단수"]).sort_values("연도")
    return None if cand.empty else float(cand.iloc[-1]["단수"])


def _rice_total_lag(도, 연도):
    rt = _R["rice_total"]
    s = rt[(rt["도"] == 도) & (rt["연도"] == 연도 - 1)]
    if not s.empty:
        return float(s.iloc[0]["단수"])
    cand = rt[(rt["도"] == 도) & (rt["연도"] < 연도)] \
        .dropna(subset=["단수"]).sort_values("연도")
    return None if cand.empty else float(cand.iloc[-1]["단수"])


def _predict_rice_city_real(도, 시군, 연도):
    w = _rice_weather(도, 연도)
    lag = _rice_city_lag(도, 시군, 연도)
    if w is None:
        return None, "날씨없음"
    if lag is None:
        return None, "시군 전년단수없음"
    if 시군 not in _R["RICE_CATS"]:
        return None, "미학습시군"
    row = {**{k: w[k] for k in WEA}, "전년단수": lag, "연도": 연도, "시군": 시군}
    X = pd.DataFrame([row])[_R["RCOLS"]]
    X["시군"] = pd.Categorical(X["시군"], categories=_R["RICE_CATS"])
    return float(_R["rice_model"].predict(X)[0]), "시군모델"


def _predict_rice_total_real(도, 연도):
    w = _rice_weather(도, 연도)
    lag = _rice_total_lag(도, 연도)
    if w is None:
        return None, "날씨없음"
    if lag is None:
        return None, "도전체 전년단수없음"
    if 도 not in _R["RICE_DO_CATS"]:
        return None, "도전체 모델 미학습지역"
    row = {**{k: w[k] for k in WEA}, "전년단수": lag, "연도": 연도, "도": 도}
    X = pd.DataFrame([row])[_R["RTCOLS"]]
    X["도"] = pd.Categorical(X["도"], categories=_R["RICE_DO_CATS"])
    return float(_R["rice_total_model"].predict(X)[0]), "도전체모델"


def _predict_yield_real(도, 작물, 연도, 시군=None):
    if 작물 == "논벼":
        if 시군:
            pred, via = _predict_rice_city_real(도, 시군, 연도)
            if pred is not None:
                return pred, via
            pred2, via2 = _predict_rice_total_real(도, 연도)
            if pred2 is not None:
                return pred2, f"{via2}(시군자료없음)"
            return None, via
        return _predict_rice_total_real(도, 연도)

    main = STATE["main_regions"]
    if 작물 in main and 도 not in main[작물]:
        return None, "주산지아님"

    lag = _lag(도, 작물, 연도)
    if 작물 in FRUIT:
        return (lag, "전년값") if lag is not None else (None, "전년단수없음")

    w = _weather_row(도, 작물, 연도)
    if w is None:
        return None, "날씨없음"
    if lag is None:
        return None, "전년단수없음"
    row = {c: 0 for c in _R["GCOLS"]}
    for k in WEA:
        row[k] = w[k]
    row["전년단수"] = lag
    row["연도"] = 연도
    if f"도_{도}" in row:
        row[f"도_{도}"] = 1
    if f"작물_{작물}" in row:
        row[f"작물_{작물}"] = 1
    X = pd.DataFrame([row])[_R["GCOLS"]]
    return float(_R["grain_model"].predict(X)[0]), "도모델"


def _actual_yield_real(도, 작물, 연도, 시군=None):
    if 작물 == "논벼":
        if 시군:
            s = _R["rice"][(_R["rice"]["도"] == 도) & (_R["rice"]["시군"] == 시군)
                           & (_R["rice"]["연도"] == 연도)]
            if not s.empty:
                return float(s.iloc[0]["단수"])
        s = _R["rice_total"][(_R["rice_total"]["도"] == 도)
                             & (_R["rice_total"]["연도"] == 연도)]
        return None if s.empty else float(s.iloc[0]["단수"])
    df = _R["df"]
    s = df[(df["도"] == 도) & (df["작물"] == 작물) & (df["연도"] == 연도)]
    return None if s.empty else float(s.iloc[0]["단수"])


# =========================================================
# SAMPLE 모드 예측
# =========================================================
def _predict_yield_sample(도, 작물, 연도, 시군=None):
    regions = SAMPLE_REGIONS.get(작물, [])
    if 작물 != "논벼" and regions and 도 not in regions:
        return None, "주산지아님"
    base = SAMPLE_단수.get(작물)
    if base is None:
        return None, "미지원작물"
    # 지역·연도로 약간의 변동을 줘서 결과가 단조롭지 않게.
    seed = (hash((도, str(시군), 작물, int(연도))) % 1000) / 1000.0
    factor = 0.90 + seed * 0.20  # 0.90 ~ 1.10
    via = "샘플(시군)" if 시군 else "샘플(도전체)" if 작물 == "논벼" else "샘플(도)"
    return base * factor, via


# =========================================================
# 공개 API
# =========================================================
def load_and_train():
    """앱 시작 시 1회 호출.
    1) agriloop_model.pkl 이 있으면 그걸 불러옴 (배포 서버용, 가장 빠름)
    2) 없으면 data/ 파일로 학습 (REAL)
    3) 그것도 없으면 SAMPLE 데모
    """
    if STATE["ready"]:
        return STATE["mode"]

    # 1) 미리 저장된 모델이 있으면 그것만 로드
    if os.path.exists(PKL):
        try:
            import pickle
            with open(PKL, "rb") as f:
                bundle = pickle.load(f)
            _R.update(bundle["_R"])
            STATE.update(bundle["STATE"])
            STATE["ready"] = True
            print(f"[model] 저장된 모델 불러옴: {os.path.basename(PKL)}")
            return STATE["mode"]
        except Exception as e:
            print(f"[model] pkl 로딩 실패 → 데이터로 재학습 시도: {e}")

    # 2) data/ 파일로 학습
    have_files = all(os.path.exists(p) for p in (F_TABLE, F_RICE, F_ASOS))
    if have_files:
        try:
            _load_real()
            STATE["mode"] = "real"
        except Exception as e:  # 데이터 형식 문제 시 샘플로 폴백
            print(f"[model] REAL 로딩 실패 → SAMPLE 모드로 전환: {e}")
            STATE["mode"] = "sample"
    else:
        STATE["mode"] = "sample"

    if STATE["mode"] == "sample":
        STATE["main_regions"] = {c: SAMPLE_REGIONS[c] for c in GRAINS + FRUIT}
        STATE["rice_dos"] = SAMPLE_REGIONS["논벼"]
        STATE["rice_sigun"] = {
            do: SAMPLE_SIGUN.get(do, [f"{do} 1시", f"{do} 2군"])
            for do in SAMPLE_REGIONS["논벼"]
        }

    STATE["ready"] = True
    return STATE["mode"]


def get_mode():
    return STATE["mode"]


def list_options():
    """프론트 드롭다운용 옵션."""
    crops = [{"code": CROP_TO_CODE[c], "name": c} for c in ALL_CROPS]
    rice_regions = STATE["rice_dos"]
    other = {CROP_TO_CODE[c]: STATE["main_regions"].get(c, [])
             for c in GRAINS + FRUIT}
    return {
        "mode": STATE["mode"],
        "crops": crops,
        "rice_dos": rice_regions,
        "rice_sigun": STATE["rice_sigun"],
        "crop_regions": other,
    }


def predict(도, 작물, 면적_ha, 연도, 시군=None):
    """
    단수 예측 + 부산물 환산.
    반환: dict. 실패 시 {"ok": False, "사유": ...}
    """
    도 = norm_do(도)
    연도 = int(연도)
    면적_ha = float(면적_ha)
    시군 = (str(시군).strip() or None) if 시군 else None

    global _LAST_WX_INFO
    _LAST_WX_INFO = {}  # 이번 예측에서 실시간 날씨가 쓰이면 채워짐

    if STATE["mode"] == "real":
        단수, via = _predict_yield_real(도, 작물, 연도, 시군)
    else:
        단수, via = _predict_yield_sample(도, 작물, 연도, 시군)

    if 단수 is None:
        return {"ok": False, "사유": via,
                "주산지": STATE["main_regions"].get(작물, [])}

    생산량_톤 = 면적_ha * 단수 / 100.0  # kg/10a × ha ÷ 100 = 톤

    부산물 = []
    합계 = 0.0
    for bp, cf in COEF.get(작물, []):
        amt = 생산량_톤 * cf
        합계 += amt
        부산물.append({"이름": bp, "계수": cf, "발생량_톤": round(amt, 2)})

    result = {
        "ok": True,
        "mode": STATE["mode"],
        "도": 도, "시군": 시군, "작물": 작물, "연도": 연도, "면적_ha": 면적_ha,
        "예측단수_kg_10a": round(단수, 1),
        "예측생산량_톤": round(생산량_톤, 2),
        "예측경로": via,
        "부산물": 부산물,
        "부산물합계_톤": round(합계, 2),
    }

    if STATE["mode"] == "real":
        실제 = _actual_yield_real(도, 작물, 연도, 시군)
        if 실제 is not None:
            result["실제단수_kg_10a"] = round(실제, 1)
            result["오차율_%"] = round(abs(단수 - 실제) / 실제 * 100, 1)

    # 실시간 날씨가 쓰였으면 처리 정보 첨부
    if _LAST_WX_INFO:
        result["날씨정보"] = dict(_LAST_WX_INFO)

    return result


def rank_regions(작물, 연도, 면적_ha=10.0, top=8):
    """기업용: 해당 작물의 주산지를 예측 부산물 발생량 기준으로 정렬.
    여러 지역을 한꺼번에 비교하므로 실시간 ASOS는 끄고(최근 연도 날씨로 근사) 빠르게 처리."""
    global _LIVE_ENABLED
    prev = _LIVE_ENABLED
    _LIVE_ENABLED = False
    try:
        rows = []
        if 작물 == "논벼":
            for do in STATE["rice_dos"]:
                r = predict(do, 작물, 면적_ha, 연도, 시군=None)
                if r.get("ok"):
                    rows.append(r)
        else:
            for do in STATE["main_regions"].get(작물, []):
                r = predict(do, 작물, 면적_ha, 연도, 시군=None)
                if r.get("ok"):
                    rows.append(r)
    finally:
        _LIVE_ENABLED = prev
    rows.sort(key=lambda x: x["부산물합계_톤"], reverse=True)
    return rows[:top]
