@echo off
REM Patent Gap - Development Run Script

echo 🚀 Starting Patent Gap Application (Development Mode)...

REM Check if virtual environment exists
if not exist "venv" (
    echo ❌ Virtual environment not found. Please run install.bat first.
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Set development environment variables
set FLASK_ENV=development
set FLASK_DEBUG=1

REM Change to Backend directory and run the app
cd Backend
python app.py
pause
