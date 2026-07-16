@echo off
chcp 65001 >nul
title Khoi dong Voice Vending Machine (Giai doan 5)

echo ===================================================
echo   KHOI DONG HE THONG VOICE VENDING MACHINE (CLOUD AI)
echo ===================================================

echo.
echo [1/5] Kiem tra va giai phong Port 8000 va Ngrok...
powershell -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }; Stop-Process -Name 'ngrok' -Force -ErrorAction SilentlyContinue"

echo.
echo [2/5] Da bo qua buoc chay Mock ESP32 vi da co phan cung that!
REM start "ESP32 Mock Hardware" cmd /k "python -u run_mock_esp.py"

echo.
echo [3/5] Dang bat Local NLP Server (STT + LLM)...
start "NLP Server" cmd /k "python -u nlp_server.py --port 8765"

echo.
echo [4/5] Dang bat Local Client Web Server (FastAPI)...
start "Client Web Server" cmd /k "python -m uvicorn client.web_app:app --host 0.0.0.0 --port 8000 --reload"

echo.
echo [5/5] Dang bat Ngrok (Webhook cho PayOS)...
start "Ngrok Webhook" cmd /k ".\ngrok.exe http --domain=hunting-handprint-acetone.ngrok-free.dev 8000"

echo.
echo Dang mo giao dien Kiosk tren trinh duyet...
timeout /t 3 /nobreak >nul
start "" "http://localhost:8000/"

echo.
echo Hoan tat! Giao dien se tu dong hien thi.
echo (He thong dang ket noi truc tiep len Cloud Run AI va PayOS Webhook!)
echo.
pause
