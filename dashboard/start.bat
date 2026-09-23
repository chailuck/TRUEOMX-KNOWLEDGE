@echo off
title TRUEOMX AI Discovery Dashboard
echo.
echo  =====================================================
echo   TRUEOMX AI - Discovery Dashboard
echo  =====================================================
echo.
echo  URL : http://localhost:8080/dashboard/
echo.
echo  Press Ctrl+C to stop the server.
echo  =====================================================
echo.

:: Start browser before server (server blocks)
start "" "http://localhost:8080/dashboard/"

:: Serve from project root so /output/ and /dashboard/ paths resolve correctly
cd /d "%~dp0.."
python -m http.server 8080

pause
