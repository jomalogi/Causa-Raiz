@echo off
title Desplegar Bot Calidad en Servidor 10.108.34.74
cd /d "%~dp0bot_calidad"
echo ========================================================
echo DESPLIEGUE EN SERVIDOR REMOTO: 10.108.34.74:822
echo ========================================================
echo.
python desplegar_remoto.py
pause
