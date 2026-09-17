@echo off
echo Instalando los componentes necesarios para la App de Asientos Contables...
echo.
cd /d "%~dp0"
pip install -r requirements.txt
echo.
echo ========================================================
echo INSTALACION COMPLETADA. 
echo Ya puedes cerrar esta ventana y usar iniciar_app.bat
echo ========================================================
pause
