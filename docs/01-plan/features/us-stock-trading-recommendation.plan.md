# 미국주식 매매 추천시스템 Planning Document

> **Summary**: 관심 종목/ETF 등록 후, 시장 공포 지수와 고점 대비 낙폭 및 펀더멘탈을 종합해 매수/매도 의견을 제공하는 경량 웹 대시보드
>
> **Project**: Invest_US_stocks
> **Version**: 0.1.0
> **Author**: -
> **Date**: 2026-02-17
> **Status**: Draft

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
- Investing.com, Seeking Alpha 등 신뢰할 수 있는 사이트의 애널리스트 의견과 주요 재무 지표를 함께 보여주면 의사결정의 질이 높아진다.
- 알림 기능 없이 직접 대시보드에 접속해 확인하는 심플한 방식을 지향한다.

### 1.3 References

- yfinance (주가 및 재무 데이터)
- CNN Fear & Greed Index API
- FRED API (CPI, 매크로 지표)
- Investing.com / Seeking Alpha (애널리스트 의견 참고)

---

## 2. Scope

### 2.1 In Scope

- [x] 관심 종목 및 ETF 등록/수정/삭제 (Watchlist 관리)
- [x] 시장 심리 지표 표시: Fear & Greed Index, VIX, 주요 지수 RSI, CPI
- [x] 등록 종목별 52주 고점 / 역대 최고가(ATH) 대비 현재 낙폭(%) 표시
- [x] 공포 구간 판단 로직 (지표 조합 기반 점수화)
- [x] 종목별 펀더멘탈 지표: Forward PER, EPS, 매출성장률, 현금흐름(FCF)
- [x] 애널리스트 투자의견 집계 (Buy / Hold / Sell 비율, 목표주가)
- [x] 매수/매도 추천 점수 (심리 점수 + 낙폭 점수 + 펀더멘탈 점수 종합)
- [x] 경량 웹 대시보드 (브라우저에서 직접 접속해 확인)

### 2.2 Out of Scope

- 텔레그램 / 이메일 / 푸시 알림
- 자동매매 (증권사 API 주문 실행)
- 백테스팅
- ML/AI 모델 학습 (규칙 기반 점수화로 대체)
- 실시간 틱 데이터 / 고빈도 데이터
- 다국가 주식시장 (미국 주식/ETF만)

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | 종목/ETF 티커 입력으로 Watchlist 등록, 수정, 삭제 | High | Pending |
| FR-02 | Fear & Greed Index (현재값 + 5일 추이) 표시 | High | Pending |
| FR-03 | VIX 지수 현재값 + 추이 차트 표시 | High | Pending |
| FR-04 | 주요 지수(S&P500, NASDAQ) RSI 표시 | High | Pending |
| FR-05 | CPI 최근 발표값 및 추이 표시 (FRED API) | Medium | Pending |
| FR-06 | 등록 종목별 52주 고점 / ATH 대비 낙폭(%) 자동 계산 및 표시 | High | Pending |
| FR-07 | 공포 구간 종합 점수 산출 (Fear Score 0~100) | High | Pending |
| FR-08 | 종목별 Forward PER, EPS 성장률, FCF 표시 | High | Pending |
| FR-09 | 애널리스트 투자의견 집계 (Strong Buy / Buy / Hold / Sell 비율, 평균 목표주가) | High | Pending |
| FR-10 | 종목별 매수 추천 점수 산출 및 순위 표시 (Fear Score × 낙폭 × 펀더멘탈) | High | Pending |
| FR-11 | 대시보드 메인: 시장 심리 요약 + Watchlist 종목 추천 순위 한눈에 표시 | High | Pending |
| FR-12 | 종목 상세 페이지: 차트, 지표, 애널리스트 의견, 추천 점수 상세 | Medium | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement Method |
|----------|----------|-------------------|
| Performance | 대시보드 초기 로딩 < 5초 (캐시 활용 시) | 브라우저 로딩 시간 측정 |
| Data Freshness | 시세/지표 데이터 일 1회 이상 갱신 | 데이터 타임스탬프 확인 |
| Reliability | API 호출 실패 시 캐시 데이터로 fallback | 에러 없이 화면 표시 여부 |
| Usability | 직관적인 UI, 추천 이유를 텍스트로 설명 | 직접 사용 확인 |
| Security | API 키 환경변수 관리 (.env), 개인 사용 목적 | .gitignore 확인 |
| Simplicity | 추가 설치 없이 `python app.py` 한 줄로 실행 | 실행 테스트 |

---

## 4. 매수 추천 로직 (핵심 알고리즘)

```
[매수 추천 점수] = Fear Score × 낙폭 점수 × 펀더멘탈 점수

Fear Score (0~100):
  - Fear & Greed Index < 30  → +40점
  - VIX > 25               → +30점
  - 주요 지수 RSI < 35      → +30점
  (예: 점수 합산 후 0~100 정규화)

낙폭 점수 (0~100):
  - ATH 대비 낙폭 > 50%    → 100점
  - ATH 대비 낙폭 > 30%    → 75점
  - ATH 대비 낙폭 > 20%    → 50점
  - ATH 대비 낙폭 > 10%    → 25점

펀더멘탈 점수 (0~100):
  - 애널리스트 Buy 비율 > 70%  → +40점
  - Forward PER < 업종 평균    → +30점
  - FCF 양수 & 성장            → +30점

최종 추천:
  - 총점 70+ : ★ 강력 매수 구간
  - 총점 50+ : 매수 고려
  - 총점 30+ : 관망
  - 총점 30-  : 매수 보류
```

---

## 5. Success Criteria

### 5.1 Definition of Done

- [ ] Watchlist 종목/ETF 등록·수정·삭제 정상 동작
- [ ] Fear & Greed Index, VIX, RSI, CPI 지표 대시보드에 표시
- [ ] 등록 종목 전체의 ATH 대비 낙폭 자동 계산 및 표시
- [ ] 종목별 매수 추천 점수 산출 및 순위 목록 표시
- [ ] 애널리스트 의견 및 Forward PER 등 펀더멘탈 표시
- [ ] `python app.py` 실행 후 브라우저에서 바로 확인 가능

### 5.2 Quality Criteria

- [ ] API 호출 실패 시 에러 없이 캐시 데이터 표시
- [ ] 데이터 갱신 타임스탬프 화면에 표시
- [ ] API 키 .env 파일로 분리, .gitignore 처리

---

## 6. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| yfinance 애널리스트 데이터 불완전 | Medium | High | 없는 데이터는 "N/A" 표시, 사용자가 직접 링크로 확인 |
| Investing.com / Seeking Alpha 스크래핑 제한 | High | High | yfinance 내 analyst_recommendations 데이터 우선 활용, 외부 링크 제공으로 대체 |
| Fear & Greed Index API 변경 | Medium | Low | 대체 소스(Alternative.me API) 준비 |
| FRED API 호출 제한 | Low | Low | CPI 데이터는 월 1회 갱신이므로 캐싱으로 해결 |
| 투자 판단 오류로 인한 손실 | High | Medium | 면책 조항 명시, "참고용 지표"임을 UI에 표시 |

---

## 7. Architecture

### 7.1 Tech Stack

| 항목 | 선택 | 이유 |
|------|------|------|
| 언어 | Python | 데이터 분석 생태계 |
| 웹 프레임워크 | **Flask** | 경량, 단순 구조에 적합 |
| 프론트엔드 | **HTML + Bootstrap + Chart.js** | 별도 빌드 없이 경량 웹 구현 |
| 데이터 수집 | **yfinance** | 주가, 재무, 애널리스트 데이터 |
| 거시지표 | **FRED API** (CPI), **Alternative.me** (Fear & Greed) | 무료, 안정적 |
| 데이터 저장 | **SQLite** | 경량 로컬 DB, Watchlist 및 캐시 |
| 기술적 분석 | **pandas-ta** | RSI 등 지표 계산 |

### 7.2 Folder Structure

```
Invest_US_stocks/
├── app.py                    # Flask 앱 진입점
├── config.py                 # 설정값 (API 키 등 .env 로드)
├── requirements.txt
├── .env.example
├── .gitignore
│
├── data/
│   └── invest.db             # SQLite (Watchlist, 캐시)
│
├── src/
│   ├── watchlist.py          # Watchlist CRUD
│   ├── market_sentiment.py   # Fear & Greed, VIX, RSI, CPI
│   ├── stock_analysis.py     # ATH 낙폭, 펀더멘탈, 애널리스트 의견
│   └── scoring.py            # 매수 추천 점수 산출
│
├── templates/                # HTML 템플릿 (Jinja2)
│   ├── index.html            # 메인 대시보드
│   └── stock_detail.html     # 종목 상세
│
└── static/                   # CSS, JS
    ├── style.css
    └── charts.js
```

---

## 8. Development Phases

| Phase | Description | Deliverable |
|-------|-------------|------------|
| Phase 1 | 프로젝트 셋업 + Watchlist CRUD | Flask 기본 앱, 종목 등록/삭제 UI |
| Phase 2 | 시장 심리 지표 수집 + 표시 | Fear & Greed, VIX, RSI, CPI 대시보드 |
| Phase 3 | 종목 데이터 수집 + 낙폭 계산 | ATH 대비 낙폭, 주가 차트 |
| Phase 4 | 펀더멘탈 + 애널리스트 의견 | Forward PER, FCF, 투자의견 표시 |
| Phase 5 | 추천 점수 로직 + 순위 표시 | 매수 추천 점수 산출 및 Watchlist 순위 |
| Phase 6 | UI 다듬기 + 캐싱 + 배포 | 완성된 대시보드, 로컬 실행 |

---

## 9. Environment Variables

| Variable | Purpose |
|----------|---------|
| `FRED_API_KEY` | FRED API (CPI 등 매크로 데이터) |
| `ALPHA_VANTAGE_API_KEY` | 보완 데이터 소스 (선택) |

---

## 10. Next Steps

1. [ ] Design 문서 작성 (`us-stock-trading-recommendation.design.md`)
2. [ ] Python 가상환경 설정 및 패키지 설치
3. [ ] Phase 1 구현 시작 (Flask 앱 + Watchlist CRUD)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-02-17 | Initial draft | - |
| 0.2 | 2026-02-17 | 사용자 요구사항 반영: 경량 웹, 알림 제거, 핵심 3가지 기능으로 집중 | - |
