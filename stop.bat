@echo off
REM Patent Gap - Stop Script

echo 🛑 Stopping Patent Gap Application...

REM Find and kill any running Python processes with app.py
taskkill /f /im python.exe /fi "WINDOWTITLE eq app.py" 2>nul
echo ✅ Application stopped
pause
