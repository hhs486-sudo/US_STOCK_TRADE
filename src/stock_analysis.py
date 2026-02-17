from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import yfinance as yf

import config
from src.db import cache_get, cache_set, cache_get_raw
from src import scoring


def get_stock_data(ticker: str) -> dict:
    ticker = ticker.upper().strip()
    key = f"stock_{ticker}"
    cached = cache_get(key, config.CACHE_TTL["stock"])
    if cached:
        return cached

    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        # 가격 이력 (5년, ATH 계산용)
        hist_5y = t.history(period="5y")
        if hist_5y.empty:
            raise ValueError(f"{ticker} 데이터 없음")

        # 현재가: regularMarketPrice(실시간) → currentPrice → 과거 이력 종가 순으로 사용
        raw_price = (
            info.get("regularMarketPrice")
            or info.get("currentPrice")
            or float(hist_5y["Close"].iloc[-1])
        )
        current_price = round(float(raw_price), 2)

        ath = round(float(hist_5y["High"].max()), 2)
        ath_date = str(hist_5y["High"].idxmax().date())
        high_52w = round(float(hist_5y["High"].iloc[-252:].max()), 2)

        ath_drawdown = round((current_price - ath) / ath * 100, 1)
        high_52w_drawdown = round((current_price - high_52w) / high_52w * 100, 1)

        # 이동평균 계산 (5년 전체 기준 → 1년 차트에 정확하게 반영)
        import pandas as pd
        closes_5y = hist_5y["Close"]
        ma20  = closes_5y.rolling(20).mean()    # 20일 이동평균
        ma60  = closes_5y.rolling(60).mean()    # 60일 이동평균
        ma120 = closes_5y.rolling(120).mean()   # 120일 이동평균

        # 1년 가격·거래량·이동평균 이력 (차트용, 전체 거래일 포함)
        hist_1y   = hist_5y.iloc[-252:]
        ma20_1y   = ma20.iloc[-252:]
        ma60_1y   = ma60.iloc[-252:]
        ma120_1y  = ma120.iloc[-252:]

        price_history = []
        for i in range(len(hist_1y)):
            row = hist_1y.iloc[i]
            price_history.append({
                "date":   str(hist_1y.index[i].date()),
                "close":  round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
                # NaN이면 None (MA 계산 초반 구간)
                "ma20":   round(float(ma20_1y.iloc[i]),  2) if not pd.isna(ma20_1y.iloc[i])  else None,
                "ma60":   round(float(ma60_1y.iloc[i]),  2) if not pd.isna(ma60_1y.iloc[i])  else None,
                "ma120":  round(float(ma120_1y.iloc[i]), 2) if not pd.isna(ma120_1y.iloc[i]) else None,
            })

        # 펀더멘탈
        forward_pe        = _safe_round(info.get("forwardPE"))
        trailing_pe       = _safe_round(info.get("trailingPE"))
        eps_growth        = _safe_pct(info.get("earningsGrowth"))
        revenue_growth    = _safe_pct(info.get("revenueGrowth"))
        free_cash_flow    = info.get("freeCashflow")
        fcf_positive      = bool(free_cash_flow and free_cash_flow > 0)
        # ROE: 자기자본이익률 (%) — 높을수록 자본 효율성 좋음
        roe = _safe_pct(info.get("returnOnEquity"))
        # PEG: PER ÷ EPS성장률 — 1 미만이면 성장 대비 저평가
        peg = _safe_round(info.get("trailingPegRatio") or info.get("pegRatio"), 2)

        # 애널리스트 의견 (info 기반)
        analyst_count   = info.get("numberOfAnalystOpinions", 0) or 0
        target_price    = _safe_round(info.get("targetMeanPrice"))
        upside_pct      = None
        if target_price and current_price:
            upside_pct = round((target_price - current_price) / current_price * 100, 1)

        # recommendations DataFrame → 최근 등급 집계
        strong_buy = buy = hold = sell = strong_sell = 0
        buy_ratio  = None
        try:
            rec = t.recommendations
            if rec is not None and not rec.empty:
                # 최근 1개 기간
                latest = rec.iloc[-1]
                strong_buy   = int(latest.get("strongBuy", 0))
                buy          = int(latest.get("buy", 0))
                hold         = int(latest.get("hold", 0))
                sell         = int(latest.get("sell", 0))
                strong_sell  = int(latest.get("strongSell", 0))
                total = strong_buy + buy + hold + sell + strong_sell
                if total > 0:
                    analyst_count = total
                    buy_ratio = round((strong_buy + buy) / total * 100, 1)
        except Exception:
            pass

        is_etf = (info.get("quoteType", "").upper() == "ETF")

        # ETF 전용 지표
        ytd_return        = _safe_pct(info.get("ytdReturn"))
        three_year_return = _safe_pct(info.get("threeYearAverageReturn"))
        total_assets      = info.get("totalAssets")   # AUM (달러)

        result = {
            "ticker":          ticker,
            "name":            info.get("longName") or info.get("shortName") or ticker,
            "current_price":   current_price,
            "currency":        info.get("currency", "USD"),
            "sector":          info.get("sector", ""),
            "industry":        info.get("industry", ""),
            "is_etf":          is_etf,
            "ytd_return":      ytd_return,
            "three_year_return": three_year_return,
            "total_assets":    total_assets,
            # 낙폭
            "ath":                   ath,
            "ath_date":              ath_date,
            "high_52w":              high_52w,
            "ath_drawdown_pct":      ath_drawdown,
            "high_52w_drawdown_pct": high_52w_drawdown,
            # 펀더멘탈
            "forward_pe":        forward_pe,
            "trailing_pe":       trailing_pe,
            "eps_growth_pct":    eps_growth,
            "revenue_growth_pct": revenue_growth,
            "free_cash_flow":    free_cash_flow,
            "fcf_positive":      fcf_positive,
            "roe":               roe,    # 자기자본이익률 (%)
            "peg":               peg,    # PER/EPS성장률
            # 애널리스트
            "analyst_count":    analyst_count,
            "strong_buy":       strong_buy,
            "buy":              buy,
            "hold":             hold,
            "sell":             sell,
            "strong_sell":      strong_sell,
            "buy_ratio_pct":    buy_ratio,
            "target_price":     target_price,
            "target_upside_pct": upside_pct,
            # 차트
            "price_history": price_history,
            "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "error": None,
        }
        cache_set(key, result)
        return result

    except Exception as e:
        fallback = cache_get_raw(key)
        if fallback:
            return fallback
        return {
            "ticker": ticker, "name": ticker,
            "current_price": None, "error": str(e),
            "ath_drawdown_pct": None, "buy_ratio_pct": None,
            "forward_pe": None, "fcf_positive": None,
        }


def get_batch_prices(tickers: list[str]) -> dict:
    """
    여러 종목 현재가를 한 번의 API 호출로 가져오는 배치 함수.
    프리마켓·애프터마켓 포함(prepost=True).
    캐시 키: price_batch, TTL: 10초

    반환: {ticker: {"price": float, "prev_close": float, "change_pct": float}, ...}
    """
    if not tickers:
        return {}

    cache_key = "price_batch_" + "_".join(sorted(tickers))
    cached = cache_get(cache_key, config.CACHE_TTL["price"])
    if cached:
        return cached

    result = {}
    try:
        # 여러 종목을 한 번에 다운로드 (prepost=True: 프리/애프터마켓 포함)
        ticker_str = " ".join(tickers)
        hist = yf.download(
            ticker_str,
            period="2d",           # 2일치 (전일 종가 비교용)
            interval="1m",
            prepost=True,          # 프리/애프터마켓 포함
            group_by="ticker",     # 종목별 그룹화
            auto_adjust=True,
            progress=False,
        )

        for ticker in tickers:
            try:
                # 종목별 데이터 추출 (1개일 때와 여러 개일 때 구조가 다름)
                if len(tickers) == 1:
                    df = hist
                else:
                    df = hist[ticker]

                if df.empty:
                    result[ticker] = None
                    continue

                # 오늘(프리마켓 포함) 최신 가격
                current = round(float(df["Close"].dropna().iloc[-1]), 2)

                # 전일 정규 종가: 어제 데이터의 마지막 종가
                today = df.index[-1].date()
                prev_df = df[df.index.normalize().date < today] if hasattr(df.index[0], 'date') else df
                # 날짜 기준 전일 종가 계산
                prev_close = None
                try:
                    dates = df.index.normalize()
                    unique_dates = sorted(set(dates.date))
                    if len(unique_dates) >= 2:
                        prev_date = unique_dates[-2]
                        prev_rows = df[dates.date == prev_date]
                        if not prev_rows.empty:
                            prev_close = round(float(prev_rows["Close"].dropna().iloc[-1]), 2)
                except Exception:
                    pass

                # 전일 대비 변동률
                change_pct = None
                if prev_close and prev_close > 0:
                    change_pct = round((current - prev_close) / prev_close * 100, 2)

                result[ticker] = {
                    "price":      current,
                    "prev_close": prev_close,
                    "change_pct": change_pct,
                }
            except Exception:
                result[ticker] = None

    except Exception:
        # 배치 실패 시 개별 조회로 폴백
        for ticker in tickers:
            try:
                fi = yf.Ticker(ticker).fast_info
                price = getattr(fi, "last_price", None) or getattr(fi, "previous_close", None)
                result[ticker] = {"price": round(float(price), 2), "prev_close": None, "change_pct": None} if price else None
            except Exception:
                result[ticker] = None

    cache_set(cache_key, result)
    return result


def get_live_prices(tickers: list[str]) -> dict:
    """
    여러 종목의 현재가를 병렬로 빠르게 가져오는 함수.
    캐시 TTL: CACHE_TTL["price"] (기본 10초).

    반환: {ticker: current_price, ...}
    """
    def _fetch_one(ticker):
        key = f"price_{ticker}"
        cached = cache_get(key, config.CACHE_TTL["price"])
        if cached:
            return ticker, cached.get("price")
        try:
            hist = yf.Ticker(ticker).history(
                period="1d", interval="1m", prepost=True
            )
            price = float(hist["Close"].iloc[-1]) if not hist.empty else None

            if not price:
                price = getattr(yf.Ticker(ticker).fast_info, "last_price", None)
            if not price:
                price = getattr(yf.Ticker(ticker).fast_info, "previous_close", None)

            if price:
                price = round(float(price), 2)
                cache_set(key, {"price": price})
            return ticker, price
        except Exception:
            return ticker, None

    # 모든 티커 병렬 조회
    with ThreadPoolExecutor(max_workers=min(len(tickers), 8)) as ex:
        return dict(ex.map(_fetch_one, tickers))


def enrich_watchlist(tickers: list[str], fear_score: int,
                     yield_spread=None) -> list[dict]:
    """
    Watchlist 종목 전체 데이터 수집 + 추천 점수, 점수 내림차순 정렬.

    초기 렌더링은 6시간 캐시 데이터를 병렬 조회 → 즉시 반환.
    실시간 가격은 /api/prices AJAX(10초)가 담당하므로 live_prices 불필요.
    """
    if not tickers:
        return []

    # 모든 종목 데이터를 동시에 병렬 조회 (캐시 적중 시 즉시 반환)
    with ThreadPoolExecutor(max_workers=min(len(tickers), 8)) as ex:
        stock_futures = {ticker: ex.submit(get_stock_data, ticker) for ticker in tickers}

    results = []
    for ticker in tickers:
        data = stock_futures[ticker].result()
        score_data = scoring.calc_recommendation_score(fear_score, data,
                                                       yield_spread=yield_spread)
        results.append({**data, **score_data})

    results.sort(key=lambda x: x.get("total_score") or 0, reverse=True)
    return results


def _safe_round(val, digits=2):
    try:
        return round(float(val), digits) if val is not None else None
    except Exception:
        return None


def _safe_pct(val):
    try:
        return round(float(val) * 100, 1) if val is not None else None
    except Exception:
        return None
