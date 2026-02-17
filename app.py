from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

import requests
import config
from src.db import init_db
from src import watchlist, market_sentiment, stock_analysis

app = Flask(__name__)
app.secret_key = "invest-secret-key"


@app.before_request
def setup():
    init_db()


@app.route("/")
def index():
    fear_greed   = market_sentiment.get_fear_greed()
    vix          = market_sentiment.get_vix()
    market_rsi   = market_sentiment.get_market_rsi()
    cpi          = market_sentiment.get_cpi()
    yield_curve  = market_sentiment.get_yield_curve()
    fear_score   = market_sentiment.get_fear_score()

    tickers = watchlist.get_tickers()
    yield_spread = yield_curve.get("spread") if yield_curve.get("available") else None
    stocks  = stock_analysis.enrich_watchlist(tickers, fear_score,
                                              yield_spread=yield_spread) if tickers else []

    return render_template(
        "index.html",
        fear_greed=fear_greed,
        vix=vix,
        market_rsi=market_rsi,
        cpi=cpi,
        yield_curve=yield_curve,
        fear_score=fear_score,
        stocks=stocks,
    )


@app.route("/stock/<ticker>")
def stock_detail(ticker):
    fear_score  = market_sentiment.get_fear_score()
    yield_curve = market_sentiment.get_yield_curve()
    stock_data  = stock_analysis.get_stock_data(ticker.upper())

    from src.scoring import calc_recommendation_score
    yield_spread = yield_curve.get("spread") if yield_curve.get("available") else None
    score = calc_recommendation_score(fear_score, stock_data, yield_spread=yield_spread)

    return render_template(
        "stock_detail.html",
        stock=stock_data,
        score=score,
        fear_score=fear_score,
        yield_curve=yield_curve,
    )


@app.route("/watchlist")
def watchlist_page():
    items = watchlist.get_all()
    return render_template("watchlist.html", items=items)


@app.route("/watchlist/add", methods=["POST"])
def watchlist_add():
    ticker     = request.form.get("ticker", "").strip().upper()
    asset_type = request.form.get("asset_type", "stock")
    memo       = request.form.get("memo", "").strip()

    if not ticker:
        flash("티커를 입력해 주세요.", "error")
        return redirect(url_for("watchlist_page"))

    # yfinance로 종목명 조회 시도
    name = ticker
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        name = info.get("longName") or info.get("shortName") or ticker
    except Exception:
        pass

    if watchlist.add(ticker, name, asset_type, memo):
        flash(f"{ticker} ({name}) 추가됐습니다.", "success")
    else:
        flash(f"{ticker} 는 이미 등록된 종목입니다.", "error")

    return redirect(url_for("watchlist_page"))


@app.route("/watchlist/delete", methods=["POST"])
def watchlist_delete():
    ticker = request.form.get("ticker", "").strip().upper()
    if ticker:
        watchlist.delete(ticker)
        flash(f"{ticker} 삭제됐습니다.", "success")
    return redirect(url_for("watchlist_page"))


@app.route("/api/prices")
def api_prices():
    """
    Watchlist 전체 종목의 현재가를 JSON으로 반환 (AJAX 전용).
    프리마켓·애프터마켓 포함, 10초 캐시.

    응답 예시:
        {
            "AAPL": {"price": 255.78, "prev_close": 254.0, "change_pct": 0.70},
            "MSFT": {"price": 400.17, "prev_close": 401.32, "change_pct": -0.29}
        }
    """
    tickers = watchlist.get_tickers()
    if not tickers:
        return jsonify({})

    from src.stock_analysis import get_batch_prices
    prices = get_batch_prices(tickers)
    return jsonify(prices)


@app.route("/api/search")
def api_search():
    """
    키워드로 종목을 검색하는 API.
    Yahoo Finance 검색 엔드포인트를 사용해 실시간 검색 결과 반환.

    파라미터:
        q (str): 검색 키워드 (예: "apple", "AAPL", "삼성")

    응답 예시:
        [
            {"ticker": "AAPL", "name": "Apple Inc.", "exchange": "NMS", "type": "EQUITY"},
            {"ticker": "AAPL.BA", "name": "Apple Inc.", "exchange": "BUE", "type": "EQUITY"},
            ...
        ]
    """
    query = request.args.get("q", "").strip()
    if len(query) < 1:
        return jsonify([])

    try:
        # Yahoo Finance 비공개 검색 API 호출
        url = "https://query1.finance.yahoo.com/v1/finance/search"
        params = {
            "q": query,          # 검색어
            "quotesCount": 8,    # 최대 종목 수
            "newsCount": 0,      # 뉴스 결과 제외
            "listsCount": 0,     # 리스트 결과 제외
        }
        headers = {
            # Yahoo Finance가 일반 브라우저 요청처럼 인식하게 처리
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        data = resp.json()

        results = []
        for q in data.get("quotes", []):
            # 주식(EQUITY)과 ETF만 필터링, 거래소 코드 없는 항목 제외
            q_type = q.get("quoteType", "")
            if q_type not in ("EQUITY", "ETF"):
                continue

            # 종목 유형 판별 (etf / stock)
            asset_type = "etf" if q_type == "ETF" else "stock"

            results.append({
                "ticker":     q.get("symbol", ""),
                "name":       q.get("longname") or q.get("shortname") or q.get("symbol", ""),
                "exchange":   q.get("exchange", ""),
                "asset_type": asset_type,
            })

        return jsonify(results)

    except Exception as e:
        # 검색 실패 시 빈 배열 반환 (UI에서 오류 없이 처리)
        return jsonify([])


@app.route("/api/refresh")
def api_refresh():
    """캐시 무효화 후 메인으로 리다이렉트."""
    from src.db import get_conn
    with get_conn() as conn:
        conn.execute("DELETE FROM cache")
    flash("데이터가 갱신됩니다. 잠시 후 페이지를 새로고침하세요.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(debug=config.FLASK_DEBUG, port=config.FLASK_PORT)
