import os
from dotenv import load_dotenv

# app.py 기준 절대경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))

FRED_API_KEY = os.getenv("FRED_API_KEY", "")
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "data", "invest.db"))

FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))

CACHE_TTL = {
    "fear_greed": int(os.getenv("CACHE_TTL_FEAR_GREED", 3600)),
    "vix":        3600,
    "market_rsi": 3600,
    "cpi":        86400,
    "stock":      int(os.getenv("CACHE_TTL_STOCK", 21600)),
    "price":      int(os.getenv("CACHE_TTL_PRICE", 10)),    # 현재가 전용: 10초 캐시 (AJAX 갱신 주기와 동일)
}
