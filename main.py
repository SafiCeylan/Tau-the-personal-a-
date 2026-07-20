import sys

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt

from database.db_manager import DatabaseManager


def main():
    db_manager = DatabaseManager('bilgiler.db')
    conn = db_manager.get_connection()
    cursor = conn.cursor()

    # WebEngine için gerekli Qt ayarı
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)

    try:
        from ui.tau_window import TauMainWindow, load_config
    except ImportError as e:
        QMessageBox.critical(
            None, "TAU başlatılamadı",
            "Arayüz için PyQtWebEngine gerekli ama bulunamadı.\n\n"
            f"Detay: {e}\n\n"
            "Kurulum için KURULUM.md dosyasına bakın, örneğin:\n"
            "pip install PyQtWebEngine"
        )
        sys.exit(1)

    config = load_config()
    window = TauMainWindow(cursor, conn, db_manager, config)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
