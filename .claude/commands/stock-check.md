---
description: 특정 종목의 현재 분석 결과 출력. 사용법: /stock-check AAPL
argument-hint: <ticker>
---

종목 **$ARGUMENTS** 의 현재 분석 결과를 출력합니다.

다음 Python 코드를 E:/Python/Invest_US_stocks 에서 실행하세요:

```python
import sys
sys.path.insert(0, 'E:/Python/Invest_US_stocks')
sys.stdout.reconfigure(encoding='utf-8')
from src.db import init_db
init_db()
from src.market_sentiment import get_fear_score
from src.stock_analysis import get_stock_data
from src.scoring import calc_recommendation_score

ticker = "$ARGUMENTS".upper()
fear_score = get_fear_score()
data = get_stock_data(ticker)
score = calc_recommendation_score(fear_score, data)

print(f"=== {ticker} 분석 결과 ===")
if data.get('error'):
    print(f"오류: {data['error']}")
else:
    print(f"현재가     : ${data['current_price']}")
    print(f"ATH        : ${data['ath']} ({data['ath_date']})")
    print(f"ATH 대비   : {data['ath_drawdown_pct']}%")
    print(f"Forward PE : {data.get('forward_pe', 'N/A')}")
    print(f"Buy 비율   : {data.get('buy_ratio_pct', 'N/A')}%")
    print(f"목표주가   : ${data.get('target_price', 'N/A')}")
    print()
    print(f"공포 점수  : {score['fear_score']}/100")
    print(f"낙폭 점수  : {score['drawdown_score']}/100")
    print(f"펀더멘탈   : {score['fundamental_score']}/100")
    print(f"종합 점수  : {score['total_score']}/100  [{score['grade']}]")
    print(f"근거       : {score['reason']}")
```

결과를 보기 좋게 정리해서 보여주세요.
