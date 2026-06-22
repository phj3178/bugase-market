# AgriLoop — 농업 부산물 AI 예측 · 농가–기업 매칭 플랫폼

농가가 입력한 재배 정보를 XGBoost 모델로 분석해 작물 단수를 예측하고,
부산물 발생계수(RPR)로 발생량·수익을 환산한 뒤, 부산물을 필요로 하는
기업·지역과 연결하는 Flask 웹 애플리케이션입니다.

업로드했던 `AgriLoop_demo.html` 은 디자인 참고용이고, 이 프로젝트는
그 디자인 위에 **실제 AI 모델을 백엔드로 붙인 동작하는 웹사이트**입니다.

---

## 1. 빠른 실행

```bash
pip install -r requirements.txt
python app.py
```

브라우저에서 http://127.0.0.1:5000 접속.

> 데이터 파일이 없으면 **샘플 데모 모드**로 바로 실행됩니다.
> (UI·매칭·수익 계산까지 전부 동작하되, 단수는 기준값 기반 임시값)

---

## 2. 진짜 AI 모델로 전환하기

`data/` 폴더에 학습용 파일 3개를 넣고 서버를 재시작하면
자동으로 **REAL 모드(XGBoost)**로 전환됩니다. 파일명은 정확히:

```
data/AgriLoop_학습표_주산지.csv
data/시군별_논벼_생산량_조곡(16년~25년).xlsx
data/ASOS_일자료.csv
```

(원래 Colab에서 쓰던 그 3개 파일입니다.)

전환 여부는 서버 실행 로그와 화면 우상단 배지로 확인할 수 있습니다.
- `AI 모델 연결됨` → REAL 모드
- `샘플 데모 모드` → 파일 미연결

### ASOS 실시간 인증키 (선택)

2026년처럼 미래 연도를 예측할 때 기상청 ASOS API로 실측 날씨를 가져옵니다.
보안을 위해 환경변수로 키를 주입하세요(없으면 평년값으로 대체):

```bash
export ASOS_SERVICE_KEY="data.go.kr_Decoding_인증키"
```

---

## 3. 구조

```
agriloop/
├── app.py              Flask 서버 (페이지 + REST API)
├── model.py            AI 모델 (원본 노트북 로직을 함수로 리팩토링)
├── config.py           부산물 단가·폐기비용 (가격은 AI가 아닌 팀 기준값)
├── requirements.txt
├── templates/index.html
├── static/style.css    (참고 HTML 디자인 그대로 사용)
├── static/app.js       프론트엔드 ↔ 백엔드 통신
└── data/               학습용 CSV/xlsx 3개를 넣는 곳
```

### API

| 메서드 | 경로            | 설명                                   |
|--------|-----------------|----------------------------------------|
| GET    | `/`             | 메인 페이지                            |
| GET    | `/api/options`  | 작물·지역·시군 드롭다운 옵션           |
| POST   | `/api/predict`  | 농가용 단수·부산물·수익 예측           |
| POST   | `/api/match`    | 기업용 주산지 공급량 랭킹              |

`/api/predict` 요청 예시:

```json
{ "crop": "rice", "do": "전라북도", "sigun": "김제시",
  "year": 2026, "area_m2": 50000 }
```

작물 코드: `rice 논벼 / barley_hull 겉보리 / barley_naked 쌀보리 /
barley_beer 맥주보리 / corn 옥수수 / soybean 콩 / apple 사과 / pear 배 / citrus 감귤`

---

## 4. 참고 사항

- 모델이 지원하는 작물은 9종(논벼·보리 3종·옥수수·콩·사과·배·감귤)입니다.
  참고 HTML에 있던 양파·마늘은 학습 데이터에 없어 제외했습니다.
- 가격(단가·폐기비용)은 `config.py`에서 자유롭게 수정하세요. AI 예측값이 아니라
  수익을 보여주기 위한 기준 시세입니다.
- 배포가 필요하면 `python app.py`(개발 서버) 대신
  `gunicorn app:app` 같은 WSGI 서버를 쓰세요.
```
```
