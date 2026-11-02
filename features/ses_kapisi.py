# -*- coding: utf-8 -*-
"""
🎙️ SES KAPISI — mikrofondan gelen her cümle bir komut DEĞİLDİR.

NEDEN VAR (15 Eki 2026, canlı kayıt `ogrenme.db`): 24 Eyl – 3 Eki arasında
masaüstü mikrofonundan TV/dizi konuşmaları geldi ("amirim", "savcım",
"tekrar cezaevine dönmek istiyorum…") ve Ultron bunları komut sanıp işledi:
planner 18 plan üretti, SCREEN_CLICK / FINANCE_TRACK / SET_VOLUME /
CREATE_REMINDER niyetleri tetiklendi. Metinler küçük harfe çevrilmiş geldiği
için yol STT'dir (ListenWorkerThread); dinlemeyi neyin açtığı kesinleşmedi —
bu kapı KAYNAKTAN BAĞIMSIZ savunmadır.

ÖLÇÜM (aynı arşiv): yazılı gerçek komutların en uzunu 13 kelime (348 tur);
ortam konuşmasının 48 turundan 38'i 15 kelimeden uzun. Eşik 15 → ölçülen
gerçek komutlarda yanlış pozitif 0. Kısa ortam cümleleri ("bakın kasap",
"tabii") çoğunlukla sohbete düşüyor; zararları LLM'in boş bir cevabıdır.

KURAL: sesle gelen, Ultron'a doğrudan hitap etmeyen ve eşikten uzun cümle
ORTAM KONUŞMASIDIR → hiçbir araç, plan ya da rutin çalıştırmaz. Canlı sesli
sohbet açıksa (kullanıcı konuşmayı kendisi başlattı) cevabı sohbet olarak
alır; kapalıysa hiç işlenmez.
"""

import re

ORTAM_KELIME_ESIGI = 15

# Cümle Ultron'a hitapla başlıyorsa uzun da olsa kullanıcının komutudur.
_HITAP = re.compile(r'^\s*(hey\s+)?(ultron|ultra)\b', re.IGNORECASE)


def kelime_sayisi(metin: str) -> int:
    return len((metin or '').split())


def ortam_konusmasi_mi(metin: str) -> bool:
    """Sesle gelen bu cümle büyük olasılıkla ortamdan mı duyuldu?"""
    if not metin or _HITAP.match(metin):
        return False
    return kelime_sayisi(metin) > ORTAM_KELIME_ESIGI


def bildirim(metin: str) -> str:
    return (f"🎙️ _Uzun bir konuşma duydum ({kelime_sayisi(metin)} kelime) — bana "
            f"söylenmiş bir komut gibi görünmüyor, işlemedim. Komutsa "
            f"\"Ultron\" diye başlayarak tekrar söyle._")
