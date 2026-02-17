from src.db import get_conn


def get_all() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, ticker, name, asset_type, memo, added_at FROM watchlist ORDER BY added_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_tickers() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT ticker FROM watchlist").fetchall()
    return [r["ticker"] for r in rows]


def add(ticker: str, name: str = "", asset_type: str = "stock", memo: str = "") -> bool:
    ticker = ticker.upper().strip()
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO watchlist (ticker, name, asset_type, memo) VALUES (?, ?, ?, ?)",
                (ticker, name, asset_type, memo),
            )
        return True
    except Exception:
        return False


def delete(ticker: str) -> bool:
    ticker = ticker.upper().strip()
    with get_conn() as conn:
        conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))
    return True


def exists(ticker: str) -> bool:
    ticker = ticker.upper().strip()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM watchlist WHERE ticker = ?", (ticker,)
        ).fetchone()
    return row is not None
