@echo off
chcp 65001 >nul
echo ==========================================
echo   CRC Analyzer - Iniciar Aplicacao
echo ==========================================
echo.

call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERRO] Ambiente virtual nao encontrado.
    echo Execute primeiro: install.bat
    pause
    exit /b 1
)

echo Ambiente virtual ativado.
echo A iniciar servidor Flask...
echo.
echo ==========================================
echo   A aplicacao estara disponivel em:
echo   http://localhost:5000
echo ==========================================
echo.
echo Pressione CTRL+C para parar o servidor.
echo.

python app.py

pause
