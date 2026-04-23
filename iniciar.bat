@echo off
title MedControl - Sistema de Auditoría de Medicamentos
cd /d "%~dp0"
chcp 65001 >nul

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║        MedControl - Iniciando servidor       ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: Resolver comando de Python
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

:: Crear entorno virtual si no existe
if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual (.venv)...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

:: Activar venv
call ".venv\Scripts\activate.bat"

:: Instalar dependencias
echo Instalando/actualizando dependencias...
python -m pip install --upgrade pip
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

:: Abrir el navegador despues de 2 segundos
start /b "" cmd /c "timeout /t 2 >nul && start http://localhost:5000"

:: Iniciar Flask
python app.py

pause
