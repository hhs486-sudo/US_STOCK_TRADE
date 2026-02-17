from src.db import get_conn, PH


def get_all() -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, ticker, name, asset_type, memo, added_at FROM watchlist ORDER BY added_at DESC"
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_tickers() -> list[str]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT ticker FROM watchlist")
        rows = cur.fetchall()
    finally:
        conn.close()
    return [r["ticker"] for r in rows]


def add(ticker: str, name: str = "", asset_type: str = "stock", memo: str = "") -> bool:
    ticker = ticker.upper().strip()
    try:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO watchlist (ticker, name, asset_type, memo) VALUES ({PH}, {PH}, {PH}, {PH})",
                (ticker, name, asset_type, memo),
            )
            conn.commit()
        finally:
            conn.close()
        return True
    except Exception:
        return False


def delete(ticker: str) -> bool:
    ticker = ticker.upper().strip()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM watchlist WHERE ticker = {PH}", (ticker,))
        conn.commit()
    finally:
        conn.close()
    return True


def exists(ticker: str) -> bool:
    ticker = ticker.upper().strip()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT 1 FROM watchlist WHERE ticker = {PH}", (ticker,))
        row = cur.fetchone()
    finally:
        conn.close()
    return row is not None
