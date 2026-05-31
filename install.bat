@echo off
chcp 65001 >nul
echo ==========================================
echo   CRC Analyzer - Instalador Automatico
echo ==========================================
echo.

REM Verificar se Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao esta instalado ou nao esta no PATH.
    echo Por favor, instale Python 3.8+ em https://python.org
    pause
    exit /b 1
)

echo [OK] Python encontrado.
python --version
echo.

REM Criar ambiente virtual
echo [1/4] A criar ambiente virtual...
python -m venv venv
if errorlevel 1 (
    echo [ERRO] Falha ao criar ambiente virtual.
    pause
    exit /b 1
)
echo [OK] Ambiente virtual criado.
echo.

REM Ativar ambiente virtual
echo [2/4] A ativar ambiente virtual...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERRO] Falha ao ativar ambiente virtual.
    pause
    exit /b 1
)
echo [OK] Ambiente virtual ativado.
echo.

REM Instalar dependencias Python
echo [3/4] A instalar dependencias Python (pode demorar alguns minutos)...
pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.
echo.

REM Verificar Tesseract
echo [4/4] A verificar Tesseract OCR...
tesseract --version >nul 2>&1
if errorlevel 1 (
    echo [AVISO] Tesseract OCR nao encontrado.
    echo Para extracao de PDFs digitalizados, instale em:
    echo https://github.com/UB-Mannheim/tesseract/wiki
    echo.
    echo A aplicacao funciona mesmo sem Tesseract usando dados de demonstracao.
) else (
    echo [OK] Tesseract OCR encontrado.
)
echo.

echo ==========================================
echo   Instalacao concluida com sucesso!
echo ==========================================
echo.
echo Para iniciar a aplicacao:
echo   1. Execute: start_app.bat
echo   2. Abra o navegador em http://localhost:5000
echo.
pause
