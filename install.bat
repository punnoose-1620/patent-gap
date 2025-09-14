@echo off
REM Patent Gap - Windows Installation Script
REM This script sets up a virtual environment and installs all required dependencies

echo 🚀 Patent Gap - Installation Script
echo ==================================

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH. Please install Python 3.7 or higher.
    pause
    exit /b 1
)

echo ✅ Python detected

REM Create virtual environment
echo 📦 Creating virtual environment...
if exist "venv" (
    echo ⚠️  Virtual environment already exists. Removing old one...
    rmdir /s /q venv
)

python -m venv venv
if errorlevel 1 (
    echo ❌ Failed to create virtual environment
    pause
    exit /b 1
)
echo ✅ Virtual environment created

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo ⬆️  Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo 📚 Installing Python dependencies...
if exist "requirements.txt" (
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ Failed to install dependencies
        pause
        exit /b 1
    )
    echo ✅ Dependencies installed from requirements.txt
) else (
    echo ❌ requirements.txt not found!
    pause
    exit /b 1
)

REM Create necessary directories
echo 📁 Creating necessary directories...
if not exist "Assets" mkdir Assets
if not exist "Backend\logs" mkdir Backend\logs
if not exist "Frontend\assets" mkdir Frontend\assets
if not exist "Frontend\css" mkdir Frontend\css
if not exist "Frontend\js" mkdir Frontend\js

REM Create .env file if it doesn't exist
if not exist "Backend\.env" (
    echo ⚙️  Creating .env file...
    if exist "Backend\env_example.txt" (
        copy "Backend\env_example.txt" "Backend\.env" >nul
        echo ✅ .env file created from template
    ) else (
        echo ⚠️  env_example.txt not found, creating basic .env file...
        (
            echo # Patent Gap Environment Configuration
            echo SECRET_KEY=your-secret-key-change-this-in-production
            echo PORT=5000
            echo DEBUG=True
            echo FLASK_ENV=development
        ) > "Backend\.env"
        echo ✅ Basic .env file created
    )
) else (
    echo ✅ .env file already exists
)

REM Create run script
echo 📝 Creating run script...
(
    echo @echo off
    echo REM Patent Gap - Run Script
    echo.
    echo echo 🚀 Starting Patent Gap Application...
    echo.
    echo REM Check if virtual environment exists
    echo if not exist "venv" ^(
    echo     echo ❌ Virtual environment not found. Please run install.bat first.
    echo     pause
    echo     exit /b 1
    echo ^)
    echo.
    echo REM Activate virtual environment
    echo call venv\Scripts\activate.bat
    echo.
    echo REM Change to Backend directory and run the app
    echo cd Backend
    echo python app.py
    echo pause
) > run.bat

REM Create development run script
echo 📝 Creating development run script...
(
    echo @echo off
    echo REM Patent Gap - Development Run Script
    echo.
    echo echo 🚀 Starting Patent Gap Application ^(Development Mode^)...
    echo.
    echo REM Check if virtual environment exists
    echo if not exist "venv" ^(
    echo     echo ❌ Virtual environment not found. Please run install.bat first.
    echo     pause
    echo     exit /b 1
    echo ^)
    echo.
    echo REM Activate virtual environment
    echo call venv\Scripts\activate.bat
    echo.
    echo REM Set development environment variables
    echo set FLASK_ENV=development
    echo set FLASK_DEBUG=1
    echo.
    echo REM Change to Backend directory and run the app
    echo cd Backend
    echo python app.py
    echo pause
) > run-dev.bat

REM Create stop script
echo 📝 Creating stop script...
(
    echo @echo off
    echo REM Patent Gap - Stop Script
    echo.
    echo echo 🛑 Stopping Patent Gap Application...
    echo.
    echo REM Find and kill any running Python processes with app.py
    echo taskkill /f /im python.exe /fi "WINDOWTITLE eq app.py" 2^>nul
    echo echo ✅ Application stopped
    echo pause
) > stop.bat

REM Display installation summary
echo.
echo 🎉 Installation Complete!
echo ========================
echo.
echo 📁 Project Structure:
echo    ├── venv\                 # Virtual environment
echo    ├── Backend\              # Python backend
echo    ├── Frontend\             # HTML frontend
echo    ├── Assets\               # Static assets
echo    ├── run.bat              # Production run script
echo    ├── run-dev.bat          # Development run script
echo    └── stop.bat             # Stop script
echo.
echo 🚀 To start the application:
echo    run.bat                  # Production mode
echo    run-dev.bat              # Development mode
echo.
echo 🛑 To stop the application:
echo    stop.bat
echo.
echo 🔧 To activate virtual environment manually:
echo    venv\Scripts\activate.bat
echo.
echo 📖 For more information, see README.md
echo.
echo ✅ Ready to go! Happy coding! 🎯
echo.
pause
