@echo off
cd /d D:\gerador_orçamentos

echo ==========================================
echo RC Suporte - Gerador de Orcamentos
echo ==========================================
echo.

rem Definir PYTHONPATH para Windows
set PYTHONPATH=.

echo Iniciando servidor em http://localhost:8000
echo Pressione CTRL+C para encerrar
echo.

python main.py