import os
import sys

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtNetwork import QLocalSocket, QLocalServer

from database.db_manager import DatabaseManager

# Uygulama hangi klasörden başlatılırsa başlatılsın DB her zaman proje kökünde kalsın
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Tek kopya kilidi: ikinci Ultron açılırsa yenisi kapanır, mevcut pencere öne gelir.
# (İki kopya aynı anda Telegram botunu dinleyince "Conflict" hatası oluşuyordu.)
INSTANCE_KEY = "ULTRON_NEURAL_CORE_SINGLE_INSTANCE"


def _zaten_calisiyor_mu() -> bool:
    sock = QLocalSocket()
    sock.connectToServer(INSTANCE_KEY)
    if sock.waitForConnected(300):
        sock.write(b"SHOW")
        sock.flush()
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return True
    return False


def main():
    db_manager = DatabaseManager(os.path.join(BASE_DIR, 'bilgiler.db'))
    conn = db_manager.get_connection()
    cursor = conn.cursor()

    app = QApplication(sys.argv)
    # Tray modu: pencere kapansa da uygulama arka planda yaşamaya devam eder
    app.setQuitOnLastWindowClosed(False)

    if _zaten_calisiyor_mu():
        print("ULTRON zaten çalışıyor — mevcut pencere öne getirildi. Bu kopya kapanıyor.")
        sys.exit(0)

    try:
        from ui.tau_window import TauMainWindow, load_config
    except ImportError as e:
        QMessageBox.critical(
            None, "TAU başlatılamadı",
            "Arayüz modülleri yüklenemedi. Eksik bağımlılık olabilir.\n\n"
            f"Detay: {e}\n\n"
            "Kurulum için KURULUM.md dosyasına bakın veya şunu çalıştırın:\n"
            "pip install -r requirements.txt"
        )
        sys.exit(1)

    config = load_config()
    window = TauMainWindow(cursor, conn, db_manager, config)

    # Tek kopya sunucusu: ikinci kopya "SHOW" gönderirse pencereyi öne getir
    QLocalServer.removeServer(INSTANCE_KEY)  # önceki çökmeden kalan kilidi temizle
    instance_server = QLocalServer()
    instance_server.listen(INSTANCE_KEY)
    instance_server.newConnection.connect(window._restore_from_tray)
    window._instance_server = instance_server  # referans yaşasın

    window.show()
    window.raise_()
    window.activateWindow()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
