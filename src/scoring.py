def calc_drawdown_score(ath_drawdown_pct: float | None) -> int:
    """일반 주식 ATH 대비 낙폭 → 점수 (0~100).
    주식은 낙폭이 크기 때문에 10~50% 구간 기준 사용."""
    if ath_drawdown_pct is None:
        return 0
    d = abs(ath_drawdown_pct)
    if d >= 50:
        return 100
    elif d >= 30:
        return 75
    elif d >= 20:
        return 50
    elif d >= 10:
        return 25
    return 0


def calc_etf_drawdown_score(ath_drawdown_pct: float | None) -> int:
    """ETF(지수추종) ATH 대비 낙폭 → 점수 (0~100).
    지수 ETF는 개별 주식보다 낙폭이 작으므로 5~20% 구간 기준 사용."""
    if ath_drawdown_pct is None:
        return 0
    d = abs(ath_drawdown_pct)
    if d >= 20:
        return 100
    elif d >= 15:
        return 75
    elif d >= 10:
        return 50
    elif d >= 5:
        return 25
    return 0


def calc_technical_score(stock_data: dict) -> int:
    """
    개별 종목 기술적 지표 점수 (0~100).
    RSI(14) + MACD(12,26,9) + MA 배열 신호 합산.
    """
    score = 0

    # RSI 신호 (0~40pt): 과매도일수록 매수 신호
    rsi = stock_data.get("rsi")
    if rsi is not None:
        if rsi <= 30:
            score += 40   # 과매도 → 강력 매수 신호
        elif rsi <= 40:
            score += 25   # 약세
        elif rsi <= 50:
            score += 10   # 중립↓
        elif rsi > 70:
            score += 0    # 과매수 → 매수 불리
        else:
            score += 5    # 그 외 (50~70 중립↑)

    # MACD 신호 (0~30pt): MACD > Signal이면 상승 모멘텀
    macd_bullish = stock_data.get("macd_bullish")
    if macd_bullish is True:
        score += 30   # 상승세
    # False 또는 None → 0pt

    # MA 배열 신호 (0~30pt): 황금배열=상승 추세
    ma_signal = stock_data.get("ma_signal", "neutral")
    if ma_signal == "bullish":
        score += 30   # 황금 배열 (price > MA20 > MA60)
    elif ma_signal == "neutral":
        score += 15   # 중립
    # bearish (역배열) → 0pt

    return min(score, 100)


def calc_fundamental_score(stock_data: dict) -> int | None:
    """
    주식 전용 펀더멘탈 점수 (0~100).
    ETF는 None 반환 (적용 불가).
    밸류에이션: PEG 우선, 없으면 Forward PE.
    재무건전성 보너스/패널티 포함.
    """
    if stock_data.get("is_etf"):
        return None

    score = 0

    # 애널리스트 Buy 비율 (0~30pt)
    buy_ratio = stock_data.get("buy_ratio_pct")
    if buy_ratio is not None:
        if buy_ratio >= 70:
            score += 30
        elif buy_ratio >= 50:
            score += 15

    # 밸류에이션 (0~30pt): PEG 우선, 없으면 Forward PE
    peg = stock_data.get("peg")
    forward_pe = stock_data.get("forward_pe")
    if peg is not None and peg > 0:
        if peg < 1:
            score += 30   # 성장 대비 저평가
        elif peg <= 2:
            score += 20   # 적정
        else:
            score += 5    # 고평가
    elif forward_pe is not None and forward_pe > 0:
        if forward_pe < 15:
            score += 25
        elif forward_pe < 20:
            score += 20
        elif forward_pe < 25:
            score += 15

    # FCF 양수 (0~20pt)
    if stock_data.get("fcf_positive"):
        score += 20

    # 성장성 (0~15pt): EPS + 매출 중복 적용 가능
    eps_growth = stock_data.get("eps_growth_pct")
    revenue_growth = stock_data.get("revenue_growth_pct")
    if eps_growth is not None and eps_growth > 15:
        score += 15   # 고성장
    elif eps_growth is not None and eps_growth > 10:
        score += 10   # 성장
    if revenue_growth is not None and revenue_growth > 10:
        score += 5    # 매출 성장 가산 (EPS와 중복 가능)

    # ROE (0~10pt): 자기자본이익률
    roe = stock_data.get("roe")
    if roe is not None:
        if roe > 20:
            score += 10   # 우량
        elif roe > 15:
            score += 5    # 양호

    # 재무 건전성 보너스/패널티 (cap에서 흡수)
    health_adj = 0
    debt_to_equity = stock_data.get("debt_to_equity")
    current_ratio = stock_data.get("current_ratio")
    if debt_to_equity is not None:
        if debt_to_equity < 0.3:
            health_adj += 5    # 우량 (부채 매우 낮음)
        elif debt_to_equity > 5.0:
            health_adj -= 10   # 위험 (과도한 부채)
        elif debt_to_equity > 2.0:
            health_adj -= 5    # 경계
    if current_ratio is not None:
        if current_ratio > 2.0:
            health_adj += 5    # 안전 (유동성 충분)
        elif current_ratio < 1.0:
            health_adj -= 5    # 유동성 위험

    return max(0, min(score + health_adj, 100))


def calc_m2_adjustment(m2_yoy: float | None, consecutive_months: int = 1) -> int:
    """
    M2 통화량 YoY 증가율 × 시차(Lag) 가중치 기반 점수 조정.

    M2와 주가 사이에는 6~12개월 시차가 존재하므로,
    "방향(수축/확장)" × "추세 지속 기간" 조합으로 실제 시장 영향 시점을 반영.

    ─ 기본 점수 (방향별) ─────────────────────────
      YoY ≥ 15%:  유동성 과잉  → base +10
      YoY  7~15%: 유동성 풍부  → base  +5
      YoY  0~ 7%: 중립/건강    → base   0  (시차 무관)
      YoY -2~ 0%: 유동성 수축  → base  -7
      YoY < -2%:  심각 수축    → base -15

    ─ 시차(Lag) 가중치 ────────────────────────────
    [수축 구간]
      1~ 3개월:  0.3 → 경보 단계, 실제 영향까지 6~12개월 남음
      4~ 6개월:  0.6 → 기업 실적 영향 가시화 시작
      7~12개월:  1.0 → 실제 경제·기업 타격 최대
      13개월 +:  0.7 → 정점 통과, 회복 가능성 증가

    [확장 구간]
      1~ 3개월:  0.4 → 선행 신호, 주가 아직 미반영 (미래 수혜)
      4~ 9개월:  0.8 → 유동성 효과 가시화
      10개월 +:  0.4 → 이미 주가에 반영됐을 가능성 높음
    """
    if m2_yoy is None:
        return 0

    # 기본 점수 결정
    if m2_yoy >= 15:
        base = 10
    elif m2_yoy >= 7:
        base = 5
    elif m2_yoy >= 0:
        return 0        # 중립 구간: 시차 고려 불필요
    elif m2_yoy >= -2:
        base = -7
    else:
        base = -15

    # 시차 가중치 적용
    months = max(1, consecutive_months)
    if base < 0:        # ── 수축 구간 가중치 ──
        if months <= 3:
            weight = 0.3    # 경보 단계
        elif months <= 6:
            weight = 0.6    # 영향 가시화 시작
        elif months <= 12:
            weight = 1.0    # 실제 영향 최대
        else:
            weight = 0.7    # 정점 통과, 회복 신호
    else:               # ── 확장 구간 가중치 ──
        if months <= 3:
            weight = 0.4    # 선행 신호
        elif months <= 9:
            weight = 0.8    # 효과 가시화
        else:
            weight = 0.4    # 이미 주가에 반영

    return round(base * weight)


def calc_recession_penalty(yield_spread) -> int:
    """
    장단기 금리차(10년-2년) 역전 시 침체 우려 패널티 (0~25점 차감).

    spread > 0.5%:  정상 →  0점 차감
    spread 0~0.5%:  플랫 →  5점 차감
    spread -0.5~0%: 역전 → 15점 차감
    spread < -0.5%: 심각 → 25점 차감
    """
    if yield_spread is None:
        return 0
    if yield_spread > 0.5:
        return 0
    elif yield_spread > 0:
        return 5
    elif yield_spread > -0.5:
        return 15
    else:
        return 25


def calc_recommendation_score(fear_score: int, stock_data: dict,
                               yield_spread=None, m2_yoy=None,
                               m2_consecutive: int = 1) -> dict:
    """
    최종 추천 점수 및 등급 산출.

    주식: total = fear×0.25 + drawdown×0.30 + fundamental×0.25 + technical×0.20
    ETF:  total = fear×0.35 + drawdown×0.35 + technical×0.30  (펀더멘탈 없음)
    장단기 금리차 역전 시 침체 패널티 차감.
    M2 유동성: 15%↑ +10보너스 / 7~15% +5 / 0~7% 0 / 수축 -7~-15 패널티.
    """
    is_etf = stock_data.get("is_etf", False)
    # ETF는 지수추종 특성상 낙폭 기준이 다름 (5~20% 구간)
    if is_etf:
        drawdown_score = calc_etf_drawdown_score(stock_data.get("ath_drawdown_pct"))
    else:
        drawdown_score = calc_drawdown_score(stock_data.get("ath_drawdown_pct"))
    fundamental_score = calc_fundamental_score(stock_data)  # ETF → None
    technical_score   = calc_technical_score(stock_data)    # 모든 종목 적용

    if is_etf:
        # ETF: 기술적 지표 포함 (펀더멘탈 대체)
        total = round(
            fear_score * 0.35
            + drawdown_score * 0.35
            + technical_score * 0.30
        )
    else:
        # 주식: 4가지 요소 반영
        total = round(
            fear_score * 0.25
            + drawdown_score * 0.30
            + (fundamental_score or 0) * 0.25
            + technical_score * 0.20
        )

    # 장단기 금리차 역전 패널티 (침체 우려 시 점수 하향)
    recession_penalty = calc_recession_penalty(yield_spread)
    # M2 통화량 유동성 조정 (시차 가중치 포함, 양수=보너스 가산, 음수=패널티 차감)
    m2_adjustment = calc_m2_adjustment(m2_yoy, m2_consecutive)
    total = max(0, min(100, total - recession_penalty + m2_adjustment))

    if total >= 70:
        grade = "★ 강력 매수"
        grade_color = "#27ae60"
    elif total >= 50:
        grade = "매수 고려"
        grade_color = "#2ecc71"
    elif total >= 30:
        grade = "관망"
        grade_color = "#f39c12"
    else:
        grade = "매수 보류"
        grade_color = "#95a5a6"

    # 추천 이유 텍스트
    reasons = []
    if fear_score >= 60:
        reasons.append("시장 공포 구간")
    elif fear_score >= 40:
        reasons.append("시장 불안 구간")

    dd = stock_data.get("ath_drawdown_pct")
    if dd is not None:
        reasons.append(f"ATH {dd}%")

    if not is_etf:
        buy_ratio = stock_data.get("buy_ratio_pct")
        if buy_ratio is not None:
            reasons.append(f"Buy {buy_ratio}%")
    else:
        three_yr = stock_data.get("three_year_return")
        if three_yr is not None:
            reasons.append(f"3년수익 {three_yr}%")

    # 금리차 역전 패널티 근거 추가
    if recession_penalty >= 25:
        reasons.append("⚠ 금리 심각 역전(-25)")
    elif recession_penalty >= 15:
        reasons.append("⚠ 금리 역전(-15)")
    elif recession_penalty >= 5:
        reasons.append("금리차 플랫(-5)")

    # M2 유동성 조정 근거 추가
    if m2_adjustment >= 10:
        reasons.append("💧 M2 과잉 유동성(+10)")
    elif m2_adjustment >= 5:
        reasons.append("💧 M2 유동성 풍부(+5)")
    elif m2_adjustment <= -15:
        reasons.append("⚠ M2 심각 수축(-15)")
    elif m2_adjustment <= -7:
        reasons.append("⚠ M2 수축(-7)")

    return {
        "total_score":        total,
        "fear_score":         fear_score,
        "drawdown_score":     drawdown_score,
        "fundamental_score":  fundamental_score,   # ETF는 None
        "technical_score":    technical_score,     # 모든 종목 적용
        "recession_penalty":  recession_penalty,
        "m2_adjustment":      m2_adjustment,        # 양수=보너스, 음수=패널티
        "is_etf":             is_etf,
        "grade":              grade,
        "grade_color":        grade_color,
        "reason":             " + ".join(reasons) if reasons else "-",
    }
