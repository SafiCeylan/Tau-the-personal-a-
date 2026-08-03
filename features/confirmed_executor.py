# -*- coding: utf-8 -*-
"""
Onaylanan Komutların Yürütücüsü — tek doğru kapı.

Güvenlik katmanı bir komutu CONFIRM/DOUBLE_CONFIRM ile beklettiğinde, kullanıcı
onayladıktan sonra komut BURADAN yürütülür. Önceden hem masaüstü hem Telegram
onay yolu doğrudan `sistem_komutu_algila` çağırıyordu — ama WhatsApp ve e-posta
GÖNDERİMİ orada değil (whatsapp_control / email_control içinde). Sonuç: onaylı
WhatsApp/e-posta mesajları hiç gönderilmiyor, sistem yanlışlıkla "yürütüldü" diyordu.

Bu yürütücü komutu doğru modüle yönlendirir:
  • WhatsApp gönderimi  → whatsapp_control.whatsapp_mesaj_gonder
  • E-posta gönderimi   → email_control.email_gonder
  • Diğer her şey       → system_control.sistem_komutu_algila (kapatma, süreç sonlandırma…)
"""

from features.actions.system_control import sistem_komutu_algila


def onayli_komut_yurut(komut: str, kanal: str = 'desktop'):
    """
    Onaylanan komutu uygun executor'a yönlendirir.
    Dönüş: (is_action: bool, yanit: str) — sistem_komutu_algila ile aynı sözleşme.

    `kanal`: komut hangi kanaldan geldiyse ('desktop' veya Telegram chat_id).
    Dosya gönderiminde "2'yi gönder" seçimi kanal başına tutulduğu için gerekli.
    """
    # 0) Dosya gönderimi mi? ("staj raporunu anneme mail at", "2'yi patrona whatsapp'tan gönder")
    #    Mesaj gönderiminden ÖNCE bakılır: ikisi de "anneme mail at" kalıbına benziyor,
    #    ama dosya planı yalnızca indekste gerçek bir dosya eşleştiyse üretilir.
    try:
        from features.file_send import dosya_niyeti_coz, dosya_komutu_isle
        plan = dosya_niyeti_coz(komut, kanal)
        # 'ac' de buraya girer: çalıştırılabilir dosya onay kartından geçtiyse
        # `onaylandi=True` ile çağrılır, yoksa file_send tekrar onay ister ve
        # kullanıcı sonsuz döngüye girer.
        if plan and plan.get('islem') in ('gonder', 'ac'):
            handled, resp = dosya_komutu_isle(komut, kanal=kanal, plan=plan,
                                              onaylandi=True)
            if handled:
                return True, resp
    except Exception as e:
        print(f"[Onaylı Yürütücü] Dosya gönderimi yönlendirme hatası: {e}")

    # 1) WhatsApp mesaj gönderimi mi?
    try:
        from features.actions.whatsapp_control import whatsapp_gonderim_ayristir, whatsapp_mesaj_gonder
        wa = whatsapp_gonderim_ayristir(komut)
        if wa:
            alici, metin = wa
            return whatsapp_mesaj_gonder(alici, metin)
    except Exception as e:
        print(f"[Onaylı Yürütücü] WhatsApp yönlendirme hatası: {e}")

    # 2) E-posta gönderimi mi?
    try:
        from features.email_control import email_gonderim_ayristir, email_gonder
        ep = email_gonderim_ayristir(komut)
        if ep:
            alici, konu, icerik = ep
            return email_gonder(alici, konu, icerik)
    except Exception as e:
        print(f"[Onaylı Yürütücü] E-posta yönlendirme hatası: {e}")

    # 3) Uzaktan klavye tuşu mu? (Alt+F4, Delete, "kilit aç: 1234", "yaz: ...")
    #    Güvenlik katmanı riskli tuşlara onay kartı açıyor; onay sonrası komut
    #    BURAYA düşer. Kalıp kontrolü DAR tutulur — "anneme ... yaz" gibi mesaj
    #    cümleleri klavyeye gitmemeli, WhatsApp/e-posta dalları yukarıda.
    try:
        from core.interaction.level4_input import klavye_komutu_mu, send_keyboard_input
        if klavye_komutu_mu(komut):
            return send_keyboard_input(komut)
    except Exception as e:
        print(f"[Onaylı Yürütücü] Klavye yönlendirme hatası: {e}")

    # 4) Diğer sistem komutları (bilgisayarı kapat, süreç sonlandır…)
    return sistem_komutu_algila(komut)
