import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtNetwork import QLocalSocket, QLocalServer

from database.db_manager import DatabaseManager
from core.paths import veri_yolu

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
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    # Tray modu: pencere kapansa da uygulama arka planda yaşamaya devam eder
    app.setQuitOnLastWindowClosed(False)

    # Windows açılışında otomatik başlatma: pencere açılmasın, doğrudan tray'e insin.
    # (Başlangıç klasöründeki kısayol "--tray" argümanıyla çalıştırır.)
    sessiz_baslat = "--tray" in sys.argv

    # Önce tek-kopya kilidini kontrol et: ikinci kopya ise DB'yi hiç açmadan çık
    # (gereksiz bağlantı açıp kapatmayı ve olası dosya kilidi çakışmasını önler).
    if _zaten_calisiyor_mu():
        print("ULTRON zaten çalışıyor — mevcut pencere öne getirildi. Bu kopya kapanıyor.")
        sys.exit(0)

    # DB %APPDATA%\ULTRON altında — exe ile python sürümü aynı hafızayı paylaşır
    db_manager = DatabaseManager(veri_yolu('bilgiler.db'))
    conn = db_manager.get_connection()
    cursor = conn.cursor()

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

    if sessiz_baslat and getattr(window, 'tray', None):
        # Tray ikonu pencereden bağımsız kurulur — pencereyi hiç göstermeden
        # arka planda yaşamaya devam eder. (Tray yoksa normal açılışa düş.)
        print("ULTRON tray modunda başlatıldı (--tray).")
    else:
        window.show()
        window.raise_()
        window.activateWindow()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
