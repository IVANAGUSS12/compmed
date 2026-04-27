@echo off
title MedControl
cd /d "%~dp0"

echo.
echo  ==========================================
echo       MedControl - Iniciando servidor
echo  ==========================================
echo.

set "PY_CMD="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"
if "%PY_CMD%"=="" (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)
if "%PY_CMD%"=="" (
    echo [ERROR] Python no encontrado. Instalalo desde https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

echo Instalando dependencias...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de dependencias.
    pause
    exit /b 1
)

echo.
echo  Servidor iniciado en: http://localhost:5000
echo  Presiona Ctrl+C para detener
echo.

start /b "" cmd /c "timeout /t 2 >nul && start http://localhost:5000"

python app.py
if errorlevel 1 (
    echo.
    echo [ERROR] La aplicacion cerro con un error. Ver mensaje arriba.
)

pause