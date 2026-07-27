"""
ULTRON CORE ENGINE v1.0 — 14 Modular Layers Implementation (Fixed Architecture)
Layer Order & Execution Pipeline Refactored for Zero-Hallucination & Interactive Security.
"""

import re
import sys
import os
from typing import Tuple, Dict, Any

from core.context import UltronContext
from core.tools import DEFTER
# Araçların deftere yazılması için import ŞART — modül yan etkisiyle kaydolurlar.
import core.builtin_tools  # noqa: F401
from features.actions.system_control import (
    sistem_komutu_algila, sistem_durumu_raporu, sarki_otomatik_baslat,
    medya_kontrol, medya_komutu_algila,
)
from features.web_search import canli_web_ara, web_arama_niyeti_algila
from features.file_reader import dosya_oku_ve_analiz_et, dosya_okuma_niyeti_algila
from features.reminders import hatirlatma_algila, hatirlatma_kaydet, gecmis_getir
from features.mood import ruh_hali_analiz, ruh_hali_kaydet
from features.qa import cevapla_guven_skoru_ile
from features.reporting import analiz_raporu_olustur
from features.actions.whatsapp_control import (
    whatsapp_komutu_algila, whatsapp_gonderim_ayristir, kisi_coz
)
from features.briefing import sabah_brifingi_olustur, aksam_raporu_olustur, hava_raporu, doviz_raporu
from features.email_control import email_komutu_algila, email_gonderim_ayristir, email_coz
from features.scheduler import zamanlama_komutu_algila
from features.auto_memory import hafiza_ogren
from features.file_finder import dosya_arama_niyeti, dosya_bul_ve_islet
from features.file_send import (
    dosya_niyeti_coz, dosya_komutu_isle, hedef_dosyayi_coz, indeks_komutu_algila,
    calistirilabilir_mi,
)
from features.clipboard_tools import pano_komutu
from features.quick_tools import (
    hesapla, hesap_niyeti_algila, saat_tarih_raporu, saat_tarih_niyeti_algila,
    sayac_niyeti_algila, sayac_kur, not_niyeti_algila, not_ekle,
    notlari_getir, notlari_sil,
)
from features.screenshot_tool import ekran_goruntusu_al


# =========================================================================
# LAYER 1: INPUT CAPTURE
# =========================================================================
class InputCaptureLayer:
    def process(self, raw_input: str, input_type: str = "text") -> UltronContext:
        return UltronContext(raw_input=raw_input, input_type=input_type)


# =========================================================================
# LAYER 2: INPUT NORMALIZATION (Typo & Slang Fixer)
# =========================================================================
class NormalizationLayer:
    def process(self, ctx: UltronContext) -> UltronContext:
        text = ctx.raw_input.strip()
        text_clean = re.sub(r'\s+', ' ', text)
        
        # Typo Normalizations
        typo_map = {
            r'\bchorome\b': 'chrome',
            r'\bcrom\b': 'chrome',
            r'\bspotifi\b': 'spotify',
            r'\byutube\b': 'youtube',
            r'\bhesp\b': 'hesap',
        }
        for pattern, replacement in typo_map.items():
            text_clean = re.sub(pattern, replacement, text_clean, flags=re.IGNORECASE)

        ctx.normalized_input = text_clean
        return ctx


# =========================================================================
# LAYER 3: INTENT ANALYZER
# =========================================================================
class IntentAnalyzerLayer:
    def __init__(self, config: dict = None):
        # config verilir ve llm_intent_enabled açıksa, regex GENERAL_CONVERSATION'a
        # düştüğünde yerel LLM'e danışılır (doğal dil komutlarını yakalamak için).
        self.config = config or {}

    def process(self, ctx: UltronContext) -> UltronContext:
        msg = ctx.normalized_input.lower()

        # 📇 Dosya indeksi yönetimi ("dosya indeksini güncelle")
        if re.search(r'\b(indeks|index)', msg) and 'dosya' in msg:
            ctx.intent = "FILE_INDEX"
            ctx.confidence = 0.95
            return ctx

        # 📎 Dosya bul & gönder — WhatsApp/e-posta niyetlerinden ÖNCE bakılır,
        # çünkü "staj raporunu anneme mail at" cümlesi ikisine birden benziyor.
        # Karar `dosya_niyeti_coz` içinde veriliyor: zayıf sinyalli cümlelerde
        # indekste eşleşme yoksa niyet ALINMAZ, mesaj akışı bozulmaz.
        dosya_plani = dosya_niyeti_coz(ctx.normalized_input, getattr(ctx, 'kanal', 'desktop'))
        if dosya_plani:
            ctx.intent = "FILE_TRANSFER"
            ctx.confidence = 0.92
            ctx.entities = ctx.entities or {}
            ctx.entities['dosya_plani'] = dosya_plani
            return ctx

        # WhatsApp mesaj/rehber komutları ("whatsapp aç" DEĞİL — o SYSTEM_CONTROL kalır)
        if ('whatsapp' in msg or re.search(r'\bwp\b', msg)) and \
                any(k in msg for k in ['mesaj', 'kişi', 'rehber', 'gönder', 'yolla', 'yaz']):
            ctx.intent = "WHATSAPP_MESSAGE"
            ctx.confidence = 0.95
        elif re.search(r'\b(mail|e-posta|eposta)\b', msg) and \
                any(k in msg for k in ['kişi', 'rehber', 'gönder', 'yolla', 'yaz', ' at']):
            ctx.intent = "EMAIL_MESSAGE"
            ctx.confidence = 0.95
        elif any(k in msg for k in ['günaydın', 'sabah brifingi', 'sabah raporu', 'sabah özeti', 'brifing']):
            ctx.intent = "MORNING_BRIEFING"
            ctx.confidence = 0.95
        elif any(k in msg for k in ['akşam raporu', 'gün raporu', 'günün özeti', 'gün özeti', 'akşam özeti']):
            ctx.intent = "EVENING_REPORT"
            ctx.confidence = 0.95
        elif 'zamanla' in msg or 'zamanlanmış' in msg or 'zamanlama' in msg or \
                re.search(r'\bher\s+(gün|sabah|akşam)\b.*\d{1,2}[:.]\d{2}', msg):
            # "her gün 21:00 dolar kaç" gibi doğal zamanlama da buraya girer
            ctx.intent = "SCHEDULE_TASK"
            ctx.confidence = 0.95
        elif not_niyeti_algila(msg):
            # "notları göster" — dosya aramadan ÖNCE ("göster" çakışıyor)
            ctx.intent = "NOTE_TAKE"
            ctx.confidence = 0.95
        elif sayac_niyeti_algila(msg):
            # "5 dakika sayaç kur" — hatırlatmadan ÖNCE (ikisi de zaman içerir)
            ctx.intent = "TIMER"
            ctx.confidence = 0.95
        elif saat_tarih_niyeti_algila(msg):
            ctx.intent = "TIME_DATE"
            ctx.confidence = 0.95
        elif hesap_niyeti_algila(msg):
            ctx.intent = "CALCULATOR"
            ctx.confidence = 0.95
        elif dosya_arama_niyeti(msg):
            # "indirilenlerdeki son pdf'i aç" — SYSTEM_CONTROL'dan ÖNCE ("aç" çakışır)
            ctx.intent = "FILE_SEARCH"
            ctx.confidence = 0.90
        elif 'ekran görüntüsü' in msg or 'ekranın fotoğrafı' in msg or 'screenshot' in msg:
            ctx.intent = "SCREENSHOT"
            ctx.confidence = 0.95
        elif re.search(r'\bpano', msg):
            ctx.intent = "CLIPBOARD"
            ctx.confidence = 0.95
        elif any(k in msg for k in ['odaklan', 'pomodoro', 'odak modu', 'odak mod']) or \
                ('odak' in msg and any(k in msg for k in ['durum', 'iptal', 'kaldı', 'süre', 'bitir'])):
            ctx.intent = "FOCUS_MODE"
            ctx.confidence = 0.95
        elif re.search(r'\bhava\b', msg) and \
                any(k in msg for k in ['durum', 'nasıl', 'kaç derece', 'yağmur', 'sıcak', 'soğuk', 'kar ']):
            # Hava soruları web aramasına değil doğrudan wttr.in'e gider
            ctx.intent = "WEATHER"
            ctx.confidence = 0.95
        elif any(k in msg for k in ['dolar kaç', 'euro kaç', 'dolar ne kadar', 'euro ne kadar', 'döviz kur']):
            ctx.intent = "CURRENCY"
            ctx.confidence = 0.95
        # Kelime sınırı ile eşle: "prenses", "seslendirme" gibi kelimeler tetiklemesin
        elif re.search(r'\b(ses|sesi|sesini|volume)\b', msg):
            ctx.intent = "SET_VOLUME"
            ctx.confidence = 0.95
        elif medya_komutu_algila(msg):
            # ZATEN çalan medyanın kontrolü (duraklat/devam/sonraki/önceki).
            # PLAY_MUSIC'ten ÖNCE olmalı — "şarkıyı geç" yeni oynatma değildir.
            ctx.intent = "MEDIA_CONTROL"
            ctx.confidence = 0.95
        elif any(k in msg for k in ["müzik çal", "şarkı çal", "müzik aç", "şarkı aç", "youtube music"]) or \
                (re.search(r'\bçal\b', msg) and any(k in msg for k in ["şarkı", "müzik", "youtube"])) or \
                msg.endswith(" çal"):
            # "X şarkısını youtube müzik ile çal", "X çal" gibi doğal kalıplar da müziktir
            ctx.intent = "PLAY_MUSIC"
            ctx.confidence = 0.95
        elif any(k in msg for k in ["hatırlat", "hatırlatıcı", "alarm"]):
            ctx.intent = "CREATE_REMINDER"
            ctx.confidence = 0.90
        elif any(k in msg for k in ["analiz raporu", "haftalık rapor", "aylık rapor", "kişisel analiz", "haftalık özet"]):
            ctx.intent = "ANALYSIS_REPORT"
            ctx.confidence = 0.90
        elif any(k in msg for k in ["ara:", "internet:", "google:", "haberler"]) or ("nedir" in msg or "kimdir" in msg):
            ctx.intent = "WEB_SEARCH"
            ctx.confidence = 0.90
        elif any(k in msg for k in ["oku:", "dosya oku:", "kod oku:", "pdf oku:"]):
            ctx.intent = "FILE_OPERATION"
            ctx.confidence = 0.90
        # Kelime sınırıyla eşle: "açıkla", "kapat halini anlat", "başlangıç" gibi
        # kelimeler SYSTEM_CONTROL'ü YANLIŞLIKLA tetiklemesin. Aksi halde bu komutlar
        # yanlış güvenlik skoru + yanlış onay kartı üretiyordu.
        elif any(k in msg for k in ["sistem", "donanım", "ram", "cpu"]) or \
                re.search(r'\b(kapat|başlat|çalıştır|aç)\b', msg):
            ctx.intent = "SYSTEM_CONTROL"
            ctx.confidence = 0.85
        else:
            ctx.intent = "GENERAL_CONVERSATION"
            ctx.confidence = 0.70

        # LLM DESTEĞİ: Regex net bir eyleme bağlayamadıysa (GENERAL_CONVERSATION),
        # yerel LLM'e sınıflandırma danış. Doğal dille yazılmış komutları
        # ("bana motivasyon şarkısı koy") yakalar. Ollama yoksa/yavaşsa sessizce
        # regex sonucunda kalır — akış asla bozulmaz.
        if ctx.intent == "GENERAL_CONVERSATION" and self.config.get('llm_intent_enabled'):
            try:
                from features.llm_intent import llm_intent_coz
                sonuc = llm_intent_coz(ctx.normalized_input, self.config)
                if sonuc:
                    llm_intent, llm_entities = sonuc
                    if llm_intent != "GENERAL_CONVERSATION":
                        ctx.intent = llm_intent
                        ctx.confidence = 0.80
                        ctx.intent_source = "llm"
                        ctx.llm_entities = llm_entities or {}
            except Exception as e:
                print(f"[Ultron Intent] LLM niyet çözümü atlandı: {e}")

        return ctx


# =========================================================================
# LAYER 4: ENTITY EXTRACTION
# =========================================================================
class EntityExtractionLayer:
    def process(self, ctx: UltronContext) -> UltronContext:
        msg = ctx.normalized_input
        # Niyet katmanının bıraktığı verilerle başla (ör. FILE_TRANSFER'in
        # 'dosya_plani'), üzerine LLM niyet çözücünün kanonik parametrelerini yaz;
        # aşağıdaki regex çıkarımları yalnızca boş alanları doldurur.
        entities = dict(ctx.entities or {})
        entities.update(ctx.llm_entities)

        # 1. Volume % Extractor
        pct_match = re.search(r'(?:%|yüzde)\s*(\d+)|(\d+)\s*(?:%|kadar)', msg, re.IGNORECASE)
        if pct_match:
            entities["volume_percent"] = int(pct_match.group(1) or pct_match.group(2))

        # 2. Target File Path Extractor
        file_match = re.search(r'(?:oku:|dosya oku:|kod oku:|pdf oku:)\s*(.+)', msg, re.IGNORECASE)
        if file_match:
            entities["file_path"] = file_match.group(1).strip()

        # 3. Search Query Extractor (LLM zaten temiz sorgu verdiyse dokunma)
        search_match = re.search(r'(?:ara:|internet:|google:|web:)\s*(.+)', msg, re.IGNORECASE)
        if search_match:
            entities["search_query"] = search_match.group(1).strip()
        elif not entities.get("search_query"):
            entities["search_query"] = msg

        # 4. Song Query Extractor (LLM zaten şarkı adı verdiyse onu koru)
        if ctx.intent == "PLAY_MUSIC" and not entities.get("song_title"):
            song_q = msg
            triggers = ["youtube music'ten", "youtube müzik'ten", "youtube music'den", "youtube müzik'den", "youtube music'te", "youtube müzik'te", "youtube music", "youtube müzik", "müzik çal", "şarkı çal", "müzik aç", "şarkı aç", "çal:"]
            for t in triggers:
                song_q = re.sub(t, "", song_q, flags=re.IGNORECASE)
            if song_q.lower().endswith("çal"):
                song_q = song_q[:-3]
            entities["song_title"] = song_q.strip().strip("'").strip()

        ctx.entities = entities
        return ctx


# =========================================================================
# LAYER 5: MEMORY CONTEXT
# =========================================================================
class MemoryContextLayer:
    def __init__(self, db_manager=None, config=None):
        self.db = db_manager
        self.config = config or {}

    def process(self, ctx: UltronContext) -> UltronContext:
        memories = []
        if self.db:
            try:
                # Tüm kayıtları çek, sonra MESAJA EN ALAKALI olanları seç (RAG).
                # Önceki hâl alakadan bağımsız "en son 10"u dökerek doğru bilgiyi
                # çoğu zaman prompt'un dışında bırakıyordu.
                tum = self.db.list_memory()
                from features.memory_rag import alakali_hafizalar
                memories = alakali_hafizalar(
                    ctx.normalized_input, tum, self.config, k=6)
            except Exception as e:
                print(f"[Ultron MemoryContext] Hafıza okunamadı: {e}")
                # Güvenli geri düşüş: eski davranış
                try:
                    memories = [f"{k}: {v}" for k, v, _c in self.db.list_memory()[:10]]
                except Exception:
                    memories = []
        ctx.user_memories = memories
        return ctx


# =========================================================================
# LAYER 6: SECURITY ANALYZER (5 Seviyeli Risk Skorlama Mimarisi 0 - 100+)
# =========================================================================
class SecurityAnalyzerLayer:
    def process(self, ctx: UltronContext) -> UltronContext:
        msg = ctx.normalized_input.lower()

        # Medya kontrolü zararsız ve anında geri alınabilir (tuş sinyali).
        # Onay sorulmadan geçer — aksi halde "spotify'da müziği durdur" gibi
        # komutlar aşağıdaki "durdur+spotify" kuralına takılıp onay kartı açıyordu.
        if ctx.intent == "MEDIA_CONTROL":
            ctx.security_score = 5
            ctx.security_level = "SAFE"
            ctx.security_message = "✅ **[GÜVENLİ]** Medya kontrolü uygulanıyor."
            return ctx

        # 1. Tier: 100+ (Kritik - Manuel Onay Şartı)
        if "evet bilgisayarı kapat" in msg:
            ctx.security_score = 90
            ctx.security_level = "CONFIRM"
            ctx.security_message = "🔴 **[KRİTİK ONAY ALINDI]:** Bilgisayarı kapatma işlemi yürütülecektir. İşlemi başlatmak için onay kartını onaylayın."
            return ctx

        if "bilgisayarı kapat" in msg or "sistemi kapat" in msg or "format at" in msg:
            ctx.security_score = 105
            ctx.security_level = "FORBIDDEN"
            ctx.security_message = "⛔ **[GÜVENLİK SKORU: 105/100 — MANUEL ONAY GEREKLİ]**\nBilgisayarı kapatma işlemi kritik risk taşımaktadır. Bilgisayarı kapatmak istediğinizden %100 eminseniz mesaj kutusuna tam olarak **'evet bilgisayarı kapat'** yazınız."
            return ctx

        # 1.4 📎 DOSYA GÖNDERİMİ.
        #     Kullanıcının KENDİ telefonuna (Telegram) göndermek onay istemez —
        #     dosya zaten sahibine gidiyor. BAŞKASINA gönderim (mail/WhatsApp)
        #     geri alınamaz bir dış eylemdir: her zaman onay kartı.
        if ctx.intent == "FILE_TRANSFER":
            plan = (ctx.entities or {}).get('dosya_plani') or {}
            if plan.get('islem') == 'gonder' and plan.get('hedef') in ('email', 'whatsapp'):
                yol = hedef_dosyayi_coz(plan, getattr(ctx, 'kanal', 'desktop'))
                if yol:
                    kanal_adi = 'E-posta' if plan['hedef'] == 'email' else 'WhatsApp'
                    boyut = os.path.getsize(yol) / (1024 * 1024)
                    ctx.entities['dosya_yolu'] = yol
                    ctx.security_score = 75
                    ctx.security_level = "CONFIRM"
                    ctx.security_message = (
                        f"📎 **[DOSYA GÖNDERİM ONAYI — SKOR 75/100]**\n"
                        f"• Dosya: **{os.path.basename(yol)}** ({boyut:.1f} MB)\n"
                        f"• 📁 {os.path.dirname(yol)}\n"
                        f"• Alıcı: **{plan.get('alici') or '?'}** ({kanal_adi})\n\n"
                        f"Onaylarsanız dosya **bilgisayarınızdan çıkıp alıcıya gönderilecektir.**"
                    )
                    return ctx
            # 1.45 📂 DOSYA AÇMA. Belge/resim/PDF sorusuz açılır. Ama .exe/.bat/
            #      .ps1 gibi dosyaları "açmak" aslında PROGRAM ÇALIŞTIRMAKTIR —
            #      indekste 134 bin dosya var, yanlış eşleşme program başlatır.
            if plan.get('islem') == 'ac':
                yol = hedef_dosyayi_coz(plan, getattr(ctx, 'kanal', 'desktop'))
                if yol and calistirilabilir_mi(yol):
                    ctx.entities['dosya_yolu'] = yol
                    ctx.security_score = 80
                    ctx.security_level = "CONFIRM"
                    ctx.security_message = (
                        f"⚠️ **[PROGRAM ÇALIŞTIRMA ONAYI — SKOR 80/100]**\n"
                        f"• Dosya: **{os.path.basename(yol)}**\n"
                        f"• 📁 {os.path.dirname(yol)}\n\n"
                        f"Bu bir **belge değil, program.** Açmak onu "
                        f"**çalıştıracaktır.** Onaylıyor musunuz?"
                    )
                    return ctx

            ctx.security_score = 10
            ctx.security_level = "SAFE"
            ctx.security_message = "✅ **[GÜVENLİ]** Dosya araması yürütülüyor."
            return ctx

        # 1.5 WhatsApp mesaj gönderimi: alıcı çözülüyorsa ONAY kartı göster.
        #     (Alıcı rehberde yoksa güvenli sayılır — execution katmanı rehbere
        #      ekleme talimatı döner, gönderim yapılmaz.)
        #     SADECE WHATSAPP_MESSAGE niyetinde ayrıştır — yoksa her mesajda gereksiz
        #     çalışıp "X'e yaz" gibi cümlelerde yanlış gönderim onayı üretebiliyordu.
        wa = whatsapp_gonderim_ayristir(ctx.normalized_input) \
            if ctx.intent == "WHATSAPP_MESSAGE" else None
        if wa:
            alici, metin = wa
            numara = kisi_coz(alici)
            if numara:
                ctx.security_score = 70
                ctx.security_level = "CONFIRM"
                ctx.security_message = (
                    f"📱 **[WHATSAPP GÖNDERİM ONAYI — SKOR 70/100]**\n"
                    f"• Alıcı: **{alici}** (`{numara}`)\n"
                    f"• Mesaj: \"{metin}\"\n\n"
                    f"Onaylarsanız mesaj **OTOMATİK olarak gönderilecektir.**"
                )
                return ctx

        # 1.6 E-posta gönderimi: alıcı çözülüyorsa ONAY kartı göster
        ep = email_gonderim_ayristir(ctx.normalized_input) \
            if ctx.intent == "EMAIL_MESSAGE" else None
        if ep:
            ep_alici, ep_konu, ep_icerik = ep
            ep_adres = email_coz(ep_alici)
            if ep_adres:
                ctx.security_score = 70
                ctx.security_level = "CONFIRM"
                ctx.security_message = (
                    f"📧 **[E-POSTA GÖNDERİM ONAYI — SKOR 70/100]**\n"
                    f"• Alıcı: **{ep_alici}** (`{ep_adres}`)\n"
                    f"• Konu: {ep_konu}\n"
                    f"• İçerik: \"{ep_icerik}\"\n\n"
                    f"Onaylarsanız e-posta **OTOMATİK olarak gönderilecektir.**"
                )
                return ctx

        # 2. Tier: 80-100 (Yüksek Risk - Çift Onay İste)
        if any(k in msg for k in ["tüm süreçleri kapat", "tüm uygulamaları kapat", "tümünü sonlandır", "sistem görevini kapat", "proses kill all"]):
            ctx.security_score = 85
            ctx.security_level = "DOUBLE_CONFIRM"
            ctx.security_message = "🔴 **[GÜVENLİK SKORU: 85/100 — ÇİFT ONAY GEREKLİ]**\nTüm sistem süreçlerini kapatma işlemi yüksek risk içerir. İşlemi yürütmek için ekranınızdaki onay butonuna basınız."
            return ctx

        # 3. Tier: 60-80 (Orta Risk - Tekli Onay İste)
        if any(k in msg for k in ["kapat", "sonlandır", "kill", "durdur"]) and any(k in msg for k in ["chrome", "spotify", "discord", "steam", "not defteri", "hesap makinesi"]):
            ctx.security_score = 75
            ctx.security_level = "CONFIRM"
            ctx.security_message = f"⚠️ **[GÜVENLİK SKORU: 75/100 — ONAY İSTE]**\n'{ctx.normalized_input}' komutu çalışan bir süreci kapatacaktır. Devam etmek için onay veriniz."
            return ctx

        # 4. Tier: 20-60 (Düşük Risk - Bilgilendir)
        if ctx.intent in ("OPEN_APPLICATION", "FILE_OPERATION"):
            ctx.security_score = 35
            ctx.security_level = "INFO"
            ctx.security_message = "ℹ️ **[GÜVENLİK SKORU: 35/100 — BİLGİLENDİRME]**\nUygulama açma / dosya okuma işlemi yürütülüyor."
            return ctx

        # 5. Tier: 0-20 (Güvenli - Direkt Çalıştır)
        ctx.security_score = 5
        ctx.security_level = "SAFE"
        ctx.security_message = "✅ **[GÜVENLİK SKORU: 5/100 — GÜVENLİ]**\nDoğrudan çalıştırma onaylandı."
        return ctx


# =========================================================================
# LAYER 7: TASK PLANNER
# =========================================================================
class TaskPlannerLayer:
    def process(self, ctx: UltronContext) -> UltronContext:
        if ctx.intent == "SYSTEM_CONTROL":
            ctx.subtasks = ["Parse OS Action", "Check Permissions", "Execute WinAPI", "Verify Process State"]
        elif ctx.intent == "WEB_SEARCH":
            ctx.subtasks = ["Fetch DuckDuckGo/Wiki API", "Clean Snippets", "Augment Prompt", "Generate LLM Answer"]
        elif ctx.intent == "PLAY_MUSIC":
            ctx.subtasks = ["Extract Song Title", "Fetch YouTube Video ID", "Open Music Player", "Trigger Unpause Hardware Key"]
        else:
            ctx.subtasks = ["Process Query via LLM"]
        return ctx


# =========================================================================
# LAYER 8: TOOL SELECTION ENGINE
# =========================================================================
class ToolSelectionEngineLayer:
    def process(self, ctx: UltronContext) -> UltronContext:
        tools = []
        if ctx.intent in ("SYSTEM_CONTROL", "SET_VOLUME"):
            tools.append("WindowsAPI")
        if ctx.intent == "PLAY_MUSIC":
            tools.extend(["YouTubeMusic", "WindowsMediaAPI"])
        if ctx.intent == "WEB_SEARCH":
            tools.extend(["DuckDuckGo", "WikipediaAPI"])
        if ctx.intent == "FILE_OPERATION":
            tools.append("FileSystemReader")
        if ctx.intent == "CREATE_REMINDER":
            tools.append("SQLiteMemory")

        ctx.selected_tools = tools or ["LLMCore"]
        return ctx


# =========================================================================
# LAYER 12: EXECUTION ENGINE (Gerçek Aksiyon Yürütücü - L9/L10 Öncesi)
# =========================================================================
class ExecutionEngineLayer:
    def process(self, ctx: UltronContext, db_cursor=None, db_conn=None) -> UltronContext:
        if ctx.security_level in ("CONFIRM", "DOUBLE_CONFIRM", "FORBIDDEN"):
            ctx.execution_success = False
            ctx.execution_result = ctx.security_message
            return ctx

        # 0. Ruh Hali Kaydı — SADECE gerçek sohbette. Komut metinleri ("... çal",
        #    "chrome aç") duygu geçmişini kirletmesin diye GENERAL_CONVERSATION dışı
        #    niyetlerde atlanır.
        if db_cursor and db_conn and ctx.intent == "GENERAL_CONVERSATION":
            try:
                ruh_hali, _skor = ruh_hali_analiz(ctx.normalized_input)
                if ruh_hali != 'belirsiz':
                    ruh_hali_kaydet(db_cursor, db_conn, ruh_hali, ctx.normalized_input)
            except Exception as e:
                print(f"[Ultron Mood] Ruh hali kaydedilemedi: {e}")

        # 0.1 🧠 Otomatik hafıza öğrenme ("en sevdiğim dizi X", "hatırla: k = v"...)
        if db_cursor and db_conn:
            try:
                ogrenilen = hafiza_ogren(ctx.normalized_input, db_cursor, db_conn)
                if ogrenilen:
                    ctx.execution_success = True
                    ctx.execution_result = ogrenilen
                    return ctx
            except Exception as e:
                print(f"[Ultron AutoMemory] {e}")

        # 0.2 → 6  ARAÇ DEFTERİ ÜZERİNDEN YÜRÜTME
        #
        # Eskiden burada ~260 satırlık bir if/elif zinciri vardı: her yetenek
        # regex'e gömülüydü, dışarıdan isimle çağrılamıyordu. Artık her yetenek
        # `core/builtin_tools.py` içinde isimli bir ARAÇ; bu katman yalnızca
        # intent'ten aracı bulup çalıştırır.
        #
        # Planner (Faz 1) aynı defteri kullanacak. Plan üretmenin bir anlamı
        # olması bu ayrıştırmaya bağlıydı: planner `{"action": "dosya_ara"}`
        # üretir, çözümü Executor yapar. Planner aracın NASIL çalıştığını bilmez.
        arac = DEFTER.intent_ile(ctx.intent)
        if arac is None:
            ctx.execution_success = False
            return ctx

        try:
            sonuc = arac.calistir(**self._argumanlari_hazirla(ctx, arac, db_cursor, db_conn))
        except Exception as e:
            # Araç çökerse akış LLM'e düşer — eski zincirde de tek bir yeteneğin
            # hatası tüm boru hattını durdurmuyordu.
            print(f"[Ultron Araç] {arac.ad} çalışırken hata: {e}")
            ctx.execution_success = False
            return ctx

        # Araç bağlama veri bıraktıysa (pano içeriği, ekran görüntüsü yolu, odak
        # modu ayarı) entities'e aktar — PromptGenerator ve UI bunları okur.
        if sonuc.veri:
            ctx.entities.update(sonuc.veri)

        if not sonuc.islendi:
            # DİKKAT: "üstlenmedi" ile "başarısız oldu" AYNI ŞEY DEĞİL.
            # Üstlenmediyse cevabı LLM üretir; başarısız olduysa aracın kendi
            # hata mesajı kullanıcıya döner (aşağıdaki dal).
            ctx.execution_success = False
            return ctx

        ctx.execution_success = sonuc.basarili
        ctx.execution_result = sonuc.mesaj
        return ctx

    @staticmethod
    def _argumanlari_hazirla(ctx: UltronContext, arac, db_cursor, db_conn) -> Dict[str, Any]:
        """Bağlamdaki veriyi aracın parametre adlarına köprüler."""
        argumanlar: Dict[str, Any] = {'metin': ctx.normalized_input}

        if arac.db_ister:
            argumanlar['db_cursor'] = db_cursor
            argumanlar['db_conn'] = db_conn

        # LLM niyet çözücünün kanonik parametreleri regex'in çıkardığına TERCİH
        # EDİLİR (llm_entities sonra yazılır, entities'i ezer).
        varliklar: Dict[str, Any] = dict(ctx.entities or {})
        varliklar.update(ctx.llm_entities or {})

        if arac.ad == 'uygulama_calistir':
            # Sadece LLM yönlendirdiyse kanonik komut kurulur; regex zaten ham
            # metinden okuyor. (Eski zincirin davranışı birebir korundu.)
            if ctx.intent_source == 'llm':
                if ctx.intent == 'PLAY_MUSIC' and varliklar.get('song_title'):
                    argumanlar['sarki'] = varliklar['song_title']
                elif ctx.intent == 'SYSTEM_CONTROL' and varliklar.get('app_name'):
                    argumanlar['uygulama'] = varliklar['app_name']
        elif arac.ad == 'dosya_gonder':
            # Kanal ayrımı: telefondaki "2'yi gönder", masaüstünde yapılmış
            # aramanın dosyasını göndermesin.
            argumanlar['kanal'] = getattr(ctx, 'kanal', 'desktop')
            argumanlar['plan'] = varliklar.get('dosya_plani')
        elif arac.ad == 'hesap_makinesi' and varliklar.get('expression'):
            argumanlar['ifade'] = varliklar['expression']
        elif arac.ad == 'sayac' and varliklar.get('timer_minutes'):
            argumanlar['dakika'] = varliklar['timer_minutes']
        elif arac.ad == 'not_yonet' and varliklar.get('note_text'):
            argumanlar['icerik'] = varliklar['note_text']
        elif arac.ad == 'dosya_oku' and varliklar.get('file_path'):
            argumanlar['yol'] = varliklar['file_path']
        elif arac.ad == 'web_ara' and varliklar.get('search_query'):
            argumanlar['sorgu'] = varliklar['search_query']
        elif arac.ad == 'medya_kontrol' and varliklar.get('media_action'):
            argumanlar['aksiyon'] = varliklar['media_action']

        return argumanlar


# =========================================================================
# LAYER 9: PROMPT GENERATOR (Canlı Veri & Sohbet Geçmişi Destekli)
# =========================================================================
class PromptGeneratorLayer:
    def process(self, ctx: UltronContext) -> UltronContext:
        mem_str = "\n".join([f"- {m}" for m in ctx.user_memories])
        
        chat_history_str = ""
        if ctx.recent_context:
            history_lines = []
            for turn in ctx.recent_context[-6:]:
                role = "Kullanıcı" if turn.get("role") == "user" else "Ultron"
                history_lines.append(f"{role}: {turn.get('text', '')}")
            chat_history_str = "\n[GEÇMİŞ SOHBET BAĞLAMI]:\n" + "\n".join(history_lines) + "\n"

        web_context_str = ""
        if ctx.execution_result and ctx.intent == "WEB_SEARCH":
            web_context_str = f"\n[CANLI İNTERNET VERİLERİ]:\n{ctx.execution_result}\nLütfen bu canlı verileri temel alarak Türkçe net ve detaylı yanıt ver.\n"

        # Pano görevi (özetle/çevir): içerik + görev LLM'e verilir
        if ctx.entities.get('pano_icerik'):
            web_context_str += (f"\n[PANO İÇERİĞİ]:\n{ctx.entities['pano_icerik'][:3000]}\n"
                                f"GÖREV: {ctx.entities.get('pano_gorev', '')}\n")

        ctx.enriched_prompt = (
            f"[ULTRON SİSTEM]\n"
            f"Sen ULTRON'sun: Türkçe konuşan kişisel bir masaüstü ve Telegram asistanı. "
            f"Kullanıcıya DAİMA BİRİNCİ TEKİL ŞAHISLA cevap ver (\"ben ... yapabilirim\"). "
            f"Kullanıcıya \"sen şunu yapabilirsin\" DEME — yetenekler SANA aittir, ona değil.\n"
            f"\n"
            f"GERÇEK YETENEKLERİN (bunları gerçekten yapabilirsin):\n"
            f"• Uygulama açma/kapatma, ses ve sistem kontrolü, ekran görüntüsü alma\n"
            f"• Hatırlatma kurma, sayaç kurma, sabah brifingi, hava durumu ve döviz kuru\n"
            f"• WhatsApp ve e-posta mesajı gönderme (kullanıcı onayıyla)\n"
            f"• İnternette arama, dosya bulma/okuma, müzik çalma, not/hafıza tutma\n"
            f"• Çalan müziği kontrol etme (duraklat, devam ettir, sonraki/önceki şarkı)\n"
            f"• Matematik işlemi hesaplama, saat ve tarih söyleme\n"
            f"\n"
            f"KURALLAR (kesinlikle uy):\n"
            f"1. KISA ve NET cevap ver — en fazla 4-5 cümle.\n"
            f"2. Bir eylemi bu yanıtın içinde SEN fiilen tetikleyemezsin; onu sistem "
            f"yürütür. Bu yüzden 'açtım / gönderdim / çaldım' gibi YAPMIŞ gibi ANLATMA. "
            f"Ama yeteneklerini SORANA yukarıdaki gerçek yeteneklerini anlat.\n"
            f"3. Emin olmadığın bilgiyi uydurma; bilmiyorsan bilmediğini söyle.\n"
            f"[KULLANICI HAFIZASI]\n{mem_str}\n"
            f"{chat_history_str}"
            f"{web_context_str}"
            f"Kullanıcı Komutu: {ctx.normalized_input}\n"
            f"Amaç: {ctx.intent}\n"
            f"ULTRON'un cevabı (birinci tekil şahıs, Türkçe):"
        )
        return ctx


# =========================================================================
# LAYER 10: LLM CORE
# =========================================================================
class LLMCoreLayer:
    """Gerçek LLM çağrısını yapar (allow_llm=True) veya çağıranın kendi LLM'ini
    çalıştırması için enriched_prompt'u bırakır (allow_llm=False — masaüstü streaming).

    Önceden bu katman HİÇ LLM çağırmıyordu; sadece prompt'u kopyalıyordu. Bu yüzden
    engine'i tek başına kullanan yerler (zamanlanmış görevler, Telegram) cevap
    alamıyordu. Artık config verilip allow_llm açılırsa engine tam cevabı üretir."""

    def __init__(self, config: dict = None):
        self.config = config or {}

    def process(self, ctx: UltronContext, allow_llm: bool = False) -> UltronContext:
        if ctx.security_level in ("CONFIRM", "DOUBLE_CONFIRM", "FORBIDDEN"):
            ctx.llm_response = ctx.security_message
            return ctx

        # Deterministik execution sonucu varsa (ve LLM istemeyen niyetse) onu kullan
        if ctx.execution_success and ctx.intent not in ("WEB_SEARCH", "GENERAL_CONVERSATION"):
            ctx.llm_response = ctx.execution_result
            return ctx

        # Buraya kadar geldiyse LLM cevabı gerekiyor (sohbet, web araması yorumu vb.)
        if allow_llm:
            provider = self.config.get('ai_provider', 'ollama')
            try:
                from features.llm_gateway import llm_uret
                ans, _ctx = llm_uret(provider, ctx.enriched_prompt, self.config)
                ctx.llm_response = ans or "Yanıt alınamadı."
                ctx.llm_generated = True
            except Exception as e:
                print(f"[Ultron LLMCore] LLM çağrısı başarısız: {e}")
                ctx.llm_response = f"⚠️ AI yanıtı üretilemedi: {e}"
        else:
            # Masaüstü UI streaming için ham prompt'u bırak (kendi worker'ıyla akıtır)
            ctx.llm_response = ctx.enriched_prompt
        return ctx


# =========================================================================
# LAYER 11: ACTION PLANNER
# =========================================================================
class ActionPlannerLayer:
    def process(self, ctx: UltronContext) -> UltronContext:
        ctx.action_plan = [
            {"step": i+1, "tool": tool, "status": "COMPLETED" if ctx.execution_success else "PENDING"}
            for i, tool in enumerate(ctx.selected_tools)
        ]
        return ctx


# =========================================================================
# LAYER 13: RESULT CHECKER
# =========================================================================
class ResultCheckerLayer:
    def process(self, ctx: UltronContext) -> UltronContext:
        if ctx.execution_success or (ctx.llm_response and len(ctx.llm_response) > 0):
            ctx.verification_passed = True
        else:
            ctx.verification_passed = False
            ctx.error_reason = "Aksiyon sonucu boş veya doğrulanamadı."
        return ctx


# =========================================================================
# LAYER 14: RESPONSE BUILDER
# =========================================================================
class ResponseBuilderLayer:
    def process(self, ctx: UltronContext) -> UltronContext:
        if ctx.execution_result and ctx.intent not in ("WEB_SEARCH", "GENERAL_CONVERSATION"):
            ctx.final_output = ctx.execution_result
        else:
            ctx.final_output = ctx.llm_response or "Ultron Nöral İşlemi Tamamlandı."

        ctx.ui_state = "speaking" if ctx.verification_passed else "idle"
        return ctx
