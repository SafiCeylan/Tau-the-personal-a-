"""
Özel Kullanıcı Kısayolları Modül Testleri.
"""

import os
import unittest
from unittest.mock import patch
import features.custom_shortcuts as cs


class TestCustomShortcuts(unittest.TestCase):

    def setUp(self):
        self.test_file = "test_custom_shortcuts.json"
        self.patcher = patch.object(cs, "_dosya_yolu", return_value=self.test_file)
        self.patcher.start()
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def tearDown(self):
        self.patcher.stop()
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_ekle_ve_yukle(self):
        ok, msg = cs.ekle("Photoshop", "ctrl+alt+shift+p")
        self.assertTrue(ok)
        self.assertIn("Photoshop", msg)

        shortcuts = cs.yukle()
        self.assertIn("Photoshop", shortcuts)
        self.assertEqual(shortcuts["Photoshop"], "ctrl+alt+shift+p")

    def test_komut_bul(self):
        cs.ekle("Terminal", "ctrl+alt+t")
        res = cs.komut_bul("Terminal")
        self.assertEqual(res, "ctrl+alt+t")

        res_lower = cs.komut_bul("terminal")
        self.assertEqual(res_lower, "ctrl+alt+t")

    def test_buton_metnindeki_emoji_yok_sayilir(self):
        """Menü butonu '⭐ Photoshop' gönderir, kayıt 'Photoshop' adında."""
        cs.ekle("Photoshop", "ctrl+alt+shift+p")
        self.assertEqual(cs.komut_bul("⭐ Photoshop"), "ctrl+alt+shift+p")

    def test_kismi_metin_kisayol_tetiklemez(self):
        """
        REGRESYON: eşleşme alt diziyle yapılıyordu — "aç" mesajı
        "⚡ VS Code Aç" kısayolunu, tek harflik mesaj bile rastgele bir
        kısayolu çalıştırıyordu. Sohbet cümleleri komuta dönüşmemeli.
        """
        cs.ekle("⚡ VS Code Aç", "code")
        for mesaj in ("aç", "a", "code", "vs", "teşekkürler"):
            self.assertIsNone(cs.komut_bul(mesaj),
                              f"'{mesaj}' yanlışlıkla kısayol tetikledi")

    def test_sil(self):
        cs.ekle("MyTestShortcut", "code")
        ok, msg = cs.sil("MyTestShortcut")
        self.assertTrue(ok)

        shortcuts = cs.yukle()
        self.assertNotIn("MyTestShortcut", shortcuts)

    def test_kismi_isimle_silinmez(self):
        """'a' yazınca içinde 'a' geçen ilk kısayol silinmemeli."""
        cs.ekle("Photoshop", "ctrl+alt+shift+p")
        ok, msg = cs.sil("a")
        self.assertFalse(ok)
        self.assertIn("Photoshop", cs.yukle())


if __name__ == "__main__":
    unittest.main()
