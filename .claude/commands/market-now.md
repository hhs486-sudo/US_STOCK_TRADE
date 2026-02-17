---
description: 현재 시장 심리 지표(Fear & Greed, VIX, RSI, CPI) 빠른 확인
---

현재 시장 심리 지표를 조회합니다.

다음 Python 코드를 E:/Python/Invest_US_stocks 에서 실행하세요:

```python
import sys
sys.path.insert(0, 'E:/Python/Invest_US_stocks')
sys.stdout.reconfigure(encoding='utf-8')
from src.db import init_db
init_db()
from src.market_sentiment import get_fear_greed, get_vix, get_market_rsi, get_cpi, get_fear_score

fg  = get_fear_greed()
vix = get_vix()
rsi = get_market_rsi()
cpi = get_cpi()
score = get_fear_score()

print("=== 시장 심리 현황 ===")
print(f"CNN Fear & Greed : {fg['value']} ({fg['label']})  [1주전 {fg.get('prev_1w','N/A')}, 1달전 {fg.get('prev_1m','N/A')}]")
print(f"VIX              : {vix['current']} ({vix['level']})  전일대비 {vix.get('change_pct','N/A')}%")
print(f"S&P500 RSI       : {rsi['sp500']['rsi']} ({rsi['sp500']['level']})")
print(f"NASDAQ RSI       : {rsi['nasdaq']['rsi']} ({rsi['nasdaq']['level']})")
if cpi.get('available'):
    print(f"CPI (YoY)        : {cpi['latest_value']}% ({cpi['latest_date']})  추세: {cpi['trend']}")
print()
print(f"공포 종합 점수   : {score}/100")
if score >= 70:   print("→ 🔴 강력 매수 기회")
elif score >= 50: print("→ 🟠 매수 고려 구간")
elif score >= 30: print("→ 🔵 주의 구간")
else:             print("→ 🟢 안정 구간")
```

결과를 표 형태로 정리해서 보여주세요.
