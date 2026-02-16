@echo off
REM Build script for Certify Intel Desktop Application (Windows)
REM This script bundles the Python backend and builds the Electron app

echo ========================================
echo  Certify Intel Desktop Build Script
echo ========================================
echo.

REM Check for required tools
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
    echo ERROR: Node.js/npm is not installed or not in PATH
    exit /b 1
)

REM Set version from argument or default
set VERSION=%1
if "%VERSION%"=="" set VERSION=A

echo Building Version: %VERSION%
echo.

REM Step 1: Bundle Python backend
echo [1/5] Bundling Python backend with PyInstaller...
cd ..\backend
pip install pyinstaller --quiet
pyinstaller certify_backend.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: Failed to bundle Python backend
    exit /b 1
)
cd ..\desktop-app

REM Step 2: Copy backend bundle
echo [2/5] Copying backend bundle...
if not exist backend-bundle mkdir backend-bundle
copy /Y ..\backend\dist\certify_backend.exe backend-bundle\

REM Step 3: Copy frontend files
echo [3/5] Copying frontend files...
if not exist frontend mkdir frontend
xcopy /Y /E /I ..\frontend\* frontend\

REM Step 4: Prepare data
echo [4/5] Preparing data...
if not exist data mkdir data
if "%VERSION%"=="A" (
    echo   Using Version A: With data and API keys
    copy /Y ..\backend\competitors.db data\
    copy /Y ..\backend\.env data\
) else (
    echo   Using Version B: Blank template
    REM Create empty database
    echo. > data\competitors.db
    REM Create empty .env template
    echo # API Configuration > data\.env.template
    echo OPENAI_API_KEY= >> data\.env.template
    echo NEWS_API_KEY= >> data\.env.template
)

REM Step 5: Install npm dependencies and build
echo [5/5] Building Electron application...
call npm install
if "%VERSION%"=="A" (
    set BUILD_VERSION=A
    call npm run build:win
) else (
    set BUILD_VERSION=B
    call npm run build:win
)

echo.
echo ========================================
echo  Build Complete!
echo ========================================
echo.
echo Output: .\dist\
dir dist\*.exe 2>nul

pause
