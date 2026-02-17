---
description: Watchlist에 종목 추가. 사용법: /watchlist-add AAPL stock 장기보유
argument-hint: <ticker> [stock|etf] [메모]
---

Watchlist에 종목을 추가합니다.

입력값: `$ARGUMENTS`

인수를 파싱합니다:
- 첫 번째: 티커 (필수)
- 두 번째: 유형 stock 또는 etf (기본값: stock)
- 나머지: 메모 (선택)

다음 Python 코드를 E:/Python/Invest_US_stocks 에서 실행하세요:

```python
import sys
sys.path.insert(0, 'E:/Python/Invest_US_stocks')
sys.stdout.reconfigure(encoding='utf-8')
args = "$ARGUMENTS".split()
ticker = args[0].upper() if args else ""
asset_type = args[1].lower() if len(args) > 1 and args[1].lower() in ('stock','etf') else 'stock'
memo = ' '.join(args[2:]) if len(args) > 2 else ''

if not ticker:
    print("오류: 티커를 입력하세요. 예) /watchlist-add AAPL stock 장기보유")
    sys.exit(1)

from src.db import init_db
init_db()
from src import watchlist
import yfinance as yf

name = ticker
try:
    info = yf.Ticker(ticker).info or {}
    name = info.get('longName') or info.get('shortName') or ticker
except:
    pass

ok = watchlist.add(ticker, name, asset_type, memo)
if ok:
    print(f"✅ 추가 완료: {ticker} ({name})  유형={asset_type}  메모={memo or '-'}")
else:
    print(f"⚠️  {ticker} 는 이미 등록된 종목입니다.")

print("\n현재 Watchlist:")
for item in watchlist.get_all():
    print(f"  {item['ticker']:<6} [{item['asset_type']:<5}] {item['name'][:30]}")
```

결과를 보여주세요.
