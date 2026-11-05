@echo off
rem Abre a sessao interativa de bancada (Experimento 8 por padrao).
rem   LAB.cmd            osciloscopio real pela USB
rem   LAB.cmd --sim      ensaio com o osciloscopio simulado
rem   LAB.cmd --exp 7    roteiro do Experimento 7 (ou 6, 9, 10)
cd /d "%~dp0"
python -m labscope %*
pause
