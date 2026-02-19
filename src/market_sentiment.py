import requests
import yfinance as yf
import pandas_ta as ta
import pandas as pd
from datetime import datetime

import config
from src.db import cache_get, cache_set, cache_get_raw


_CNN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    )
}
_CNN_FG_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"


def _fg_color(value: float) -> str:
    if value <= 25:
        return "#e74c3c"   # Extreme Fear
    elif value <= 45:
        return "#e67e22"   # Fear
    elif value <= 55:
        return "#f1c40f"   # Neutral
    elif value <= 75:
        return "#2ecc71"   # Greed
    return "#27ae60"       # Extreme Greed


def _fg_label(value: float) -> str:
    if value <= 25:
        return "Extreme Fear"
    elif value <= 45:
        return "Fear"
    elif value <= 55:
        return "Neutral"
    elif value <= 75:
        return "Greed"
    return "Extreme Greed"


def get_fear_greed() -> dict:
    """CNN Fear & Greed Index (주식시장 기반). Alternative.me를 fallback으로 사용."""
    key = "fear_greed"
    cached = cache_get(key, config.CACHE_TTL["fear_greed"])
    if cached:
        return cached

    # 1차: CNN
    try:
        resp = requests.get(_CNN_FG_URL, headers=_CNN_HEADERS, timeout=10)
        resp.raise_for_status()
        fg = resp.json()["fear_and_greed"]

        value = round(float(fg["score"]), 1)
        result = {
            "value":          value,
            "label":          _fg_label(value),
            "source":         "CNN Fear & Greed",
            "color":          _fg_color(value),
            "prev_close":     round(float(fg["previous_close"]), 1),
            "prev_1w":        round(float(fg["previous_1_week"]), 1),
            "prev_1m":        round(float(fg["previous_1_month"]), 1),
            "history":        [],
            "updated":        datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }
        cache_set(key, result)
        return result
    except Exception:
        pass

    # 2차 fallback: Alternative.me
    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=5", timeout=10)
        resp.raise_for_status()
        items = resp.json()["data"]
        value = int(items[0]["value"])
        result = {
            "value":    value,
            "label":    items[0]["value_classification"],
            "source":   "Alternative.me (크립토 기반)",
            "color":    _fg_color(value),
            "prev_close": None, "prev_1w": None, "prev_1m": None,
            "history":  [{"value": int(i["value"]), "label": i["value_classification"]} for i in items],
            "updated":  datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }
        cache_set(key, result)
        return result
    except Exception:
        return cache_get_raw(key) or {
            "value": None, "label": "N/A", "source": "-", "color": "#95a5a6",
            "prev_close": None, "prev_1w": None, "prev_1m": None,
            "history": [], "updated": "조회 실패"
        }


def get_vix() -> dict:
    key = "vix"
    cached = cache_get(key, config.CACHE_TTL["vix"])
    if cached:
        return cached

    try:
        hist = yf.Ticker("^VIX").history(period="1mo")
        if hist.empty:
            raise ValueError("VIX 데이터 없음")

        current = round(float(hist["Close"].iloc[-1]), 2)
        prev = round(float(hist["Close"].iloc[-2]), 2)
        change_pct = round((current - prev) / prev * 100, 2)

        if current < 15:
            level = "low"
        elif current < 25:
            level = "normal"
        elif current < 35:
            level = "high"
        else:
            level = "extreme"

        history = [
            {"date": str(d.date()), "close": round(float(v), 2)}
            for d, v in zip(hist.index[-20:], hist["Close"].iloc[-20:])
        ]

        result = {
            "current": current,
            "prev_close": prev,
            "change_pct": change_pct,
            "level": level,
            "history": history,
            "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }
        cache_set(key, result)
        return result
    except Exception:
        return cache_get_raw(key) or {
            "current": None, "prev_close": None, "change_pct": None,
            "level": "unknown", "history": [], "updated": "조회 실패"
        }


def get_market_rsi() -> dict:
    key = "market_rsi"
    cached = cache_get(key, config.CACHE_TTL["market_rsi"])
    if cached:
        return cached

    def _rsi(ticker: str) -> dict:
        try:
            hist = yf.Ticker(ticker).history(period="3mo")
            if hist.empty:
                raise ValueError
            rsi_series = ta.rsi(hist["Close"], length=14)
            rsi = round(float(rsi_series.dropna().iloc[-1]), 1)
            if rsi < 30:
                level = "oversold"
            elif rsi > 70:
                level = "overbought"
            else:
                level = "neutral"
            return {"rsi": rsi, "level": level}
        except Exception:
            return {"rsi": None, "level": "unknown"}

    result = {
        "sp500":  _rsi("^GSPC"),
        "nasdaq": _rsi("^IXIC"),
        "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }
    cache_set(key, result)
    return result


def get_cpi() -> dict:
    key = "cpi"
    cached = cache_get(key, config.CACHE_TTL["cpi"])
    if cached:
        return cached

    if not config.FRED_API_KEY:
        return {"available": False, "reason": "FRED_API_KEY not set"}

    try:
        resp = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={
                "series_id":  "CPIAUCSL",
                "api_key":    config.FRED_API_KEY,
                "sort_order": "desc",
                "limit":      15,   # YoY 계산용 최소 13개 + 여유분
                "file_type":  "json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        obs = resp.json()["observations"]

        # YoY 변화율 계산 (전년 동월 대비)
        values = [float(o["value"]) for o in obs if o["value"] != "."]
        dates  = [o["date"][:7] for o in obs if o["value"] != "."]

        latest_val  = values[0]
        prev_val    = values[1]
        yoy_val     = values[0]
        yoy_prev    = values[12] if len(values) > 12 else None

        yoy_rate      = round((yoy_val / yoy_prev - 1) * 100, 2) if yoy_prev else None
        yoy_rate_prev = round((values[1] / values[13] - 1) * 100, 2) if len(values) > 13 else None

        if yoy_rate and yoy_rate_prev:
            trend = "down" if yoy_rate < yoy_rate_prev else "up"
        else:
            trend = "flat"

        history = [
            {"date": d, "value": round(v, 2)}
            for d, v in zip(dates[:12], values[:12])
        ]

        result = {
            "available":    True,
            "latest_value": yoy_rate,
            "latest_date":  dates[0],
            "prev_value":   yoy_rate_prev,
            "trend":        trend,
            "history":      history,
            "updated":      datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }
        cache_set(key, result)
        return result
    except Exception:
        return cache_get_raw(key) or {"available": False, "reason": "조회 실패"}


def get_m2() -> dict:
    """
    M2 통화량 YoY 증가율 조회 (FRED M2SL).

    M2(광의통화)는 시장 유동성의 핵심 지표.
    YoY 증가율이 높을수록 유동성 풍부 → 증시 우호,
    마이너스(수축)이면 유동성 긴축 → 증시 하락 압력.

    반환:
        {
            "available":    True,
            "latest_value": 5.2,        # YoY 증가율 (%)
            "latest_date":  "2024-01",
            "prev_value":   4.8,        # 전월 YoY 증가율
            "trend":        "up",       # up / down / flat
            "level":        "expanding",
            "level_label":  "유동성 풍부",
            "color":        "#27ae60",
            "history":      [...],
            "updated":      "...",
        }
    """
    key = "m2"
    cached = cache_get(key, config.CACHE_TTL["m2"])
    if cached:
        return cached

    if not config.FRED_API_KEY:
        return {"available": False, "reason": "FRED_API_KEY not set"}

    try:
        resp = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={
                "series_id":  "M2SL",           # M2 통화량 (십억 달러, 계절조정)
                "api_key":    config.FRED_API_KEY,
                "sort_order": "desc",
                "limit":      26,               # YoY 14개월치 계산: 14 + 12 = 26개 필요
                "file_type":  "json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        obs = resp.json()["observations"]

        # 유효한 값만 추출
        values = [float(o["value"]) for o in obs if o["value"] != "."]
        dates  = [o["date"][:7] for o in obs if o["value"] != "."]

        # ── 최대 14개월치 YoY 시리즈 계산 ──
        # yoy[i] = (values[i] / values[i+12] - 1) × 100  (전년 동월 대비)
        yoy_series = []
        for i in range(min(14, len(values) - 12)):
            yoy_val = round((values[i] / values[i + 12] - 1) * 100, 2)
            yoy_series.append({"date": dates[i], "yoy": yoy_val})

        yoy_rate      = yoy_series[0]["yoy"] if yoy_series else None
        yoy_rate_prev = yoy_series[1]["yoy"] if len(yoy_series) > 1 else None

        # 추세 판단 (전월 YoY 대비)
        if yoy_rate is not None and yoy_rate_prev is not None:
            trend = "down" if yoy_rate < yoy_rate_prev else "up"
        else:
            trend = "flat"

        # ── 연속 추세 지속 개월 계산 (시차 가중치 산출용) ──
        # 현재 방향(수축/확장)이 몇 개월째 연속 유지되고 있는지 카운트
        consecutive_months = 0
        if yoy_rate is not None:
            is_contracting = yoy_rate < 0   # 현재 방향: 수축(True) / 확장(False)
            for entry in yoy_series:
                if (entry["yoy"] < 0) == is_contracting:
                    consecutive_months += 1
                else:
                    break   # 방향이 바뀌면 중단

        # 유동성 수준 분류 — 전문가 기준 5단계 (매수/매도 타이밍 신호)
        def _level(rate):
            if rate is None:
                return "unknown", "데이터 없음", "#95a5a6"
            if rate >= 15:
                return "excess",               "유동성 과잉 (매수 신호)",      "#1a5276"  # 짙은 파랑
            elif rate >= 7:
                return "expanding",            "유동성 풍부 (매수 우호)",      "#27ae60"  # 초록
            elif rate >= 0:
                return "neutral",              "건강한 성장 (보유/중립)",      "#f1c40f"  # 노랑
            elif rate >= -2:
                return "contracting",          "유동성 수축 (주의)",           "#e67e22"  # 주황
            else:
                return "severely_contracting", "유동성 심각 수축 (매도 신호)", "#e74c3c"  # 빨강

        level, level_label, color = _level(yoy_rate)

        # history: YoY 시리즈 저장 (차트·모달 표시용)
        history = yoy_series[:12]

        result = {
            "available":          True,
            "latest_value":       yoy_rate,
            "latest_date":        dates[0],
            "prev_value":         yoy_rate_prev,
            "trend":              trend,
            "level":              level,
            "level_label":        level_label,
            "color":              color,
            "consecutive_months": consecutive_months,  # 현재 추세 연속 지속 개월
            "history":            history,
            "updated":            datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }
        cache_set(key, result)
        return result
    except Exception:
        return cache_get_raw(key) or {"available": False, "reason": "조회 실패"}


def get_yield_curve() -> dict:
    """
    미국 장단기 금리차 조회 (10년물 - 2년물).
    역전(음수) 시 경기침체 선행 신호.

    1차: FRED API (DGS10, DGS2)
    2차: yfinance ^TNX(10년) - ^IRX(3개월) 대체

    반환:
        {
            "spread":      -0.25,    # 금리차 (%) — 음수: 역전
            "rate_10y":     4.50,    # 10년물 금리
            "rate_2y":      4.75,    # 2년물 금리
            "status":      "inverted",  # normal / flat / inverted / deeply_inverted
            "status_label": "역전 (침체 경계)",
            "available":   True,
        }
    """
    key = "yield_curve"
    cached = cache_get(key, config.CACHE_TTL.get("yield_curve", 3600))
    if cached:
        return cached

    def _classify(spread: float) -> tuple:
        """금리차 → (status, label) 분류"""
        if spread > 0.5:
            return "normal",          "정상 (우상향)"
        elif spread > 0:
            return "flat",            "플랫 (주의)"
        elif spread > -0.5:
            return "inverted",        "역전 (침체 경계)"
        else:
            return "deeply_inverted", "심각한 역전 (침체 신호)"

    # ── 1차: FRED API ──
    if config.FRED_API_KEY:
        try:
            def _fred(series_id):
                r = requests.get(
                    "https://api.stlouisfed.org/fred/series/observations",
                    params={
                        "series_id": series_id,
                        "api_key":   config.FRED_API_KEY,
                        "sort_order": "desc",
                        "limit":     5,
                        "file_type": "json",
                    },
                    timeout=10,
                )
                obs = [o for o in r.json()["observations"] if o["value"] != "."]
                return round(float(obs[0]["value"]), 3)

            rate_10y = _fred("DGS10")
            rate_2y  = _fred("DGS2")
            spread   = round(rate_10y - rate_2y, 3)
            status, label = _classify(spread)
            result = {
                "spread": spread, "rate_10y": rate_10y, "rate_2y": rate_2y,
                "status": status, "status_label": label, "available": True,
                "source": "FRED (DGS10-DGS2)",
                "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            }
            cache_set(key, result)
            return result
        except Exception:
            pass

    # ── 2차 fallback: yfinance ^TNX(10년) - ^IRX(3개월) ──
    try:
        tnx = yf.Ticker("^TNX").fast_info     # 10년물
        irx = yf.Ticker("^IRX").fast_info     # 3개월물 (2년물 대체)
        rate_10y = round(getattr(tnx, "last_price", 0) / 10, 3)  # ^TNX는 10배 값 반환
        rate_short = round(getattr(irx, "last_price", 0) / 10, 3)
        spread = round(rate_10y - rate_short, 3)
        status, label = _classify(spread)
        result = {
            "spread": spread, "rate_10y": rate_10y, "rate_2y": rate_short,
            "status": status, "status_label": label, "available": True,
            "source": "yfinance (^TNX-^IRX)",
            "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }
        cache_set(key, result)
        return result
    except Exception:
        return cache_get_raw(key) or {
            "spread": None, "rate_10y": None, "rate_2y": None,
            "status": "unknown", "status_label": "조회 실패",
            "available": False, "source": "-", "updated": "-",
        }


def get_fear_score() -> int:
    """
    시장 공포 종합 점수 (0~100, 높을수록 공포 심화).
    CNN Fear & Greed 기준으로 보정된 임계값 사용.

    구성:
      Fear & Greed (CNN)  최대 40점
      VIX                 최대 35점
      S&P500 RSI          최대 25점
    """
    score = 0

    # ── Fear & Greed (CNN 기준) ── max 40점
    fg = get_fear_greed()
    if fg.get("value") is not None:
        v = fg["value"]
        if v <= 20:          # Extreme Fear
            score += 40
        elif v <= 30:        # Extreme Fear 상단
            score += 32
        elif v <= 40:        # Fear
            score += 22
        elif v <= 50:        # Fear/Neutral 경계
            score += 10

    # ── VIX ── max 35점
    vix = get_vix()
    if vix.get("current") is not None:
        v = vix["current"]
        if v >= 35:          # 극도 공포
            score += 35
        elif v >= 28:        # 높음
            score += 25
        elif v >= 23:        # 경계
            score += 15
        elif v >= 20:        # 약간 상승
            score += 5

    # ── S&P500 RSI ── max 25점
    rsi = get_market_rsi()
    sp_rsi = rsi.get("sp500", {}).get("rsi")
    if sp_rsi is not None:
        if sp_rsi <= 30:     # 과매도
            score += 25
        elif sp_rsi <= 38:   # 약세
            score += 20
        elif sp_rsi <= 45:   # 하락 압력
            score += 12
        elif sp_rsi <= 50:   # 중립 하단
            score += 5

    return min(score, 100)
