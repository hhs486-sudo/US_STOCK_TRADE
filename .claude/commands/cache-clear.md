---
description: 캐시 초기화. 인수 없으면 전체, 종목명 입력 시 해당 종목만. 예) /cache-clear AAPL
argument-hint: [ticker|all]
---

캐시를 초기화합니다.

입력값: `$ARGUMENTS`

- 인수 없음 또는 "all" → 전체 캐시 삭제
- 종목 티커 → 해당 종목 캐시만 삭제
- "market" → 시장 지표 캐시만 삭제 (fear_greed, vix, market_rsi, cpi)

다음 Python 코드를 E:/Python/Invest_US_stocks 에서 실행하세요:

```python
import sys
sys.path.insert(0, 'E:/Python/Invest_US_stocks')
sys.stdout.reconfigure(encoding='utf-8')
from src.db import init_db, get_conn
init_db()

arg = "$ARGUMENTS".strip().upper()

with get_conn() as conn:
    if not arg or arg == "ALL":
        conn.execute("DELETE FROM cache")
        print("✅ 전체 캐시 삭제 완료")
    elif arg == "MARKET":
        conn.execute("DELETE FROM cache WHERE key IN ('fear_greed','vix','market_rsi','cpi')")
        print("✅ 시장 지표 캐시 삭제 완료 (fear_greed, vix, market_rsi, cpi)")
    else:
        conn.execute("DELETE FROM cache WHERE key = ?", (f"stock_{arg}",))
        print(f"✅ {arg} 종목 캐시 삭제 완료")

    rows = conn.execute("SELECT key, updated_at FROM cache ORDER BY updated_at DESC").fetchall()
    if rows:
        print(f"\n남은 캐시 ({len(rows)}개):")
        for r in rows:
            print(f"  {r['key']:<20} {r['updated_at']}")
    else:
        print("\n캐시가 비어 있습니다.")
```

결과를 보여주세요.
