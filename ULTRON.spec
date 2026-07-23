# -*- mode: python ; coding: utf-8 -*-
"""
ULTRON Neural Core — PyInstaller paketi (onedir).
Derleme:  pyinstaller ULTRON.spec --noconfirm
Çıktı:    dist/ULTRON/ULTRON.exe
"""

from PyInstaller.utils.hooks import collect_all

datas = [
    ('database/schema.sql', 'database'),
    ('config.example.json', '.'),
    ('models/vosk-tr', 'models/vosk-tr'),   # wake word Türkçe modeli (~85MB)
]
binaries = []
hiddenimports = [
    'PyQt5.QtNetwork',
    'pyttsx3.drivers', 'pyttsx3.drivers.sapi5',
    'comtypes.stream',
    'pycaw', 'pycaw.pycaw',
    'winotify',
    'pyperclip',
    'edge_tts',
    'speech_recognition',
    'pyaudio',
]

# Veri/DLL taşıyan paketleri komple topla
for pkg in ('vosk', 'sounddevice', 'pywinauto', 'comtypes', 'pygame', 'gtts'):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'notebook', 'IPython'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ULTRON',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # pencereli uygulama — konsol açılmaz
    icon='ultron.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='ULTRON',
)
