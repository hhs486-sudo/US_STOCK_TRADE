---
description: Flask 서버 시작/재시작. 포트 충돌 정리 후 app.py 실행
---

미국주식 추천 시스템 Flask 서버를 시작합니다.

다음 순서로 진행하세요:

1. 기존 Python 프로세스(포트 5000) 정리
   - Windows: `taskkill //F //IM python.exe`
   - 포트 확인: `netstat -ano | grep ":5000"`

2. 서버 시작
   ```
   cd E:/Python/Invest_US_stocks
   python app.py
   ```

3. 정상 기동 확인
   - `curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/` → 200 확인

4. 결과 보고
   - 접속 URL: http://localhost:5000
   - 시작 실패 시 에러 메시지 출력
