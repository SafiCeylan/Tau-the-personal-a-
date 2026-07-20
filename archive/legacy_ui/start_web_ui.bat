@echo off
echo TAU Web UI Baslatiliyor...
echo.

REM Gerekli paketleri yukle
echo Gerekli paketler yukleniyor...
pip install -r requirements_web.txt

echo.
echo TAU Web UI baslatiliyor...
python main_web.py

pause
