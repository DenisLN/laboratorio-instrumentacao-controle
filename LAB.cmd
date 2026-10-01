@echo off
rem Abre a sessao interativa de bancada (Experimento 7 por padrao).
rem   LAB.cmd            osciloscopio real pela USB
rem   LAB.cmd --sim      ensaio com o osciloscopio simulado
rem   LAB.cmd --exp 6    roteiro do Experimento 6
cd /d "%~dp0"
python -m labscope %*
pause
