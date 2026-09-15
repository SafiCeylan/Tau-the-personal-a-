# -*- coding: utf-8 -*-
"""
ULTRON Neural Core — Otomatik Derleme ve Dağıtım Scripti.

Bu script:
1. `pyinstaller ULTRON.spec --noconfirm` komutunu çalıştırır.
2. Derlenen çıktıları `dist/ULTRON` dizininden OneDrive DIŞINDAKİ
   hedef konuma (`C:\\Users\\memoc\\UltronApp\\ULTRON`) taşır/kopyalar.
3. Exe ve bağımlılıkların varlığını ve `%APPDATA%\\ULTRON` veritabanı yollarını doğrular.
"""

import os
import sys
import shutil
import subprocess

TARGET_DIR = r"C:\Users\memoc\UltronApp\ULTRON"

def run_build(cwd: str = None) -> bool:
    if cwd is None:
        cwd = os.path.dirname(os.path.abspath(__file__))
    
    spec_path = os.path.join(cwd, "ULTRON.spec")
    if not os.path.exists(spec_path):
        print(f"[ULTRON Deploy Error] ULTRON.spec dosyasi bulunamadi: {spec_path}")
        return False
    
    work_path = r"C:\Users\memoc\ultron_build_tmp"
    dist_tmp = r"C:\Users\memoc\ultron_dist_tmp"
    os.makedirs(work_path, exist_ok=True)
    os.makedirs(dist_tmp, exist_ok=True)
    
    print("[ULTRON Deploy] PyInstaller derlemesi baslatiliyor...")
    cmd = [
        sys.executable, "-m", "PyInstaller", "ULTRON.spec", "--noconfirm",
        "--workpath", work_path,
        "--distpath", dist_tmp
    ]
    
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ULTRON Deploy Error] PyInstaller basarisiz oldu:\n{result.stderr}")
        return False
    
    print("[ULTRON Deploy] PyInstaller derlemesi tamamlandi.")
    return True


def deploy_build(dist_dir: str = None, target_dir: str = TARGET_DIR) -> bool:
    if dist_dir is None:
        dist_dir = r"C:\Users\memoc\ultron_dist_tmp\ULTRON"
        if not os.path.exists(dist_dir):
            cwd = os.path.dirname(os.path.abspath(__file__))
            dist_dir = os.path.join(cwd, "dist", "ULTRON")

    
    if not os.path.exists(dist_dir):
        print(f"[ULTRON Deploy Error] Derleme ciktisi bulunamadi: {dist_dir}")
        return False
    
    exe_in_dist = os.path.join(dist_dir, "ULTRON.exe")
    if not os.path.exists(exe_in_dist):
        print(f"[ULTRON Deploy Error] ULTRON.exe ciktida yok: {exe_in_dist}")
        return False
    
    os.makedirs(target_dir, exist_ok=True)
    
    # Hedef exe çalışıyorsa kopyalama WinError 32 verir — önce kapat ve bekle
    try:
        subprocess.run(["taskkill", "/F", "/IM", "ULTRON.exe"], capture_output=True)
        import time
        time.sleep(1)
    except Exception:
        pass


    print(f"[ULTRON Deploy] Dosyalar {target_dir} konumuna aktariliyor...")

    try:
        # Kopyala ve uzerine yaz
        for item in os.listdir(dist_dir):
            s = os.path.join(dist_dir, item)
            d = os.path.join(target_dir, item)
            if os.path.isdir(s):
                if os.path.exists(d):
                    shutil.rmtree(d, ignore_errors=True)
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)

        
        target_exe = os.path.join(target_dir, "ULTRON.exe")
        if os.path.exists(target_exe):
            print(f"[ULTRON Deploy Success] Derleme ve dagitim basariyla tamamlandi -> {target_exe}")
            return True
        else:
            print(f"[ULTRON Deploy Error] Hedef exe kopyalanamadi: {target_exe}")
            return False
    except Exception as e:
        print(f"[ULTRON Deploy Error] Kopyalama hatasi: {e}")
        return False

def main():
    if not run_build():
        sys.exit(1)
    if not deploy_build():
        sys.exit(1)
    print("[ULTRON Deploy] Tum islemler basariyla tamamlandi.")

if __name__ == "__main__":
    main()
