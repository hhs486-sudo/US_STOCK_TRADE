@echo off
cd /d "%~dp0"

echo [미국주식 추천] 기존 서버 종료 중...
powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force"
timeout /t 1 /nobreak >nul

echo [미국주식 추천] 서버 시작 중...
echo http://localhost:5000 에서 확인하세요.
echo 종료하려면 Ctrl+C 를 누르세요.
echo.

python app.py

pause
