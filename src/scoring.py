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

    주식: total = fear_score×0.3 + drawdown_score×0.4 + fundamental_score×0.3
    ETF:  total = fear_score×0.5 + drawdown_score×0.5  (펀더멘탈 없음)
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
        "recession_penalty":  recession_penalty,
        "m2_adjustment":      m2_adjustment,        # 양수=보너스, 음수=패널티
        "is_etf":             is_etf,
        "grade":              grade,
        "grade_color":        grade_color,
        "reason":             " + ".join(reasons) if reasons else "-",
    }
