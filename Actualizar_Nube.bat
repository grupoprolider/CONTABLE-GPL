@echo off
color 0A
echo ==================================================
echo   Sincronizando cambios con la Nube (Streamlit)
echo ==================================================
echo.
git add .
git commit -m "Actualizacion rapida de usuario"
git push
echo.
echo ==================================================
echo   ¡Listo! Los cambios ya estan viajando a la web.
echo   La pagina se actualizara sola en unos 30 segundos.
echo ==================================================
pause
