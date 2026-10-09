@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Expert AI Manager - instalacao local.
set /p PROJECT=Diretorio do projeto (ja existente):
set /p NAME=Nome do projeto:
set /p PREFIX=Prefixo de tarefas (ex: CRM):
py -3 -B install.py --project "%PROJECT%" --name "%NAME%" --prefix "%PREFIX%"
if errorlevel 1 echo A instalacao falhou: verifique os dados e tente novamente.
echo.
pause
