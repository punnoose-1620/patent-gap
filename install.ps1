# Patent Gap - PowerShell Installation Script
# This script sets up a virtual environment and installs all required dependencies

Write-Host "🚀 Patent Gap - Installation Script" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Green

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Python not found"
    }
    Write-Host "✅ $pythonVersion detected" -ForegroundColor Green
} catch {
    Write-Host "❌ Python is not installed or not in PATH. Please install Python 3.7 or higher." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Create virtual environment
Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "⚠️  Virtual environment already exists. Removing old one..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force "venv"
}

python -m venv venv
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to create virtual environment" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "✅ Virtual environment created" -ForegroundColor Green

# Activate virtual environment
Write-Host "🔧 Activating virtual environment..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"

# Upgrade pip
Write-Host "⬆️  Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Install requirements
Write-Host "📚 Installing Python dependencies..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to install dependencies" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "✅ Dependencies installed from requirements.txt" -ForegroundColor Green
} else {
    Write-Host "❌ requirements.txt not found!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Create necessary directories
Write-Host "📁 Creating necessary directories..." -ForegroundColor Yellow
@("Assets", "Backend\logs", "Frontend\assets", "Frontend\css", "Frontend\js") | ForEach-Object {
    if (-not (Test-Path $_)) {
        New-Item -ItemType Directory -Path $_ -Force | Out-Null
    }
}

# Create .env file if it doesn't exist
if (-not (Test-Path "Backend\.env")) {
    Write-Host "⚙️  Creating .env file..." -ForegroundColor Yellow
    if (Test-Path "Backend\env_example.txt") {
        Copy-Item "Backend\env_example.txt" "Backend\.env"
        Write-Host "✅ .env file created from template" -ForegroundColor Green
    } else {
        Write-Host "⚠️  env_example.txt not found, creating basic .env file..." -ForegroundColor Yellow
        @"
# Patent Gap Environment Configuration
SECRET_KEY=your-secret-key-change-this-in-production
PORT=5000
DEBUG=True
FLASK_ENV=development
"@ | Out-File -FilePath "Backend\.env" -Encoding UTF8
        Write-Host "✅ Basic .env file created" -ForegroundColor Green
    }
} else {
    Write-Host "✅ .env file already exists" -ForegroundColor Green
}

# Create run script
Write-Host "📝 Creating run script..." -ForegroundColor Yellow
@"
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
"@ | Out-File -FilePath "run.bat" -Encoding ASCII

# Create development run script
Write-Host "📝 Creating development run script..." -ForegroundColor Yellow
@"
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
"@ | Out-File -FilePath "run-dev.bat" -Encoding ASCII

# Create stop script
Write-Host "📝 Creating stop script..." -ForegroundColor Yellow
@"
@echo off
REM Patent Gap - Stop Script

echo 🛑 Stopping Patent Gap Application...

REM Find and kill any running Python processes with app.py
taskkill /f /im python.exe /fi "WINDOWTITLE eq app.py" 2>nul
echo ✅ Application stopped
pause
"@ | Out-File -FilePath "stop.bat" -Encoding ASCII

# Create PowerShell run script
Write-Host "📝 Creating PowerShell run script..." -ForegroundColor Yellow
@"
# Patent Gap - PowerShell Run Script

Write-Host "🚀 Starting Patent Gap Application..." -ForegroundColor Green

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "❌ Virtual environment not found. Please run install.ps1 first." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Activate virtual environment
& "venv\Scripts\Activate.ps1"

# Change to Backend directory and run the app
Set-Location Backend
python app.py
"@ | Out-File -FilePath "run.ps1" -Encoding UTF8

# Display installation summary
Write-Host ""
Write-Host "🎉 Installation Complete!" -ForegroundColor Green
Write-Host "========================" -ForegroundColor Green
Write-Host ""
Write-Host "📁 Project Structure:" -ForegroundColor Cyan
Write-Host "   ├── venv\                 # Virtual environment" -ForegroundColor White
Write-Host "   ├── Backend\              # Python backend" -ForegroundColor White
Write-Host "   ├── Frontend\             # HTML frontend" -ForegroundColor White
Write-Host "   ├── Assets\               # Static assets" -ForegroundColor White
Write-Host "   ├── run.bat              # Production run script" -ForegroundColor White
Write-Host "   ├── run-dev.bat          # Development run script" -ForegroundColor White
Write-Host "   ├── run.ps1              # PowerShell run script" -ForegroundColor White
Write-Host "   └── stop.bat             # Stop script" -ForegroundColor White
Write-Host ""
Write-Host "🚀 To start the application:" -ForegroundColor Cyan
Write-Host "   .\run.bat                  # Production mode (Batch)" -ForegroundColor White
Write-Host "   .\run-dev.bat              # Development mode (Batch)" -ForegroundColor White
Write-Host "   .\run.ps1                  # PowerShell mode" -ForegroundColor White
Write-Host ""
Write-Host "🛑 To stop the application:" -ForegroundColor Cyan
Write-Host "   .\stop.bat" -ForegroundColor White
Write-Host ""
Write-Host "🔧 To activate virtual environment manually:" -ForegroundColor Cyan
Write-Host "   venv\Scripts\activate.bat  # Batch" -ForegroundColor White
Write-Host "   venv\Scripts\Activate.ps1  # PowerShell" -ForegroundColor White
Write-Host ""
Write-Host "📖 For more information, see README.md" -ForegroundColor Cyan
Write-Host ""
Write-Host "✅ Ready to go! Happy coding! 🎯" -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to continue"
