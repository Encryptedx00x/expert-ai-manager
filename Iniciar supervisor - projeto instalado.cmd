@echo off
chcp 65001 >nul
echo Antes de iniciar: revise a janela calibrada, o planejamento e o status.
set /p PROJECT=Diretorio do projeto:
if not exist "%PROJECT%\scripts\expert_ai_rpa.py" (
  echo Expert AI Manager nao instalado nesse projeto.
  pause
  exit /b 1
)
cd /d "%PROJECT%"
py -3 -B scripts\expert_ai_rpa.py status
echo.
set /p ANSWER=Iniciar o supervisor desse projeto? (s/N):
if /i not "%ANSWER%"=="s" exit /b 0
py -3 -B -u scripts\expert_ai_rpa.py run
pause
