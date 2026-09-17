@echo off
echo Iniciando Generador de Asientos Contables...
cd /d "%~dp0"
python -m streamlit run app.py
pause
