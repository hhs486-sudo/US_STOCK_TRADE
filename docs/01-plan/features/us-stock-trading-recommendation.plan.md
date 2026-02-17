# 미국주식 매매 추천시스템 Planning Document

> **Summary**: 관심 종목/ETF 등록 후, 시장 공포 지수와 고점 대비 낙폭 및 펀더멘탈을 종합해 매수/매도 의견을 제공하는 경량 웹 대시보드
>
> **Project**: Invest_US_stocks
> **Version**: 1.0.0
> **Author**: -
> **Date**: 2026-02-17
> **Status**: Completed

---

## 1. Overview

### 1.1 Purpose

내가 관심 있는 미국주식 종목과 ETF를 등록해두고,
시장 공포 구간(Fear & Greed Index 하락, VIX 급등, RSI 과매도 등)에서
등록 종목의 고점 대비 낙폭, 애널리스트 투자의견, Forward PER, 현금흐름 등을 한눈에 확인해
매수/매도 의사결정을 지원하는 경량 웹 대시보드를 구축한다.

### 1.2 Background

- 좋은 기업의 주식도 시장 공포 구간에서 과매도되는 경우가 많다.
- 투자자 심리 위축 시점을 객관적 지표로 포착하고, 그 시점의 종목별 낙폭과 펀더멘탈을 빠르게 확인할 수 있으면 좋은 매수 기회를 놓치지 않을 수 있다.
- 장단기 금리차(수익률 곡선) 역전 시 경기침체 선행 신호를 함께 반영해 추천 점수 신뢰도를 높인다.
- 알림 기능 없이 직접 대시보드에 접속해 확인하는 심플한 방식을 지향한다.

### 1.3 References

- yfinance (주가 및 재무 데이터)
- CNN Fear & Greed Index API (1차) / Alternative.me (2차 fallback)
- FRED API (CPI, 장단기 금리 DGS10/DGS2)
- yfinance ^TNX/^IRX (금리 fallback)

---

## 2. Scope

### 2.1 In Scope

- [x] 관심 종목 및 ETF 키워드 검색 후 등록/삭제 (Watchlist 관리)
- [x] 시장 심리 지표 표시: Fear & Greed Index, VIX, 주요 지수 RSI, CPI, 장단기 금리차
- [x] 등록 종목별 52주 고점 / 역대 최고가(ATH) 대비 현재 낙폭(%) 표시
- [x] 공포 구간 판단 로직 (지표 조합 기반 점수화, 0~100)
- [x] 종목별 펀더멘탈 지표: Forward PER, Trailing PER, EPS 성장률, 매출 성장률, FCF, ROE, PEG
- [x] 애널리스트 투자의견 집계 (Strong Buy / Buy / Hold / Sell 비율, 목표주가)
- [x] 매수 추천 점수 (심리 점수 + 낙폭 점수 + 펀더멘탈 점수, 금리차 패널티 반영)
- [x] ETF 전용 지표 (YTD 수익률, 3년 평균 수익률, AUM)
- [x] 경량 웹 대시보드 (브라우저에서 직접 접속해 확인)
- [x] 1년 가격 차트 (MA20/MA60/MA120 이동평균, 거래량)
- [x] 실시간 가격 AJAX 자동 갱신 (10초 주기)
- [x] PostgreSQL(Neon) + SQLite 이중 지원 (운영/개발)
- [x] Render.com 배포 (Procfile, gunicorn)

### 2.2 Out of Scope

- 텔레그램 / 이메일 / 푸시 알림
- 자동매매 (증권사 API 주문 실행)
- 백테스팅
- ML/AI 모델 학습 (규칙 기반 점수화로 대체)
- 실시간 틱 데이터 / 고빈도 데이터
- 다국가 주식시장 (미국 주식/ETF만)
- 사용자 인증 / 다중 사용자

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | 종목/ETF 티커 키워드 검색 후 Watchlist 등록, 삭제 | High | ✅ Done |
| FR-02 | Fear & Greed Index (현재값 + 전일/1주전/1달전 비교) 표시 | High | ✅ Done |
| FR-03 | VIX 지수 현재값 + 20일 추이 차트 표시 | High | ✅ Done |
| FR-04 | 주요 지수(S&P500, NASDAQ) RSI(14) 표시 | High | ✅ Done |
| FR-05 | CPI YoY 변화율 및 추이 표시 (FRED API) | Medium | ✅ Done |
| FR-06 | 장단기 금리차(10년-2년) 표시 및 침체 신호 경고 | High | ✅ Done |
| FR-07 | 등록 종목별 52주 고점 / ATH 대비 낙폭(%) 자동 계산 및 표시 | High | ✅ Done |
| FR-08 | 공포 구간 종합 점수 산출 (Fear Score 0~100) | High | ✅ Done |
| FR-09 | 종목별 펀더멘탈 지표: Forward/Trailing PER, EPS/Revenue 성장률, FCF, ROE, PEG | High | ✅ Done |
| FR-10 | 애널리스트 투자의견 집계 (Strong Buy / Buy / Hold / Sell 비율, 평균 목표주가) | High | ✅ Done |
| FR-11 | 종목별 매수 추천 점수 산출 및 순위 표시 (Fear + 낙폭 + 펀더멘탈 + 금리 패널티) | High | ✅ Done |
| FR-12 | 대시보드 메인: 시장 심리 요약 + Watchlist 종목 추천 순위 한눈에 표시 | High | ✅ Done |
| FR-13 | 종목 상세 페이지: 1년 차트(MA선/거래량), 지표, 애널리스트 의견, 추천 점수 상세 | Medium | ✅ Done |
| FR-14 | 추천 등급 클릭 시 점수 산출 근거 팝업 표시 | Medium | ✅ Done |
| FR-15 | 실시간 현재가 AJAX 자동 갱신 (10초 주기, 프리/애프터마켓 포함) | Medium | ✅ Done |
| FR-16 | 종목 키워드 검색 API (Yahoo Finance 검색, 자동완성) | Low | ✅ Done |

### 3.2 Non-Functional Requirements

| Category | Criteria | Status |
|----------|----------|--------|
| Performance | 캐시 히트 시 응답 < 2초 | ✅ 1.5초 달성 |
| Performance | 캐시 미스(첫 로딩) < 10초 | ✅ 7.6초 달성 |
| Data Freshness | 종목 데이터 6시간, 시장 심리 1시간, 현재가 10초 | ✅ Done |
| Reliability | API 호출 실패 시 캐시 데이터로 fallback | ✅ Done |
| Scalability | 여러 API 호출 병렬 처리 (ThreadPoolExecutor) | ✅ Done |
| Persistence | 서버 재시작 후 Watchlist/캐시 유지 (PostgreSQL) | ✅ Done |
| Security | API 키 환경변수 관리 (.env), .gitignore 처리 | ✅ Done |
| Simplicity | run.bat 더블클릭으로 로컬 실행 | ✅ Done |

---

## 4. 매수 추천 로직 (핵심 알고리즘)

```
[매수 추천 점수] = 가중 합산 - 금리 패널티

주식:
  total = fear_score×0.3 + drawdown_score×0.4 + fundamental_score×0.3 - recession_penalty

ETF (펀더멘탈 없음):
  total = fear_score×0.5 + drawdown_score×0.5 - recession_penalty

Fear Score (0~100):
  CNN Fear & Greed ≤ 20  → +40점
  CNN Fear & Greed ≤ 30  → +32점
  CNN Fear & Greed ≤ 40  → +22점
  CNN Fear & Greed ≤ 50  → +10점
  VIX ≥ 35               → +35점
  VIX ≥ 28               → +25점
  VIX ≥ 23               → +15점
  VIX ≥ 20               → +5점
  S&P RSI ≤ 30           → +25점
  S&P RSI ≤ 38           → +20점
  S&P RSI ≤ 45           → +12점
  S&P RSI ≤ 50           → +5점

낙폭 점수 (0~100):
  ATH 대비 낙폭 ≥ 50%    → 100점
  ATH 대비 낙폭 ≥ 30%    → 75점
  ATH 대비 낙폭 ≥ 20%    → 50점
  ATH 대비 낙폭 ≥ 10%    → 25점

펀더멘탈 점수 (0~100, 주식 전용):
  Buy 비율 ≥ 70%          → +40점
  Buy 비율 ≥ 50%          → +20점
  Forward PER < 15        → +30점
  Forward PER < 20        → +25점
  Forward PER < 25        → +20점
  FCF 양수                → +20점
  EPS 성장률 > 10%        → +10점

금리 패널티 (recession_penalty):
  장단기 금리차 > 0.5%   → 0점 차감 (정상)
  금리차 0~0.5%          → -5점 (플랫)
  금리차 -0.5~0%         → -15점 (역전)
  금리차 < -0.5%         → -25점 (심각한 역전)

등급 기준:
  총점 70+ : ★ 강력 매수 (녹색)
  총점 50+ : 매수 고려   (연녹색)
  총점 30+ : 관망        (노랑)
  총점 30-  : 매수 보류  (회색)
```

---

## 5. Success Criteria

### 5.1 Definition of Done

- [x] Watchlist 종목/ETF 키워드 검색 후 등록·삭제 정상 동작
- [x] Fear & Greed Index, VIX, RSI, CPI, 장단기 금리차 지표 대시보드에 표시
- [x] 등록 종목 전체의 ATH / 52주 고점 대비 낙폭 자동 계산 및 표시
- [x] 종목별 매수 추천 점수 산출 및 순위 목록 표시 (금리 패널티 반영)
- [x] 애널리스트 의견, PER, FCF, ROE, PEG 등 펀더멘탈 표시
- [x] 1년 가격 차트 (MA20/MA60/MA120, 거래량) 표시
- [x] 추천 등급 클릭 시 점수 근거 팝업 표시
- [x] 실시간 현재가 10초 자동 갱신 (AJAX)
- [x] run.bat으로 로컬 실행, Render.com 배포 완료

### 5.2 Quality Criteria

- [x] API 호출 실패 시 에러 없이 캐시 데이터 표시
- [x] 캐시 히트 시 응답 < 2초 (L1 인메모리 캐시)
- [x] API 키 .env 파일로 분리, .gitignore 처리
- [x] PostgreSQL/SQLite 이중 지원으로 로컬·운영 환경 일관성

---

## 6. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| yfinance 애널리스트 데이터 불완전 | Medium | High | 없는 데이터는 "N/A" 표시 |
| CNN Fear & Greed API 변경 | Medium | Low | Alternative.me API fallback 구현 |
| FRED API 호출 제한 | Low | Low | 24시간 캐싱, yfinance fallback |
| Neon DB 연결 지연 | Medium | Low | L1 인메모리 캐시로 DB 왕복 제거 |
| 투자 판단 오류로 인한 손실 | High | Medium | "참고용 지표" 면책 조항 UI 표시 |

---

## 7. Architecture

### 7.1 Tech Stack

| 항목 | 선택 | 이유 |
|------|------|------|
| 언어 | Python 3.11+ | 데이터 분석 생태계 |
| 웹 프레임워크 | **Flask 3.x** | 경량, 단순 구조에 적합 |
| 프론트엔드 | **HTML + Bootstrap 5 + Chart.js** | 별도 빌드 없이 경량 웹 구현 |
| 데이터 수집 | **yfinance** | 주가, 재무, 애널리스트 데이터 |
| 거시지표 | **FRED API** (CPI, 금리) / **CNN API** (Fear&Greed) | 무료, 안정적 |
| 데이터 저장 | **SQLite** (로컬) / **PostgreSQL/Neon** (운영) | 이중 지원 |
| 기술적 분석 | **pandas-ta** | RSI 등 지표 계산 |
| 운영 서버 | **gunicorn** | Render.com WSGI 서버 |
| 병렬 처리 | **ThreadPoolExecutor** | 다중 API 병렬 호출 |

### 7.2 캐시 아키텍처

```
요청
  │
  ▼
L1: 프로세스 메모리 (_mem dict)
  │ HIT → 즉시 반환 (ns 접근)
  │ MISS ↓
L2: DB (SQLite or PostgreSQL)
  │ HIT → 반환 + L1 업데이트
  │ MISS ↓
External API 호출
  │
  ├─ L1 즉시 업데이트
  └─ L2 비동기 저장 (daemon thread, 응답 블로킹 없음)
```

| 캐시 키 | 데이터 | TTL |
|--------|-------|-----|
| `fear_greed` | Fear & Greed Index | 1시간 |
| `vix` | VIX 현재값 + 20일 이력 | 1시간 |
| `market_rsi` | S&P500, NASDAQ RSI | 1시간 |
| `cpi` | CPI YoY 변화율 | 24시간 |
| `yield_curve` | 장단기 금리차 | 1시간 |
| `stock_{ticker}` | 종목 전체 데이터 | 6시간 |
| `price_batch_*` | 배치 현재가 | 10초 |

### 7.3 Folder Structure

```
Invest_US_stocks/
├── app.py                    # Flask 앱 진입점 (Routes, ThreadPoolExecutor)
├── config.py                 # 설정값 (.env 로드, CACHE_TTL)
├── requirements.txt          # flask, gunicorn, psycopg2-binary, yfinance, ...
├── Procfile                  # 운영: gunicorn app:app
├── run.bat                   # 로컬: 기존 프로세스 종료 후 재시작
├── .env                      # 환경변수 (gitignore 처리)
├── .gitignore
│
├── src/
│   ├── db.py                 # L1/L2 캐시, SQLite/PostgreSQL 이중 지원
│   ├── watchlist.py          # Watchlist CRUD
│   ├── market_sentiment.py   # Fear&Greed, VIX, RSI, CPI, 금리차
│   ├── stock_analysis.py     # 종목 데이터, 배치 가격, 병렬 조회
│   └── scoring.py            # 추천 점수 산출 (순수 함수)
│
├── templates/
│   ├── base.html             # 공통 레이아웃 (Bootstrap 5 CDN)
│   ├── index.html            # 메인 대시보드 (AJAX 가격 갱신)
│   ├── stock_detail.html     # 종목 상세 (Chart.js, 등급 팝업)
│   └── watchlist.html        # Watchlist 관리 (검색 자동완성)
│
└── docs/                     # PDCA 문서
```

---

## 8. Development Phases (완료)

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | 프로젝트 셋업 + Watchlist CRUD | ✅ 완료 |
| Phase 2 | 시장 심리 지표 수집 + 표시 | ✅ 완료 |
| Phase 3 | 종목 데이터 수집 + 낙폭 계산 + 차트 | ✅ 완료 |
| Phase 4 | 펀더멘탈 + 애널리스트 의견 + ROE/PEG | ✅ 완료 |
| Phase 5 | 추천 점수 로직 + 금리차 패널티 | ✅ 완료 |
| Phase 6 | 등급 팝업 + AJAX 실시간 가격 + 성능 최적화 | ✅ 완료 |
| Phase 7 | PostgreSQL 마이그레이션 + Render 배포 | ✅ 완료 |

---

## 9. Environment Variables

| Variable | Purpose | Required |
|----------|---------|---------|
| `FRED_API_KEY` | FRED API (CPI, 장단기 금리) | 권장 |
| `DATABASE_URL` | PostgreSQL 연결 문자열 (없으면 SQLite) | 운영환경 필수 |
| `FLASK_DEBUG` | 디버그 모드 (default: false) | 선택 |
| `FLASK_PORT` | 서버 포트 (default: 5000) | 선택 |
| `CACHE_TTL_FEAR_GREED` | Fear&Greed 캐시 TTL 초 (default: 3600) | 선택 |
| `CACHE_TTL_STOCK` | 종목 데이터 캐시 TTL 초 (default: 21600) | 선택 |
| `CACHE_TTL_PRICE` | 현재가 캐시 TTL 초 (default: 10) | 선택 |

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-02-17 | Initial draft | - |
| 0.2 | 2026-02-17 | 사용자 요구사항 반영: 경량 웹, 핵심 기능 집중 | - |
| 1.0 | 2026-02-17 | 구현 완료 반영: 전체 기능, 성능 최적화, 배포 | - |
