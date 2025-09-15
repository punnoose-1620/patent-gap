@echo off
REM Patent Gap - Run Script

echo 🚀 Starting Patent Gap Application...

REM Check if virtual environment exists
if not exist "venv" (
    echo ❌ Virtual environment not found. Please run install.bat first.
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Change to Backend directory and run the app
cd Backend
python app.py
pause
