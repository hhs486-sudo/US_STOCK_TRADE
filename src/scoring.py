def calc_drawdown_score(ath_drawdown_pct: float | None) -> int:
    """ATH 대비 낙폭 → 점수 (0~100)."""
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


def calc_fundamental_score(stock_data: dict) -> int | None:
    """
    주식 전용 펀더멘탈 점수 (0~100).
    ETF는 None 반환 (적용 불가).
    """
    if stock_data.get("is_etf"):
        return None

    score = 0

    buy_ratio = stock_data.get("buy_ratio_pct")
    if buy_ratio is not None:
        if buy_ratio >= 70:
            score += 40
        elif buy_ratio >= 50:
            score += 20

    forward_pe = stock_data.get("forward_pe")
    if forward_pe is not None and forward_pe > 0:
        if forward_pe < 15:
            score += 30
        elif forward_pe < 20:
            score += 25
        elif forward_pe < 25:
            score += 20

    if stock_data.get("fcf_positive"):
        score += 20

    eps_growth = stock_data.get("eps_growth_pct")
    if eps_growth is not None and eps_growth > 10:
        score += 10

    return min(score, 100)


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
                               yield_spread=None) -> dict:
    """
    최종 추천 점수 및 등급 산출.

    주식: total = fear_score×0.3 + drawdown_score×0.4 + fundamental_score×0.3
    ETF:  total = fear_score×0.5 + drawdown_score×0.5  (펀더멘탈 없음)
    장단기 금리차 역전 시 침체 패널티 차감.
    """
    is_etf = stock_data.get("is_etf", False)
    drawdown_score    = calc_drawdown_score(stock_data.get("ath_drawdown_pct"))
    fundamental_score = calc_fundamental_score(stock_data)  # ETF → None

    if is_etf:
        total = round(fear_score * 0.5 + drawdown_score * 0.5)
    else:
        total = round(
            fear_score * 0.3
            + drawdown_score * 0.4
            + (fundamental_score or 0) * 0.3
        )

    # 장단기 금리차 역전 패널티 (침체 우려 시 점수 하향)
    recession_penalty = calc_recession_penalty(yield_spread)
    total = max(0, total - recession_penalty)

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

    return {
        "total_score":        total,
        "fear_score":         fear_score,
        "drawdown_score":     drawdown_score,
        "fundamental_score":  fundamental_score,   # ETF는 None
        "recession_penalty":  recession_penalty,
        "is_etf":             is_etf,
        "grade":              grade,
        "grade_color":        grade_color,
        "reason":             " + ".join(reasons) if reasons else "-",
    }
