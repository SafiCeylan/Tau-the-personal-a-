"""
Zamanlanmış Görevler — ULTRON'un otonom kalbi.

Her gün belirtilen saatte komut engine'den geçirilir, sonucu masaüstü sohbetine
VE (yapılandırılmışsa) Telegram'a gönderilir. Varsayılanlar: 08:00 sabah brifingi,
22:00 akşam raporu.

Sohbet komutları:
  zamanla: 08:30 sabah brifingi          → yeni görev
  her gün 22:00 akşam raporu             → yeni görev (doğal biçim)
  zamanlanmış görevler                   → listele
  zamanlama sil: 3                       → görevi sil
"""

import re
from datetime import datetime

VARSAYILAN_GOREVLER = [
    ("08:00", "sabah brifingi"),
    ("22:00", "akşam raporu"),
]


def varsayilanlari_kur(cursor, conn):
    """Tablo boşsa varsayılan görevleri ekler (ilk kurulum)."""
    cursor.execute("SELECT COUNT(*) FROM zamanli_gorevler")
    if cursor.fetchone()[0] == 0:
        for saat, komut in VARSAYILAN_GOREVLER:
            cursor.execute(
                "INSERT INTO zamanli_gorevler (saat, komut) VALUES (?, ?)", (saat, komut))
        conn.commit()
        return True
    return False


def gorev_ekle(cursor, conn, saat: str, komut: str):
    if not re.fullmatch(r'([01]?\d|2[0-3]):[0-5]\d', saat):
        return f"⚠️ Geçersiz saat biçimi: '{saat}'. Örnek: 08:30"
    saat = f"{int(saat.split(':')[0]):02d}:{saat.split(':')[1]}"
    cursor.execute("INSERT INTO zamanli_gorevler (saat, komut) VALUES (?, ?)", (saat, komut))
    conn.commit()
    return f"⏰ **Zamanlanmış görev eklendi:** her gün {saat} → \"{komut}\""


def gorev_sil(cursor, conn, gorev_id: int):
    cursor.execute("DELETE FROM zamanli_gorevler WHERE id = ?", (gorev_id,))
    conn.commit()
    if cursor.rowcount:
        return f"🗑️ #{gorev_id} numaralı zamanlanmış görev silindi."
    return f"⚠️ #{gorev_id} numaralı görev bulunamadı."


def gorevleri_listele(cursor):
    cursor.execute("SELECT id, saat, komut, son_calisma FROM zamanli_gorevler "
                   "WHERE aktif = 1 ORDER BY saat")
    rows = cursor.fetchall()
    if not rows:
        return ("⏰ Zamanlanmış görev yok.\n"
                "Eklemek için: `zamanla: 08:30 sabah brifingi`")
    lines = []
    for gid, saat, komut, son in rows:
        son_txt = f" (son: {son})" if son else ""
        lines.append(f"• **#{gid}** — her gün **{saat}** → \"{komut}\"{son_txt}")
    return ("⏰ **ZAMANLANMIŞ GÖREVLER:**\n\n" + "\n".join(lines) +
            "\n\nSilmek için: `zamanlama sil: <numara>`")


def zamani_gelenler(cursor, now: datetime = None):
    """Şu dakika çalışması gereken, bugün henüz çalışmamış görevler."""
    now = now or datetime.now()
    su_an = now.strftime('%H:%M')
    bugun = now.strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT id, saat, komut FROM zamanli_gorevler
        WHERE aktif = 1 AND saat = ? AND (son_calisma IS NULL OR son_calisma != ?)
    """, (su_an, bugun))
    return cursor.fetchall()


def calisti_isaretle(cursor, conn, gorev_id: int, now: datetime = None):
    bugun = (now or datetime.now()).strftime('%Y-%m-%d')
    cursor.execute("UPDATE zamanli_gorevler SET son_calisma = ? WHERE id = ?", (bugun, gorev_id))
    conn.commit()


def zamanlama_komutu_algila(mesaj: str, cursor, conn):
    """Sohbetten zamanlama yönetimi. Dönen: (işlendi_mi, yanıt)."""
    ml = mesaj.lower().strip()

    m = re.search(r'zamanla\s*:\s*(\d{1,2}[:.]\d{2})\s+(.+)$', mesaj, re.IGNORECASE)
    if not m:
        # doğal biçim: "her gün 08:00 de sabah brifingi" / "her sabah 8:30 brifing gönder"
        m = re.search(r"her\s+(?:gün|sabah|akşam)\s+(?:saat\s+)?(\d{1,2}[:.]\d{2})['’]?\s*(?:de|da|te|ta)?\s+(.+)$",
                      mesaj, re.IGNORECASE)
    if m:
        saat = m.group(1).replace('.', ':')
        komut = m.group(2).strip()
        # kuyruk fiillerini temizle: "... gönder/at/yap" zamanlama fiilidir, komuta dahil değil
        komut = re.sub(r'\s+(gönder|at|yolla|yap|çalıştır)$', '', komut, flags=re.IGNORECASE).strip()
        if komut:
            return True, gorev_ekle(cursor, conn, saat, komut)

    m = re.search(r'zamanlama\s+sil\s*:?\s*#?(\d+)', ml)
    if m:
        return True, gorev_sil(cursor, conn, int(m.group(1)))

    if any(k in ml for k in ['zamanlanmış görev', 'zamanlanmış rutinler', 'zamanlama listele',
                             'zamanlamaları göster', 'zamanlamalar']):
        return True, gorevleri_listele(cursor)

    if 'zamanla' in ml:
        return True, ("⚠️ Zamanlama komutunu çözemedim. Biçim:\n"
                      "• `zamanla: 08:30 sabah brifingi`\n"
                      "• `her gün 22:00 akşam raporu`\n"
                      "• `zamanlanmış görevler` / `zamanlama sil: 2`")

    return False, None
