@echo off
echo Building Patent Gap Backend Executable...
echo.

REM Clean previous build
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

REM Build the executable
python -m PyInstaller run.spec

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Build successful! The executable is located in the 'dist' folder.
    echo You can run it by executing 'dist\run.exe'
    echo.
) else (
    echo.
    echo Build failed! Please check the error messages above.
    echo.
)

pause

