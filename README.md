# 미국주식 매매 추천 시스템

시장 공포 지수와 고점 대비 낙폭, 펀더멘탈을 종합해 **매수 타이밍을 알려주는 개인용 웹 대시보드**입니다.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![Flask](https://img.shields.io/badge/Flask-3.x-green) ![PostgreSQL](https://img.shields.io/badge/DB-PostgreSQL%20%2F%20SQLite-blue) ![License](https://img.shields.io/badge/License-Personal-lightgrey)

---

## 주요 기능

### 시장 심리 지표 (5종)
| 지표 | 설명 | 데이터 소스 |
|------|------|------------|
| Fear & Greed Index | 0~100, 낮을수록 공포 구간 | CNN (Alternative.me fallback) |
| VIX | 시장 변동성 지수 | yfinance ^VIX |
| S&P500 / NASDAQ RSI | 14일 RSI, 과매도 감지 | yfinance + pandas-ta |
| CPI | 소비자물가 YoY 변화율 | FRED API |
| 장단기 금리차 | 10년-2년물 금리차, 침체 신호 | FRED API (yfinance fallback) |

### 종목 분석
- **ATH / 52주 고점 대비 낙폭** 자동 계산
- **1년 가격 차트** (MA20 / MA60 / MA120, 거래량)
- **펀더멘탈**: Forward PER, EPS 성장률, FCF, ROE, PEG
- **애널리스트 의견**: Strong Buy / Buy / Hold / Sell 비율, 목표주가
- **ETF 전용**: YTD 수익률, 3년 평균 수익률, AUM

### 매수 추천 점수
```
주식: total = 공포점수×0.3 + 낙폭점수×0.4 + 펀더멘탈×0.3 - 금리패널티
ETF:  total = 공포점수×0.5 + 낙폭점수×0.5 - 금리패널티

등급: ★ 강력 매수(70+) / 매수 고려(50+) / 관망(30+) / 매수 보류
```

### 기타
- **실시간 가격** AJAX 10초 자동 갱신 (프리/애프터마켓 포함)
- **종목 검색** 자동완성 (Yahoo Finance)
- **Watchlist** 등록/삭제 (PostgreSQL 영구 저장)

---

## 스크린샷

### 메인 대시보드
```
┌─────────────────────────────────────────────────────────┐
│  시장 심리 지표 카드 (Fear&Greed / VIX / RSI / CPI / 금리차) │
│  공포 종합 점수: 70/100 ████████░░                        │
│                                                          │
│  관심 종목 추천 순위                                        │
│  AAPL  $185.2  ATH -22%  Buy 71%  [★ 강력 매수 78점]     │
│  MSFT  $400.1  ATH -18%  Buy 85%  [★ 강력 매수 72점]     │
└─────────────────────────────────────────────────────────┘
```

---

## 시작하기

### 1. 설치

```bash
git clone https://github.com/hhs486-sudo/US_STOCK_TRADE.git
cd US_STOCK_TRADE
pip install -r requirements.txt
```

### 2. 환경변수 설정

`.env` 파일 생성:

```ini
# FRED API 키 (CPI, 금리 데이터) — 무료 발급: https://fred.stlouisfed.org/docs/api/api_key.html
FRED_API_KEY=your_fred_api_key_here

# PostgreSQL 연결 (없으면 SQLite 자동 사용)
# DATABASE_URL=postgresql://user:pass@host/db?sslmode=require

# 선택 옵션
FLASK_DEBUG=false
FLASK_PORT=5000
```

### 3. 실행

**Windows:**
```
run.bat 더블클릭
```

**또는 직접 실행:**
```bash
python app.py
```

브라우저에서 `http://localhost:5000` 접속

---

## 배포 (Render.com)

1. [Render.com](https://render.com) → New Web Service → GitHub 저장소 연결
2. 환경변수 설정:
   - `DATABASE_URL` = Neon PostgreSQL 연결 문자열
   - `FRED_API_KEY` = FRED API 키
3. 자동 배포 완료 (Procfile 포함)

**무료 PostgreSQL**: [Neon.tech](https://neon.tech) (512MB 영구 무료)

---

## 프로젝트 구조

```
Invest_US_stocks/
├── app.py                    # Flask 앱 (라우트, 병렬 API 호출)
├── config.py                 # 환경변수, 캐시 TTL 설정
├── requirements.txt
├── Procfile                  # 운영: gunicorn app:app
├── run.bat                   # 로컬 실행 스크립트
│
├── src/
│   ├── db.py                 # L1/L2 캐시, SQLite/PostgreSQL 이중 지원
│   ├── watchlist.py          # Watchlist CRUD
│   ├── market_sentiment.py   # 시장 심리 지표 수집
│   ├── stock_analysis.py     # 종목 데이터 수집 (병렬)
│   └── scoring.py            # 매수 추천 점수 산출
│
├── templates/
│   ├── base.html             # 공통 레이아웃
│   ├── index.html            # 메인 대시보드
│   ├── stock_detail.html     # 종목 상세
│   └── watchlist.html        # Watchlist 관리
│
└── docs/                     # 설계 문서
    ├── 01-plan/
    ├── 02-design/
    ├── 03-analysis/
    └── 04-report/
```

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| 백엔드 | Python 3.11+, Flask 3.x |
| 프론트엔드 | Bootstrap 5, Chart.js |
| 데이터 수집 | yfinance, requests, pandas-ta |
| 데이터베이스 | SQLite (로컬) / PostgreSQL (운영) |
| 캐시 | L1 인메모리 + L2 DB (2계층) |
| 병렬 처리 | ThreadPoolExecutor |
| 배포 | gunicorn, Render.com |

---

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | 메인 대시보드 |
| GET | `/stock/<ticker>` | 종목 상세 |
| GET | `/watchlist` | Watchlist 관리 |
| POST | `/watchlist/add` | 종목 추가 |
| POST | `/watchlist/delete` | 종목 삭제 |
| GET | `/api/prices` | 실시간 가격 JSON (AJAX) |
| GET | `/api/search?q=` | 종목 검색 |
| GET | `/api/refresh` | 캐시 초기화 |

---

## 성능

| 구분 | 응답 시간 |
|------|---------|
| 첫 요청 (캐시 미스) | ~7.6초 |
| 이후 요청 (캐시 히트) | ~1.5초 |

L1 인메모리 캐시 + 비동기 DB 쓰기 + ThreadPoolExecutor 병렬 호출로 최적화.

---

## 주의사항

> 이 도구는 **참고용 지표**를 제공합니다. 실제 투자 결정은 본인의 판단으로 하세요. 투자 손실에 대한 책임은 본인에게 있습니다.

---

## 라이선스

개인 사용 목적으로 제작되었습니다.
