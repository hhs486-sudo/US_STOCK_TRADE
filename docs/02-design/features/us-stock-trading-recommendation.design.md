# 미국주식 매매 추천시스템 Design Document

> **Summary**: 관심 종목/ETF Watchlist, 시장 심리 지표, 고점 낙폭 + 펀더멘탈 기반 매수 추천 점수를 제공하는 경량 Flask 웹 대시보드
>
> **Project**: Invest_US_stocks
> **Version**: 1.0.0
> **Author**: -
> **Date**: 2026-02-17
> **Status**: Completed
> **Planning Doc**: [us-stock-trading-recommendation.plan.md](../01-plan/features/us-stock-trading-recommendation.plan.md)

---

## 1. Overview

### 1.1 Design Goals

- Flask + SQLite(로컬)/PostgreSQL(운영) 이중 지원으로 어디서든 실행 가능
- run.bat 더블클릭 또는 gunicorn으로 즉시 실행
- 외부 API 실패 시에도 L1/L2 캐시로 graceful fallback
- 추천 점수의 근거를 팝업으로 직관적으로 설명

### 1.2 Design Principles

- **성능 우선**: L1 인메모리 캐시 + 비동기 DB 쓰기 + ThreadPoolExecutor 병렬 호출
- **이중 DB**: DATABASE_URL 환경변수 유무로 SQLite/PostgreSQL 자동 전환
- **캐싱 필수**: 모든 외부 API 호출은 L1(메모리) + L2(DB) 2계층 캐싱
- **규칙 기반 점수화**: ML 없이 명확한 로직으로 해석 가능한 추천
- **개인 사용 도구**: 인증/보안보다 편의성 우선 (개인 서버 실행 가정)

---

## 2. Architecture

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                              │
│    index.html / stock_detail.html / watchlist.html          │
│    AJAX: /api/prices (10초) → 현재가·낙폭·점수·순위 실시간 갱신  │
│    AJAX: /api/search (자동완성)                              │
└───────────────────┬─────────────────────────────────────────┘
                    │ HTTP Request
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Flask App (app.py)                        │
│                                                             │
│  GET  /               → 메인 대시보드                         │
│  GET  /stock/<ticker> → 종목 상세                             │
│  GET  /watchlist      → Watchlist 관리 페이지                 │
│  POST /watchlist/add  → 종목 추가 (yfinance 종목명 조회)       │
│  POST /watchlist/delete → 종목 삭제                           │
│  GET  /api/prices     → 배치 현재가 JSON (AJAX 전용)           │
│  GET  /api/search     → 종목 검색 JSON (Yahoo Finance)        │
│  GET  /api/refresh    → 캐시 전체 삭제 후 redirect /          │
│                                                             │
│  모든 라우트: ThreadPoolExecutor로 병렬 API 호출               │
└──────┬────────────────┬───────────────────────────────────-─┘
       │                │
       ▼                ▼
┌─────────────┐  ┌──────────────────────────────────────────┐
│  L1 Cache   │  │           src/ Modules                   │
│  (memory)   │  │                                          │
│             │  │  market_sentiment.py                     │
│  L2 Cache   │  │    get_fear_greed()  ← CNN/Alternative   │
│  SQLite or  │  │    get_vix()         ← yfinance ^VIX     │
│  PostgreSQL │  │    get_market_rsi()  ← pandas-ta RSI(14) │
│             │  │    get_cpi()         ← FRED CPIAUCSL     │
│  watchlist  │  │    get_yield_curve() ← FRED DGS10/DGS2   │
│  cache      │  │    get_fear_score()  ← 종합 공포 점수     │
└─────────────┘  │                                          │
                 │  stock_analysis.py                       │
                 │    get_stock_data()  ← yfinance          │
                 │    get_batch_prices() ← yfinance download│
                 │    get_live_prices() ← 병렬 개별 조회    │
                 │    enrich_watchlist() ← 병렬 전체 조회   │
                 │                                          │
                 │  scoring.py                              │
                 │    calc_drawdown_score()                 │
                 │    calc_fundamental_score()              │
                 │    calc_recession_penalty()              │
                 │    calc_recommendation_score()           │
                 │                                          │
                 │  watchlist.py                            │
                 │    get_all() / get_tickers()             │
                 │    add() / delete() / exists()           │
                 └──────────┬───────────────────────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │       External APIs          │
              │  yfinance (주가, 재무, 애널리스트)│
              │  CNN dataviz (Fear&Greed)    │
              │  Alternative.me (fallback)   │
              │  FRED API (CPI, DGS10/DGS2) │
              └──────────────────────────────┘
```

### 2.2 캐시 데이터 흐름

```
요청
  │
  ▼
L1: _mem dict (threading.Lock 보호)
  ├─ HIT + TTL 유효 → 즉시 반환 (ns 접근)
  └─ MISS ↓
L2: DB (SQLite / PostgreSQL)
  ├─ HIT + TTL 유효 → 반환 + L1 업데이트
  └─ MISS ↓
External API 호출
  │
  ├─ L1 즉시 업데이트 (동기)
  └─ L2 DB 저장 (daemon thread, 비동기 — 응답 블로킹 없음)
```

### 2.3 모듈 의존 관계

```
app.py
  ├── src/db.py              (L1/L2 캐시 유틸, DB 연결)
  ├── src/watchlist.py       (Watchlist CRUD)
  ├── src/market_sentiment.py (외부 API + 캐시)
  ├── src/stock_analysis.py  (외부 API + 캐시 + 병렬)
  └── src/scoring.py         (순수 계산, 외부 의존 없음)
```

---

## 3. Database Schema

### 3.1 watchlist 테이블

```sql
-- SQLite
CREATE TABLE IF NOT EXISTS watchlist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT NOT NULL UNIQUE,
    name        TEXT,
    asset_type  TEXT DEFAULT 'stock',   -- 'stock' | 'etf'
    memo        TEXT DEFAULT '',
    added_at    TEXT DEFAULT (datetime('now'))
);

-- PostgreSQL
CREATE TABLE IF NOT EXISTS watchlist (
    id          SERIAL PRIMARY KEY,
    ticker      TEXT NOT NULL UNIQUE,
    name        TEXT,
    asset_type  TEXT DEFAULT 'stock',
    memo        TEXT DEFAULT '',
    added_at    TIMESTAMP DEFAULT NOW()
);
```

### 3.2 cache 테이블

```sql
-- SQLite
CREATE TABLE IF NOT EXISTS cache (
    key         TEXT PRIMARY KEY,
    data        TEXT NOT NULL,           -- JSON 직렬화
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- PostgreSQL
CREATE TABLE IF NOT EXISTS cache (
    key         TEXT PRIMARY KEY,
    data        TEXT NOT NULL,
    updated_at  TIMESTAMP DEFAULT NOW()
);
```

### 3.3 캐시 키 규칙

| 캐시 키 | 데이터 내용 | TTL |
|--------|-----------|-----|
| `fear_greed` | CNN/Alternative.me Fear & Greed 값 및 등급 | 1시간 |
| `vix` | VIX 현재값 + 20일 종가 이력 | 1시간 |
| `market_rsi` | S&P500, NASDAQ RSI(14) | 1시간 |
| `cpi` | CPI YoY 변화율 + 12개월 이력 | 24시간 |
| `yield_curve` | 장단기 금리차 (10년-2년) | 1시간 |
| `stock_{ticker}` | 종목 전체 데이터 (가격, ATH, 펀더멘탈, 차트) | 6시간 |
| `price_batch_{tickers}` | 배치 현재가 (정렬된 티커 목록) | 10초 |
| `price_{ticker}` | 단일 현재가 | 10초 |

---

## 4. 모듈 상세 설계

### 4.1 `src/db.py`

```python
# L1 인메모리 캐시
_mem: dict = {}          # {key: {"data": ..., "ts": datetime}}
_mem_lock = threading.Lock()

# DB 드라이버 자동 선택
DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_PG = bool(DATABASE_URL)
PH = "%s" if USE_PG else "?"  # 플레이스홀더

def get_conn() -> Connection
    """SQLite or PostgreSQL 연결 반환"""

def init_db()
    """watchlist, cache 테이블 생성 (서버 시작 시 1회)"""

def cache_get(key: str, ttl_seconds: int) -> dict | None
    """L1 → L2 순으로 캐시 조회. TTL 초과 시 None"""

def cache_set(key: str, data: dict)
    """L1 즉시 업데이트 + L2 비동기 저장 (daemon thread)"""

def cache_get_raw(key: str) -> dict | None
    """TTL 무시하고 조회 (API 실패 시 fallback용)"""
```

### 4.2 `src/watchlist.py`

```python
def get_all() -> list[dict]
    """watchlist 전체 조회 (added_at 내림차순)
    Returns: [{id, ticker, name, asset_type, memo, added_at}]"""

def get_tickers() -> list[str]
    """등록된 티커 목록만 반환"""

def add(ticker, name, asset_type, memo) -> bool
    """종목 추가. 중복 시 False 반환"""

def delete(ticker) -> bool
    """종목 삭제"""

def exists(ticker) -> bool
    """등록 여부 확인"""
```

### 4.3 `src/market_sentiment.py`

```python
def get_fear_greed() -> dict
    """
    1차: CNN Fear & Greed (주식시장 기반)
    2차 fallback: Alternative.me (크립토 기반)
    Returns:
        {
            "value": 23.0,
            "label": "Extreme Fear",
            "source": "CNN Fear & Greed",
            "color": "#e74c3c",
            "prev_close": 25.0,
            "prev_1w": 30.0,
            "prev_1m": 45.0,
            "history": [...],
            "updated": "2026-02-17 09:00 UTC"
        }
    Cache: fear_greed, TTL 1시간
    """

def get_vix() -> dict
    """
    yfinance ^VIX, 1개월 이력
    Returns:
        {
            "current": 22.5,
            "prev_close": 20.1,
            "change_pct": 12.0,
            "level": "high",  # low(<15) / normal(15~25) / high(25~35) / extreme(>35)
            "history": [{"date": "...", "close": ...}]  # 20일
        }
    Cache: vix, TTL 1시간
    """

def get_market_rsi() -> dict
    """
    pandas-ta RSI(14), S&P500(^GSPC), NASDAQ(^IXIC)
    Returns:
        {
            "sp500":  {"rsi": 38.2, "level": "oversold"},
            "nasdaq": {"rsi": 35.1, "level": "neutral"},
            "updated": "..."
        }
    level: oversold(<30) / overbought(>70) / neutral
    Cache: market_rsi, TTL 1시간
    """

def get_cpi() -> dict
    """
    FRED CPIAUCSL (YoY 변화율)
    Returns:
        {
            "available": True,
            "latest_value": 3.1,     # YoY %
            "latest_date": "2026-01",
            "prev_value": 3.4,
            "trend": "down",          # up / down / flat
            "history": [{"date": "...", "value": ...}]  # 12개월
        }
    Cache: cpi, TTL 24시간
    """

def get_yield_curve() -> dict
    """
    1차: FRED DGS10 - DGS2
    2차 fallback: yfinance ^TNX - ^IRX
    Returns:
        {
            "spread": -0.25,
            "rate_10y": 4.50,
            "rate_2y": 4.75,
            "status": "inverted",  # normal / flat / inverted / deeply_inverted
            "status_label": "역전 (침체 경계)",
            "available": True,
            "source": "FRED (DGS10-DGS2)"
        }
    Cache: yield_curve, TTL 1시간
    """

def get_fear_score() -> int
    """
    종합 시장 공포 점수 (0~100, 높을수록 공포)
    구성:
      CNN Fear & Greed → 최대 40점
      VIX             → 최대 35점
      S&P500 RSI      → 최대 25점
    """
```

### 4.4 `src/stock_analysis.py`

```python
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
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "is_etf": False,

            # ETF 전용
            "ytd_return": 12.5,            # YTD 수익률 %
            "three_year_return": 8.3,       # 3년 평균 수익률 %
            "total_assets": 500_000_000_000, # AUM

            # 낙폭
            "ath": 237.4,
            "ath_date": "2024-12-26",
            "high_52w": 220.0,
            "ath_drawdown_pct": -22.0,
            "high_52w_drawdown_pct": -15.8,

            # 펀더멘탈 (주식)
            "forward_pe": 24.5,
            "trailing_pe": 28.1,
            "eps_growth_pct": 12.3,
            "revenue_growth_pct": 8.5,
            "free_cash_flow": 95_000_000_000,
            "fcf_positive": True,
            "roe": 160.5,                  # 자기자본이익률 %
            "peg": 1.8,                    # PER/EPS성장률

            # 애널리스트
            "analyst_count": 38,
            "strong_buy": 15,
            "buy": 12,
            "hold": 8,
            "sell": 2,
            "strong_sell": 1,
            "buy_ratio_pct": 71.0,
            "target_price": 225.0,
            "target_upside_pct": 21.5,

            # 차트 (1년, 이동평균 포함)
            "price_history": [
                {
                    "date": "2025-02-18",
                    "close": 185.2,
                    "volume": 52_000_000,
                    "ma20": 182.1,
                    "ma60": 178.5,
                    "ma120": 175.0   # 초반 구간은 None
                },
                ...
            ],  # 최대 252거래일 (1년)

            "updated": "2026-02-17 09:00 UTC",
            "error": None
        }
    """

def get_batch_prices(tickers: list[str]) -> dict
    """
    여러 종목 현재가를 한 번의 yf.download로 배치 조회.
    프리/애프터마켓 포함 (prepost=True).
    Cache: price_batch_{sorted_tickers}, TTL 10초

    Returns:
        {
            "AAPL": {"price": 185.2, "prev_close": 183.0, "change_pct": 1.2},
            "MSFT": None  # 조회 실패 시
        }
    """

def get_live_prices(tickers: list[str]) -> dict
    """
    여러 종목 현재가를 ThreadPoolExecutor로 병렬 조회.
    Cache TTL: 10초

    Returns: {ticker: current_price, ...}
    """

def enrich_watchlist(tickers: list[str], fear_score: int,
                     yield_spread=None) -> list[dict]
    """
    Watchlist 종목 전체 데이터 + 추천 점수 병렬 조회.
    결과를 total_score 내림차순으로 정렬하여 반환.
    (실시간 가격은 /api/prices AJAX가 별도 담당)
    """
```

### 4.5 `src/scoring.py`

```python
def calc_drawdown_score(ath_drawdown_pct: float | None) -> int
    """
    ATH 대비 낙폭 → 점수 (0~100)
    ≥50%: 100점 / ≥30%: 75점 / ≥20%: 50점 / ≥10%: 25점 / <10%: 0점
    """

def calc_fundamental_score(stock_data: dict) -> int | None
    """
    주식 전용 펀더멘탈 점수 (0~100). ETF는 None 반환.
    Buy 비율 ≥70%: +40 / ≥50%: +20
    Forward PER <15: +30 / <20: +25 / <25: +20
    FCF 양수: +20
    EPS 성장률 >10%: +10
    """

def calc_recession_penalty(yield_spread) -> int
    """
    장단기 금리차 역전 패널티 (0~25점)
    >0.5%: 0 / 0~0.5%: 5 / -0.5~0%: 15 / <-0.5%: 25
    """

def calc_recommendation_score(fear_score: int, stock_data: dict,
                               yield_spread=None) -> dict
    """
    최종 추천 점수 및 등급 산출.

    주식: total = fear×0.3 + drawdown×0.4 + fundamental×0.3 - penalty
    ETF:  total = fear×0.5 + drawdown×0.5 - penalty

    Returns:
        {
            "total_score": 78,
            "fear_score": 60,
            "drawdown_score": 75,
            "fundamental_score": 80,  # ETF는 None
            "recession_penalty": 0,
            "is_etf": False,
            "grade": "★ 강력 매수",
            "grade_color": "#27ae60",
            "reason": "시장 공포 구간 + ATH -22.0% + Buy 71.0%"
        }

    등급 기준:
        70+: ★ 강력 매수 (#27ae60)
        50+: 매수 고려   (#2ecc71)
        30+: 관망        (#f39c12)
        <30: 매수 보류   (#95a5a6)
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
| GET | `/api/prices` | 배치 현재가 JSON (AJAX) | - |
| GET | `/api/search?q=` | 종목 검색 JSON | - |
| GET | `/api/refresh` | 캐시 전체 삭제 후 redirect `/` | - |

### 5.2 Route 상세

#### `GET /` — 메인 대시보드

```python
# ThreadPoolExecutor(max_workers=6)로 병렬 호출
context = {
    "fear_greed":   get_fear_greed(),
    "vix":          get_vix(),
    "market_rsi":   get_market_rsi(),
    "cpi":          get_cpi(),
    "yield_curve":  get_yield_curve(),
    "fear_score":   get_fear_score(),
    "stocks":       enrich_watchlist(tickers, fear_score, yield_spread),
}
```

#### `GET /stock/<ticker>` — 종목 상세

```python
# ThreadPoolExecutor(max_workers=3)로 병렬 호출
context = {
    "stock":       get_stock_data(ticker),
    "score":       calc_recommendation_score(fear_score, stock_data, yield_spread),
    "fear_score":  get_fear_score(),
    "yield_curve": get_yield_curve(),
}
```

#### `GET /api/prices` — 배치 현재가 (AJAX)

```json
{
    "AAPL": {"price": 185.20, "prev_close": 183.00, "change_pct": 1.20},
    "MSFT": {"price": 400.10, "prev_close": 401.32, "change_pct": -0.30}
}
```

#### `GET /api/search?q=apple` — 종목 검색

```json
[
    {"ticker": "AAPL", "name": "Apple Inc.", "exchange": "NMS", "asset_type": "stock"},
    {"ticker": "AAPL.BA", "name": "Apple Inc.", "exchange": "BUE", "asset_type": "stock"}
]
```

---

## 6. UI/UX 설계

### 6.1 메인 대시보드 (`index.html`)

```
┌─────────────────────────────────────────────────────────┐
│  HEADER: 미국주식 매매 추천 시스템  [Watchlist] [↻ 갱신]  │
├─────────────────────────────────────────────────────────┤
│  [시장 심리 지표 카드 5개]                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │Fear&Greed│ │   VIX    │ │S&P RSI   │ │   CPI    │    │
│  │  23.0    │ │  26.5    │ │  38.2    │ │  3.1% ↓  │    │
│  │Extr.Fear │ │  HIGH    │ │ 약세     │ │ 전월比   │    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │
│  ┌──────────────────────────────────────┐                │
│  │ 장단기 금리차: -0.25% ⚠ 역전 (침체 경계) │               │
│  └──────────────────────────────────────┘                │
│                                                          │
│  [공포 종합 점수]                                          │
│  ████████░░ 시장 공포 점수: 70 / 100 (매수 기회 구간)       │
│                                                          │
├─────────────────────────────────────────────────────────┤
│  [관심 종목 추천 순위]                         마지막 갱신: │
│  ┌────┬─────────┬───────┬───────────────────┬──────┬───────────┬───┐ │
│  │순위│ 종목    │현재가 │ATH(All-Time High) │Buy%  │추천점수   │등급│ │
│  │    │         │       │대비 낙폭          │      │           │    │ │
│  ├────┼─────────┼───────┼───────────────────┼──────┼───────────┼───┤ │
│  │ 1  │AAPL 🔗  │$185.2 │      -22%         │ 71%  │  78점     │★강매│ │
│  │ 2  │MSFT 🔗  │$400.1 │      -18%         │ 85%  │  72점     │★강매│ │
│  │ 3  │SPY  🔗  │$520.0 │      -15%         │  -   │  60점     │매수고│ │
│  └────┴─────────┴───────┴───────────────────┴──────┴───────────┴───┘ │
│  (등급 뱃지 클릭 → 점수 근거 팝업)                                   │
│  (10초마다 AJAX 자동 갱신: 현재가·ATH낙폭·추천점수·순위 실시간 반영) │
│  (변경 셀 플래시 애니메이션: 상승↑녹색 / 하락↓빨강)                 │
└─────────────────────────────────────────────────────────┘
```

### 6.2 종목 상세 페이지 (`stock_detail.html`)

```
┌─────────────────────────────────────────────────────────┐
│  ← 돌아가기   AAPL - Apple Inc.   $185.20  (▼-1.2%)     │
├─────────────────────────────────────────────────────────┤
│  [추천 점수 카드]                                         │
│  종합 추천 점수: 78점  [★ 강력 매수] ← 클릭 시 팝업       │
│  근거: 시장 공포 구간 + ATH -22% + Buy 71%               │
│  ┌────────────────┐ ┌────────────────┐ ┌──────────────┐ │
│  │공포점수: 60/100│ │낙폭점수: 75/100│ │펀더: 80/100  │ │
│  └────────────────┘ └────────────────┘ └──────────────┘ │
├─────────────────────────────────────────────────────────┤
│  [1년 가격 차트 (Chart.js)]                               │
│  ─ 종가  ─ MA20  ─ MA60  ─ MA120  | 거래량 막대 (하단)   │
├─────────────────────────────────────────────────────────┤
│  [낙폭 정보]           [펀더멘탈]        [애널리스트]       │
│  ATH: $237.4           Forward PE: 24.5  총 38명          │
│  ATH 대비: -22.0%      Trailing PE: 28.1 Strong Buy: 15   │
│  52주 고점: $220.0     EPS 성장: +12.3%  Buy: 12          │
│  52주 대비: -15.8%     FCF: $95B ✓       Hold: 8          │
│                        ROE: 160.5%       Sell: 2+1         │
│                        PEG: 1.8          목표가: $225      │
│                                         Upside: +21.5%    │
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
│  [종목 검색]                                              │
│  [검색창: Apple, AAPL, S&P500...] ← 자동완성 드롭다운     │
│                                                          │
│  [종목 추가 폼]                                           │
│  티커: [AAPL] 유형: [Stock▼] 메모: [장기 보유] [추가]     │
├─────────────────────────────────────────────────────────┤
│  [등록 종목 목록]                                         │
│  ┌──────┬────────────┬──────┬────────────┬───────┬────┐  │
│  │티커  │ 종목명     │ 유형 │ 메모       │ 등록일 │    │  │
│  ├──────┼────────────┼──────┼────────────┼───────┼────┤  │
│  │ AAPL │ Apple Inc. │STOCK │ 장기 보유  │02-17  │[삭]│  │
│  │ SPY  │ SPDR S&P.. │ ETF  │ S&P500 ETF │02-17  │[삭]│  │
│  └──────┴────────────┴──────┴────────────┴───────┴────┘  │
└─────────────────────────────────────────────────────────┘
```

### 6.4 등급 팝업 Modal

```
┌─────────────────────────────────────────────────────────┐
│  AAPL 추천 점수 분석                              [×]     │
├─────────────────────────────────────────────────────────┤
│  종합 점수: 78점  ★ 강력 매수                            │
│                                                          │
│  ┌──────────────────┬────────────────────────────┐       │
│  │ 공포 점수  60점  │ Fear&Greed 23 + VIX 26.5   │       │
│  │ 낙폭 점수  75점  │ ATH 대비 -22.0%            │       │
│  │ 펀더 점수  80점  │ Buy 71% + FCF 양수         │       │
│  │ 금리 패널티 -5점 │ 금리차 플랫 (0.2%)         │       │
│  └──────────────────┴────────────────────────────┘       │
│                                                          │
│  계산식: 60×0.3 + 75×0.4 + 80×0.3 - 5 = 78점            │
└─────────────────────────────────────────────────────────┘
```

---

## 7. 외부 데이터 소스 상세

### 7.1 Fear & Greed Index

```
1차: CNN dataviz
  URL: https://production.dataviz.cnn.io/index/fearandgreed/graphdata
  Method: GET, User-Agent 헤더 필요
  Returns: fear_and_greed.score, previous_close, previous_1_week, previous_1_month

2차 fallback: Alternative.me
  URL: https://api.alternative.me/fng/?limit=5
  Returns: data[].value, value_classification
```

### 7.2 VIX + RSI (yfinance)

```python
# VIX
yf.Ticker("^VIX").history(period="1mo")

# RSI
yf.Ticker("^GSPC").history(period="3mo")  # S&P500
yf.Ticker("^IXIC").history(period="3mo")  # NASDAQ
pandas_ta.rsi(close, length=14)
```

### 7.3 CPI + 금리 (FRED API)

```
CPI: https://api.stlouisfed.org/fred/series/observations
  series_id: CPIAUCSL, limit: 15, sort_order: desc

10년물: series_id: DGS10, limit: 5
 2년물: series_id: DGS2,  limit: 5

금리 fallback (yfinance):
  ^TNX (10년물, 10배 보정) - ^IRX (3개월물, 10배 보정)
```

### 7.4 종목 데이터 (yfinance)

```python
t = yf.Ticker("AAPL")
hist_5y = t.history(period="5y")      # ATH/이동평균 계산
info = t.info                         # 펀더멘탈, 애널리스트
rec  = t.recommendations              # DataFrame: strongBuy/buy/hold/sell/strongSell
```

### 7.5 종목 검색 (Yahoo Finance)

```
URL: https://query1.finance.yahoo.com/v1/finance/search
Params: q, quotesCount=8, newsCount=0, listsCount=0
Filter: quoteType in (EQUITY, ETF)
```

---

## 8. 파일 구조

```
Invest_US_stocks/
├── app.py                    # Flask 진입점, 모든 Route 정의
├── config.py                 # 환경변수 로드, CACHE_TTL 설정
├── requirements.txt          # flask, gunicorn, psycopg2-binary, yfinance,
│                             # pandas, pandas-ta, requests, python-dotenv
├── Procfile                  # web: gunicorn app:app
├── run.bat                   # 로컬 실행 (기존 python 종료 후 재시작)
├── .env                      # 환경변수 (gitignore)
├── .gitignore                # .env, data/, __pycache__/ 제외
│
├── src/
│   ├── __init__.py
│   ├── db.py                 # L1/L2 캐시, SQLite/PostgreSQL 이중 지원
│   ├── watchlist.py          # Watchlist CRUD (get_all/get_tickers/add/delete/exists)
│   ├── market_sentiment.py   # Fear&Greed, VIX, RSI, CPI, 금리차, Fear Score
│   ├── stock_analysis.py     # 종목 데이터, 배치/개별 가격, enrich_watchlist
│   └── scoring.py            # 추천 점수 (drawdown/fundamental/recession/total)
│
├── templates/
│   ├── base.html             # 공통 레이아웃 (Bootstrap 5 CDN, Chart.js CDN)
│   ├── index.html            # 메인 대시보드 (AJAX 10초 갱신, 등급 팝업)
│   ├── stock_detail.html     # 종목 상세 (Chart.js 차트, 이동평균, 거래량)
│   └── watchlist.html        # Watchlist 관리 (검색 자동완성 드롭다운)
│
└── docs/
    ├── 01-plan/features/us-stock-trading-recommendation.plan.md
    └── 02-design/features/us-stock-trading-recommendation.design.md
```

---

## 9. 환경변수 및 설정

### 9.1 `.env` (실제 값, gitignore)

```ini
FRED_API_KEY=<key>
DATABASE_URL=postgresql://user:pass@host/db?sslmode=require
FLASK_DEBUG=false
FLASK_PORT=5000
CACHE_TTL_FEAR_GREED=3600
CACHE_TTL_VIX=3600
CACHE_TTL_STOCK=21600
```

### 9.2 `config.py`

```python
load_dotenv()
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
DB_PATH      = os.getenv("DB_PATH", "data/invest.db")
FLASK_DEBUG  = os.getenv("FLASK_DEBUG", "false").lower() == "true"
FLASK_PORT   = int(os.getenv("FLASK_PORT", 5000))

CACHE_TTL = {
    "fear_greed": int(os.getenv("CACHE_TTL_FEAR_GREED", 3600)),
    "vix":        3600,
    "market_rsi": 3600,
    "cpi":        86400,
    "yield_curve": 3600,
    "stock":      int(os.getenv("CACHE_TTL_STOCK", 21600)),
    "price":      int(os.getenv("CACHE_TTL_PRICE", 10)),
}
```

---

## 10. 에러 처리 전략

| 상황 | 처리 방법 |
|------|---------|
| yfinance API 실패 | L2 캐시 반환, 없으면 `error` 필드에 메시지 |
| CNN Fear & Greed 실패 | Alternative.me API fallback |
| FRED API 키 없음 | CPI/금리 섹션 `available: False` 반환, UI 숨김 |
| FRED API 실패 | yfinance ^TNX/^IRX fallback |
| DB 쓰기 실패 | daemon thread 내 silent fail (응답에 영향 없음) |
| 종목 티커 잘못 입력 | `error` 필드 설정, 메인 화면에 에러 표시 |
| 애널리스트 데이터 없음 | None/0 반환, UI에서 "N/A" 표시 |

---

## 11. 성능 최적화

| 최적화 | 적용 위치 | 효과 |
|--------|---------|------|
| L1 인메모리 캐시 | `src/db.py` | Neon DB 네트워크 왕복 제거 |
| 비동기 DB 쓰기 | `cache_set()` daemon thread | 응답 지연 제거 |
| 시장 지표 병렬 호출 | `index()` ThreadPoolExecutor(6) | 직렬 대비 ~5배 향상 |
| 종목 상세 병렬 호출 | `stock_detail()` ThreadPoolExecutor(3) | 직렬 대비 ~3배 향상 |
| Watchlist 병렬 조회 | `enrich_watchlist()` ThreadPoolExecutor(N) | 종목 수만큼 향상 |
| AJAX 가격 분리 | `/api/prices` (10초 TTL) | 페이지 렌더링에서 실시간 가격 분리 |
| 배치 가격 조회 | `get_batch_prices()` yf.download | 개별 조회 대비 API 호출 수 감소 |

**실측 성능:**
- 캐시 미스 (첫 로딩): ~7.6초
- 캐시 히트 (이후 요청): ~1.5초

---

## 12. 패키지 목록

```
flask>=3.0.0
gunicorn>=21.2.0
psycopg2-binary>=2.9.9
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
| 1.0 | 2026-02-17 | 구현 완료 반영: 전체 모듈, 성능 최적화, 배포 구조 | - |
