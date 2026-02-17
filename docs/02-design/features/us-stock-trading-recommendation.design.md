# 미국주식 매매 추천시스템 Design Document

> **Summary**: 관심 종목/ETF Watchlist, 시장 심리 지표, 고점 낙폭 + 펀더멘탈 기반 매수 추천 점수를 제공하는 경량 Flask 웹 대시보드
>
> **Project**: Invest_US_stocks
> **Version**: 0.1.0
> **Author**: -
> **Date**: 2026-02-17
> **Status**: Draft
> **Planning Doc**: [us-stock-trading-recommendation.plan.md](../01-plan/features/us-stock-trading-recommendation.plan.md)

---

## 1. Overview

### 1.1 Design Goals

- Flask + SQLite 기반의 단순하고 실행하기 쉬운 웹 앱
- `python app.py` 한 줄 실행 후 브라우저에서 바로 확인 가능
- 외부 API 실패 시에도 캐시 데이터로 graceful fallback
- 추천 점수의 근거를 사용자가 직관적으로 이해할 수 있도록 시각화

### 1.2 Design Principles

- **심플함 우선**: 필요한 기능만, 파일 수 최소화
- **캐싱 필수**: 외부 API 호출은 항상 SQLite에 캐싱 (Rate Limit 방지)
- **규칙 기반 점수화**: ML 없이 명확한 로직으로 해석 가능한 추천
- **개인 사용 도구**: 인증/보안보다 편의성 우선 (로컬/개인 서버 실행 가정)

---

## 2. Architecture

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                              │
│    (index.html / stock_detail.html / watchlist.html)        │
└───────────────────┬─────────────────────────────────────────┘
                    │ HTTP Request
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Flask App (app.py)                        │
│                                                             │
│  Routes:                                                    │
│  GET  /               → 메인 대시보드                         │
│  GET  /stock/<ticker> → 종목 상세                             │
│  GET  /watchlist      → Watchlist 관리 페이지                 │
│  POST /watchlist/add  → 종목 추가                             │
│  POST /watchlist/del  → 종목 삭제                             │
│  GET  /api/refresh    → 데이터 수동 갱신                       │
└──────┬────────────────┬───────────────────────────────────-─┘
       │                │
       ▼                ▼
┌─────────────┐  ┌──────────────────────────────────────────┐
│  SQLite DB  │  │           src/ Modules                   │
│  invest.db  │  │                                          │
│             │  │  market_sentiment.py  ← Fear/Greed, VIX  │
│  watchlist  │  │  stock_analysis.py    ← yfinance 데이터   │
│  cache      │  │  scoring.py           ← 추천 점수 산출    │
│  price_hist │  │  watchlist.py         ← CRUD             │
└─────────────┘  └──────────┬───────────────────────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │       External APIs          │
              │  yfinance (주가, 재무, 애널리스트)│
              │  Alternative.me (Fear&Greed)  │
              │  FRED API (CPI)               │
              └──────────────────────────────┘
```

### 2.2 데이터 흐름

```
사용자 접속
    │
    ▼
Flask Route 처리
    │
    ├─► DB 캐시 확인 ─► 캐시 유효(< 24h)? ─► Yes ─► 캐시 데이터 반환
    │                                         │
    │                                         No
    │                                         │
    │                                         ▼
    │                              External API 호출
    │                                         │
    │                              DB 캐시 저장
    │                                         │
    └─────────────────────────────────────────┘
                    │
                    ▼
             Jinja2 템플릿 렌더링
                    │
                    ▼
             브라우저에 HTML 응답
```

### 2.3 모듈 의존 관계

```
app.py
  ├── src/watchlist.py       (DB CRUD)
  ├── src/market_sentiment.py (외부 API + 캐시)
  ├── src/stock_analysis.py  (외부 API + 캐시)
  └── src/scoring.py         (순수 계산, 외부 의존 없음)
       ├── market_sentiment.py 결과 참조
       └── stock_analysis.py 결과 참조
```

---

## 3. Database Schema (SQLite)

### 3.1 watchlist 테이블

```sql
CREATE TABLE IF NOT EXISTS watchlist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT NOT NULL UNIQUE,   -- 종목 코드 (예: AAPL, SPY)
    name        TEXT,                   -- 종목명 (예: Apple Inc.)
    asset_type  TEXT DEFAULT 'stock',   -- 'stock' | 'etf'
    memo        TEXT,                   -- 사용자 메모 (선택)
    added_at    TEXT DEFAULT (datetime('now'))
);
```

### 3.2 cache 테이블

```sql
CREATE TABLE IF NOT EXISTS cache (
    key         TEXT PRIMARY KEY,       -- 캐시 키 (예: 'fear_greed', 'stock_AAPL')
    data        TEXT NOT NULL,          -- JSON 직렬화 데이터
    updated_at  TEXT DEFAULT (datetime('now'))
);
```

### 3.3 캐시 키 규칙

| 캐시 키 | 데이터 내용 | 갱신 주기 |
|--------|-----------|---------|
| `fear_greed` | Fear & Greed Index 값 및 등급 | 1시간 |
| `vix` | VIX 현재값 + 5일 종가 | 1시간 |
| `cpi` | 최근 CPI 발표값 + 추이 | 24시간 |
| `market_rsi` | S&P500, NASDAQ RSI | 1시간 |
| `stock_{ticker}` | 종목 가격, ATH, 펀더멘탈, 애널리스트 | 6시간 |

---

## 4. 모듈 상세 설계

### 4.1 `src/watchlist.py`

```python
# 함수 목록
def get_all() -> list[dict]
    """watchlist 전체 조회. [{id, ticker, name, asset_type, memo, added_at}]"""

def add(ticker: str, name: str, asset_type: str, memo: str = "") -> bool
    """종목 추가. 중복 시 False 반환"""

def delete(ticker: str) -> bool
    """종목 삭제"""

def exists(ticker: str) -> bool
    """등록 여부 확인"""
```

### 4.2 `src/market_sentiment.py`

```python
# 함수 목록
def get_fear_greed() -> dict
    """
    Returns:
        {
            "value": 23,                    # 0~100
            "label": "Extreme Fear",        # 등급 텍스트
            "color": "#e74c3c",             # 표시 색상
            "updated": "2026-02-17 09:00"
        }
    Source: https://api.alternative.me/fng/
    Cache: fear_greed, TTL 1시간
    """

def get_vix() -> dict
    """
    Returns:
        {
            "current": 22.5,
            "prev_close": 20.1,
            "change_pct": 12.0,
            "level": "high",               # 'low'(<15) | 'normal'(15~25) | 'high'(25~35) | 'extreme'(>35)
            "history": [{"date": "...", "close": ...}, ...]   # 20일
        }
    Source: yfinance ticker "^VIX"
    Cache: vix, TTL 1시간
    """

def get_market_rsi() -> dict
    """
    Returns:
        {
            "sp500":  {"rsi": 38.2, "level": "oversold"},   # oversold(<30), neutral, overbought(>70)
            "nasdaq": {"rsi": 35.1, "level": "oversold"}
        }
    Source: yfinance "^GSPC", "^IXIC" → pandas-ta RSI(14)
    Cache: market_rsi, TTL 1시간
    """

def get_cpi() -> dict
    """
    Returns:
        {
            "latest_value": 3.1,
            "latest_date": "2026-01",
            "prev_value": 3.4,
            "trend": "down",               # 'up' | 'down' | 'flat'
            "history": [{"date": "...", "value": ...}, ...]  # 12개월
        }
    Source: FRED API (series: CPIAUCSL)
    Cache: cpi, TTL 24시간
    """

def get_fear_score() -> int
    """
    종합 시장 공포 점수 (0~100, 높을수록 공포)
    산출 로직:
        score = 0
        if fear_greed["value"] < 25:  score += 40
        elif fear_greed["value"] < 40: score += 20
        if vix["current"] > 30:       score += 30
        elif vix["current"] > 25:     score += 20
        if sp500_rsi < 35:            score += 30
        elif sp500_rsi < 45:          score += 15
        return min(score, 100)
    """
```

### 4.3 `src/stock_analysis.py`

```python
# 함수 목록
def get_stock_data(ticker: str) -> dict
    """
    yfinance로 종목 데이터 수집 후 반환
    Cache: stock_{ticker}, TTL 6시간

    Returns:
        {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "current_price": 185.2,
            "currency": "USD",

            # 낙폭 관련
            "ath": 237.4,                  # 역대 최고가 (5년 데이터 기준)
            "ath_date": "2024-12-26",
            "high_52w": 220.0,             # 52주 최고가
            "ath_drawdown_pct": -22.0,     # ATH 대비 낙폭 %
            "high_52w_drawdown_pct": -15.8,

            # 펀더멘탈
            "forward_pe": 24.5,
            "trailing_pe": 28.1,
            "eps_growth_pct": 12.3,        # YoY EPS 성장률 %
            "revenue_growth_pct": 8.5,
            "free_cash_flow": 95_000_000_000,  # FCF (달러)
            "fcf_positive": True,

            # 애널리스트 의견
            "analyst_count": 38,
            "strong_buy": 15,
            "buy": 12,
            "hold": 8,
            "sell": 2,
            "strong_sell": 1,
            "buy_ratio_pct": 71.0,         # (strong_buy + buy) / total %
            "target_price_mean": 225.0,    # 평균 목표주가
            "target_upside_pct": 21.5,     # 목표주가 대비 upside %

            # 차트용 가격 이력
            "price_history": [{"date": "...", "close": ...}, ...],  # 1년

            "updated": "2026-02-17 09:00"
        }
    """

def enrich_watchlist(tickers: list[str]) -> list[dict]
    """
    Watchlist 종목 전체에 대해 get_stock_data 호출 후
    scoring.py의 점수를 추가하여 반환
    Returns: 추천 점수 기준 내림차순 정렬된 리스트
    """
```

### 4.4 `src/scoring.py`

```python
def calc_drawdown_score(ath_drawdown_pct: float) -> int:
    """
    ATH 대비 낙폭 → 점수 (0~100)
    -50% 이상:  100점
    -30%~-50%:  75점
    -20%~-30%:  50점
    -10%~-20%:  25점
    -10% 미만:   0점
    """

def calc_fundamental_score(stock_data: dict) -> int:
    """
    펀더멘탈 점수 (0~100)
    Buy 비율 > 70%:        +40점
    Forward PE < 25:       +20점  (성장주 기준; ETF는 생략)
    Forward PE < 20:       +30점
    FCF 양수:              +20점
    EPS 성장률 > 10%:      +10점
    """

def calc_recommendation_score(fear_score: int, stock_data: dict) -> dict:
    """
    최종 추천 점수 및 등급 산출

    Returns:
        {
            "total_score": 78,
            "fear_score": 60,
            "drawdown_score": 75,
            "fundamental_score": 80,
            "grade": "★ 강력 매수",      # 기준: 아래 표 참고
            "grade_color": "#27ae60",
            "reason": "시장 공포 구간 + ATH -22% + Buy 71%"  # 추천 이유 텍스트
        }

    점수 계산:
        total = fear_score * 0.3 + drawdown_score * 0.4 + fundamental_score * 0.3

    등급 기준:
        70+ : ★ 강력 매수 (green)
        50+ : 매수 고려   (light green)
        30+ : 관망        (yellow)
        30-  : 매수 보류  (gray)
    """
```

---

## 5. Flask Routes

### 5.1 Route 목록

| Method | Path | 기능 | Template |
|--------|------|------|---------|
| GET | `/` | 메인 대시보드 | `index.html` |
| GET | `/stock/<ticker>` | 종목 상세 | `stock_detail.html` |
| GET | `/watchlist` | Watchlist 관리 | `watchlist.html` |
| POST | `/watchlist/add` | 종목 추가 | redirect → `/watchlist` |
| POST | `/watchlist/delete` | 종목 삭제 | redirect → `/watchlist` |
| GET | `/api/refresh` | 캐시 강제 갱신 후 redirect `/` | - |

### 5.2 Route 상세

#### `GET /` — 메인 대시보드

```python
context = {
    "fear_greed":   get_fear_greed(),      # Fear & Greed 현재값
    "vix":          get_vix(),             # VIX 현재값
    "market_rsi":   get_market_rsi(),      # S&P500, NASDAQ RSI
    "cpi":          get_cpi(),             # 최근 CPI
    "fear_score":   get_fear_score(),      # 종합 공포 점수
    "stocks":       enrich_watchlist(tickers),  # 추천 순위 리스트
    "last_updated": ...
}
```

#### `GET /stock/<ticker>` — 종목 상세

```python
context = {
    "stock":      get_stock_data(ticker),
    "score":      calc_recommendation_score(fear_score, stock_data),
    "fear_score": get_fear_score(),
}
```

---

## 6. UI/UX 설계

### 6.1 메인 대시보드 (`index.html`)

```
┌─────────────────────────────────────────────────────────┐
│  HEADER: 미국주식 매매 추천 시스템  [Watchlist 관리] [갱신] │
├─────────────────────────────────────────────────────────┤
│  [시장 심리 지표 섹션]                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │Fear&Greed│ │   VIX    │ │S&P RSI   │ │   CPI    │    │
│  │  23      │ │  26.5    │ │  38.2    │ │  3.1%    │    │
│  │Extr.Fear │ │  HIGH    │ │Oversold  │ │  ↓ down  │    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │
│                                                          │
│  [공포 종합 점수]                                          │
│  ████████░░ 시장 공포 점수: 70 / 100 (매수 기회 구간)       │
│                                                          │
├─────────────────────────────────────────────────────────┤
│  [관심 종목 추천 순위]                         마지막 갱신: │
│  ┌─────┬──────────────┬───────┬───────┬────────┬──────┐ │
│  │순위 │ 종목          │낙폭   │Buy%   │추천점수│ 등급 │ │
│  ├─────┼──────────────┼───────┼───────┼────────┼──────┤ │
│  │  1  │ AAPL (Apple) │-22%   │ 71%   │  78점  │★강매수│ │
│  │  2  │ MSFT         │-18%   │ 85%   │  72점  │★강매수│ │
│  │  3  │ SPY (ETF)    │-15%   │  -    │  60점  │매수고려│ │
│  └─────┴──────────────┴───────┴───────┴────────┴──────┘ │
│  (종목명 클릭 → 상세 페이지)                               │
└─────────────────────────────────────────────────────────┘
```

### 6.2 종목 상세 페이지 (`stock_detail.html`)

```
┌─────────────────────────────────────────────────────────┐
│  ← 돌아가기   AAPL - Apple Inc.   $185.20  (▼-1.2%)     │
├─────────────────────────────────────────────────────────┤
│  [추천 점수 카드]                                         │
│  종합 추천 점수: 78점  ★ 강력 매수 구간                    │
│  근거: 시장 공포 구간 + ATH -22% + Buy 71%               │
│  ┌────────────────┐ ┌────────────────┐ ┌──────────────┐ │
│  │공포점수: 60/100│ │낙폭점수: 75/100│ │펀더: 80/100  │ │
│  └────────────────┘ └────────────────┘ └──────────────┘ │
├─────────────────────────────────────────────────────────┤
│  [가격 차트]                          [낙폭 정보]         │
│  1년 종가 차트 (Chart.js Line)        ATH: $237.4        │
│                                      ATH 대비: -22.0%   │
│                                      52주 고점: $220.0  │
│                                      52주 대비: -15.8%  │
├─────────────────────────────────────────────────────────┤
│  [펀더멘탈]                           [애널리스트 의견]    │
│  Forward PER:   24.5                 총 38명             │
│  EPS 성장:      +12.3%               Strong Buy: 15     │
│  FCF:           $95B (양호)          Buy: 12            │
│                                      Hold: 8            │
│                                      Sell: 2+1          │
│                                      평균 목표가: $225   │
│                                      Upside: +21.5%     │
├─────────────────────────────────────────────────────────┤
│  [외부 링크]                                              │
│  [Investing.com] [Seeking Alpha] [Yahoo Finance]        │
└─────────────────────────────────────────────────────────┘
```

### 6.3 Watchlist 관리 (`watchlist.html`)

```
┌─────────────────────────────────────────────────────────┐
│  Watchlist 관리            ← 대시보드로 돌아가기           │
├─────────────────────────────────────────────────────────┤
│  [종목 추가]                                              │
│  티커: [AAPL    ] 유형: [Stock▼] 메모: [          ] [추가]│
├─────────────────────────────────────────────────────────┤
│  [등록 종목 목록]                                         │
│  ┌──────────────┬──────┬──────────────┬────────┐        │
│  │ 종목명        │ 유형 │ 메모          │        │        │
│  ├──────────────┼──────┼──────────────┼────────┤        │
│  │ AAPL         │Stock │ 장기 보유     │ [삭제] │        │
│  │ SPY          │ ETF  │ S&P500 ETF   │ [삭제] │        │
│  └──────────────┴──────┴──────────────┴────────┘        │
└─────────────────────────────────────────────────────────┘
```

---

## 7. 외부 데이터 소스 상세

### 7.1 Fear & Greed Index

```
API: https://api.alternative.me/fng/?limit=5
Method: GET (인증 불필요)
Response:
  {
    "data": [
      {"value": "23", "value_classification": "Extreme Fear", "timestamp": "..."},
      ...
    ]
  }
```

### 7.2 VIX + 시장 데이터 (yfinance)

```python
import yfinance as yf

vix = yf.Ticker("^VIX")
sp500 = yf.Ticker("^GSPC")
nasdaq = yf.Ticker("^IXIC")

# 데이터 조회
hist = vix.history(period="1mo")
```

### 7.3 CPI (FRED API)

```
API: https://api.stlouisfed.org/fred/series/observations
Params:
  series_id: CPIAUCSL
  api_key: {FRED_API_KEY}
  sort_order: desc
  limit: 13
  file_type: json
```

### 7.4 종목 데이터 (yfinance)

```python
stock = yf.Ticker("AAPL")

# 가격 이력 (ATH 계산용)
hist_5y = stock.history(period="5y")

# 펀더멘탈
info = stock.info
# info["forwardPE"], info["trailingEps"], info["freeCashflow"]
# info["revenueGrowth"], info["earningsGrowth"]

# 애널리스트 의견
recommendations = stock.recommendations       # DataFrame
analyst_info = stock.info
# info["recommendationKey"], info["targetMeanPrice"]
# info["numberOfAnalystOpinions"]
```

---

## 8. 파일 구조

```
Invest_US_stocks/
├── app.py                    # Flask 진입점, Route 정의
├── config.py                 # 환경변수 로드, DB 경로, TTL 설정
├── requirements.txt
├── .env.example
├── .gitignore                # .env, data/ 제외
│
├── data/
│   └── invest.db             # SQLite (자동 생성)
│
├── src/
│   ├── __init__.py
│   ├── db.py                 # DB 연결, 캐시 read/write 유틸
│   ├── watchlist.py          # Watchlist CRUD
│   ├── market_sentiment.py   # Fear&Greed, VIX, RSI, CPI
│   ├── stock_analysis.py     # 종목 데이터 수집 및 가공
│   └── scoring.py            # 추천 점수 계산 (순수 함수)
│
├── templates/
│   ├── base.html             # 공통 레이아웃 (Bootstrap CDN)
│   ├── index.html            # 메인 대시보드
│   ├── stock_detail.html     # 종목 상세
│   └── watchlist.html        # Watchlist 관리
│
└── static/
    └── style.css             # 커스텀 CSS (최소화)
```

---

## 9. 환경변수 및 설정

### 9.1 `.env.example`

```ini
# FRED API Key (CPI 데이터, 무료 가입)
# https://fred.stlouisfed.org/docs/api/api_key.html
FRED_API_KEY=your_fred_api_key_here

# 데이터 갱신 주기 (초), 기본값 사용 가능
CACHE_TTL_FEAR_GREED=3600
CACHE_TTL_VIX=3600
CACHE_TTL_STOCK=21600
```

### 9.2 `config.py`

```python
import os
from dotenv import load_dotenv

load_dotenv()

FRED_API_KEY = os.getenv("FRED_API_KEY", "")
DB_PATH = os.getenv("DB_PATH", "data/invest.db")

CACHE_TTL = {
    "fear_greed":  int(os.getenv("CACHE_TTL_FEAR_GREED", 3600)),
    "vix":         3600,
    "market_rsi":  3600,
    "cpi":         86400,
    "stock":       int(os.getenv("CACHE_TTL_STOCK", 21600)),
}
```

---

## 10. 에러 처리 전략

| 상황 | 처리 방법 |
|------|---------|
| yfinance API 실패 | DB 캐시 데이터 반환, 없으면 None 표시 |
| Alternative.me API 실패 | 캐시 반환, 없으면 "N/A" 표시 |
| FRED API 키 없음 | CPI 섹션 숨김 처리 |
| 종목 티커 잘못 입력 | yfinance 조회 실패 → "조회 실패" 메시지 표시 |
| 애널리스트 데이터 없음 | ETF 등 해당 없는 경우 "N/A" 표시 |

---

## 11. 구현 순서

| 단계 | 작업 | 파일 |
|------|------|------|
| 1 | 프로젝트 셋업 + DB 초기화 | `app.py`, `src/db.py`, `config.py` |
| 2 | Watchlist CRUD | `src/watchlist.py`, `templates/watchlist.html` |
| 3 | 시장 심리 지표 수집 | `src/market_sentiment.py` |
| 4 | 종목 데이터 수집 | `src/stock_analysis.py` |
| 5 | 추천 점수 로직 | `src/scoring.py` |
| 6 | 메인 대시보드 UI | `templates/index.html` |
| 7 | 종목 상세 페이지 | `templates/stock_detail.html` |
| 8 | 캐싱 + 에러 처리 보완 | `src/db.py` |

---

## 12. 패키지 목록 (`requirements.txt`)

```
flask>=3.0.0
yfinance>=0.2.40
pandas>=2.0.0
pandas-ta>=0.3.14b
requests>=2.31.0
python-dotenv>=1.0.0
```

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-02-17 | Initial design | - |
