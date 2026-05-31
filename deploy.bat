@echo off
chcp 65001 >nul
echo ==========================================
echo   CRC Analyzer - Deploy para Render
echo ==========================================
echo.

REM Verificar se git esta instalado
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Git nao esta instalado.
    echo Instale em: https://git-scm.com/downloads
    pause
    exit /b 1
)

REM Verificar se existe repositorio
if not exist .git (
    echo [INFO] A inicializar repositorio Git...
    git init
    git branch -M main
    echo.
    echo Por favor, crie um repositorio no GitHub:
    echo   https://github.com/new
    echo.
    set /p repo_url="Introduza a URL do repositorio GitHub: "
    git remote add origin %repo_url%
)

echo [1/3] A adicionar ficheiros...
git add .

echo [2/3] A fazer commit...
for /f "tokens=2 delims==" %%a in ('wmic os get localdatetime /value') do set dt=%%a
set timestamp=%dt:~0,8%-%dt:~8,6%
git commit -m "Deploy v%timestamp%"

echo [3/3] A enviar para GitHub...
git push -u origin main

echo.
echo ==========================================
echo   Deploy enviado!
echo ==========================================
echo.
echo O Render vai detetar o push e fazer deploy automatico.
echo Verifique o status em: https://dashboard.render.com
echo.
pause
