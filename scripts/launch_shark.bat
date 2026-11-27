@echo off
:: SHARK AI - OpenCode Launch Command
:: This replaces the need for "ollama launch"

echo ==========================================
echo     SHARK AI - OpenCode Launcher
echo ==========================================

set "SCRIPT_DIR=%~dp0"
cd "%SCRIPT_DIR%"

:: Check if Python and required packages are available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not available.
    pause
    exit /b 1
)

:: Check if opencode is installed
python -c "import opencode" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing OpenCode...
    pip install opencode >nul
)

:: Check for SHARK model configuration
if not exist "opencode\opencode.json" (
    echo Creating SHARK OpenCode configuration...
    python scripts\shark_launch.py --config opencode\opencode.json
)

:: Launch OpenCode with SHARK model
echo.
echo Launching OpenCode with SHARK AI...
echo.

python scripts\shark_launch.py %*

if %errorlevel% neq 0 (
    echo.
    echo SHARK OpenCode exited with error level %errorlevel%
)
pause