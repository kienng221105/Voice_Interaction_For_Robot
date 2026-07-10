@echo off
chcp 65001 >nul
title Khoi dong Voice Vending Machine (Giai doan 5)

echo ===================================================
echo   KHOI DONG HE THONG VOICE VENDING MACHINE (CLOUD AI)
echo ===================================================

echo.
echo [1/3] Kiem tra va giai phong Port 8000 (Local Server)...
powershell -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"

echo.
echo [2/3] Dang bat Mock ESP32 (Ket noi toi MQTT localhost)...
start "ESP32 Mock Hardware" cmd /k "python -u run_mock_esp.py"

echo.
echo [3/4] Dang bat Local NLP Server (STT + LLM)...
start "NLP Server" cmd /k "python -u nlp_server.py --port 8765"

echo.
echo [4/4] Dang bat Local Client Web Server (FastAPI)...
start "Client Web Server" cmd /k "python -m uvicorn client.web_app:app --host 127.0.0.1 --port 8000 --reload"

echo.
echo Dang mo giao dien Kiosk tren trinh duyet...
timeout /t 3 /nobreak >nul
start "" "http://localhost:8000/"

echo.
echo Hoan tat! Giao dien se tu dong hien thi.
echo (He thong dang ket noi truc tiep len Cloud Run AI!)
echo.
pause
