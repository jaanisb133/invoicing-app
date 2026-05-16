@echo off
title V-Rekini Offline

echo.
echo  ==========================================
echo          V-Rekini - Offline rezims
echo  ==========================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    py --version >nul 2>&1
    if errorlevel 1 (
        echo  [!] Python nav atrasts.
        echo      Lejupieladejiet no: https://www.python.org/downloads/
        echo      Instalejot atzimejiet "Add Python to PATH"
        echo.
        pause
        exit /b 1
    )
    set PYTHON=py
) else (
    set PYTHON=python
)

:: Install dependencies if needed (check for fastapi as indicator)
%PYTHON% -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo  Instale nepieciesamas bibliotekas...
    %PYTHON% -m pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo  [!] Kluda instalejot bibliotekas.
        pause
        exit /b 1
    )
    echo  Bibliotekas instaletas veiksmigi.
    echo.
)

:: Launch the app
%PYTHON% run_offline.py
pause
