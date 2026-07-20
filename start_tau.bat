@echo off
echo TAU baslatiliyor...
echo.

echo Gerekli paketler yukleniyor...
pip install -r requirements.txt

echo.
python main.py

pause
