@echo off
title Cargue Diario de Visitas de Calidad
cd /d "%~dp0"
echo ========================================================
echo CARGUE DIARIO DE VISITAS DE CALIDAD (Visitas_Calidad.xlsx)
echo ========================================================
echo.
python cargar_base.py Visitas_Calidad.xlsx
echo.
echo Proceso finalizado.
pause
