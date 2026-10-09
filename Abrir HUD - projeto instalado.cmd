@echo off
chcp 65001 >nul
echo Expert AI Manager - abra o HUD do projeto instalado.
echo.
set /p PROJECT=Digite o caminho do projeto:
if not exist "%PROJECT%\scripts\expert_ai_hud.py" (
  echo Expert AI Manager nao instalado nessa pasta.
  pause
  exit /b 1
)
cd /d "%PROJECT%"
start "" pyw -3 -B scripts\expert_ai_hud.py
echo HUD iniciado. Verifique a barra de tarefas.
timeout /t 2 >nul
