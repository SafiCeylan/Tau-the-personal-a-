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


def onayli_komut_yurut(komut: str):
    """
    Onaylanan komutu uygun executor'a yönlendirir.
    Dönüş: (is_action: bool, yanit: str) — sistem_komutu_algila ile aynı sözleşme.
    """
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

    # 3) Diğer sistem komutları (bilgisayarı kapat, süreç sonlandır…)
    return sistem_komutu_algila(komut)
