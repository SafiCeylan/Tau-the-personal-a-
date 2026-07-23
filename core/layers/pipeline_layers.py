"""
ULTRON CORE ENGINE v1.0 — 14 Modular Layers Implementation (Fixed Architecture)
Layer Order & Execution Pipeline Refactored for Zero-Hallucination & Interactive Security.
"""

import re
import sys
import os
from typing import Tuple, Dict, Any

from core.context import UltronContext
from features.actions.system_control import sistem_komutu_algila, sistem_durumu_raporu, sarki_otomatik_baslat
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
from features.clipboard_tools import pano_komutu
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
    def process(self, ctx: UltronContext) -> UltronContext:
        msg = ctx.normalized_input.lower()

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
        elif any(k in msg for k in ["sistem", "donanım", "ram", "cpu", "kapat", "başlat", "çalıştır", "aç"]):
            ctx.intent = "SYSTEM_CONTROL"
            ctx.confidence = 0.85
        else:
            ctx.intent = "GENERAL_CONVERSATION"
            ctx.confidence = 0.70

        return ctx


# =========================================================================
# LAYER 4: ENTITY EXTRACTION
# =========================================================================
class EntityExtractionLayer:
    def process(self, ctx: UltronContext) -> UltronContext:
        msg = ctx.normalized_input
        entities = {}

        # 1. Volume % Extractor
        pct_match = re.search(r'(?:%|yüzde)\s*(\d+)|(\d+)\s*(?:%|kadar)', msg, re.IGNORECASE)
        if pct_match:
            entities["volume_percent"] = int(pct_match.group(1) or pct_match.group(2))

        # 2. Target File Path Extractor
        file_match = re.search(r'(?:oku:|dosya oku:|kod oku:|pdf oku:)\s*(.+)', msg, re.IGNORECASE)
        if file_match:
            entities["file_path"] = file_match.group(1).strip()

        # 3. Search Query Extractor
        search_match = re.search(r'(?:ara:|internet:|google:|web:)\s*(.+)', msg, re.IGNORECASE)
        if search_match:
            entities["search_query"] = search_match.group(1).strip()
        else:
            entities["search_query"] = msg

        # 4. Song Query Extractor
        if ctx.intent == "PLAY_MUSIC":
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
    def __init__(self, db_manager=None):
        self.db = db_manager

    def process(self, ctx: UltronContext) -> UltronContext:
        memories = []
        if self.db:
            try:
                # Kullanıcının Veri Hafızası ekranından kaydettiği gerçek kayıtlar
                for key, value, _category in self.db.list_memory()[:10]:
                    memories.append(f"{key}: {value}")
            except Exception as e:
                print(f"[Ultron MemoryContext] Hafıza okunamadı: {e}")
        ctx.user_memories = memories
        return ctx


# =========================================================================
# LAYER 6: SECURITY ANALYZER (5 Seviyeli Risk Skorlama Mimarisi 0 - 100+)
# =========================================================================
class SecurityAnalyzerLayer:
    def process(self, ctx: UltronContext) -> UltronContext:
        msg = ctx.normalized_input.lower()

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

        # 1.5 WhatsApp mesaj gönderimi: alıcı çözülüyorsa ONAY kartı göster.
        #     (Alıcı rehberde yoksa güvenli sayılır — execution katmanı rehbere
        #      ekleme talimatı döner, gönderim yapılmaz.)
        wa = whatsapp_gonderim_ayristir(ctx.normalized_input)
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
        ep = email_gonderim_ayristir(ctx.normalized_input)
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

        # 0. Ruh Hali Kaydı (her mesajda pasif olarak çalışır, akışı etkilemez)
        if db_cursor and db_conn:
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

        # 0.2 ⏰ Zamanlama yönetimi
        if ctx.intent == "SCHEDULE_TASK" and db_cursor and db_conn:
            handled, resp = zamanlama_komutu_algila(ctx.normalized_input, db_cursor, db_conn)
            if handled:
                ctx.execution_success = True
                ctx.execution_result = resp
                return ctx

        # 0.3 🔍 Dosya bulucu
        if ctx.intent == "FILE_SEARCH":
            handled, resp = dosya_bul_ve_islet(ctx.normalized_input)
            if handled:
                ctx.execution_success = True
                ctx.execution_result = resp
                return ctx

        # 0.5 WhatsApp: rehber yönetimi + bilinmeyen alıcı rehberliği.
        #     (Çözülebilen gönderimler buraya ULAŞMAZ — güvenlik katmanı CONFIRM ile
        #      keser; onay sonrası sistem_komutu_algila üzerinden yürütülür.)
        if ctx.intent == "WHATSAPP_MESSAGE":
            handled, resp = whatsapp_komutu_algila(ctx.normalized_input)
            if handled:
                ctx.execution_success = True
                ctx.execution_result = resp
                return ctx

        # 0.6 E-posta: rehber yönetimi + bilinmeyen alıcı rehberliği
        #     (Çözülebilen gönderimler CONFIRM ile kesilir; onay sonrası
        #      sistem_komutu_algila üzerinden yürütülür.)
        if ctx.intent == "EMAIL_MESSAGE":
            handled, resp = email_komutu_algila(ctx.normalized_input)
            if handled:
                ctx.execution_success = True
                ctx.execution_result = resp
                return ctx

        # 0.7 Sabah Brifingi (hava + döviz + bugünkü hatırlatmalar)
        if ctx.intent == "MORNING_BRIEFING":
            ctx.execution_success = True
            ctx.execution_result = sabah_brifingi_olustur(db_cursor)
            return ctx

        # 0.35 📸 Ekran görüntüsü (Telegram'dan gelirse foto olarak da yollanır)
        if ctx.intent == "SCREENSHOT":
            yol, mesaj = ekran_goruntusu_al()
            ctx.execution_success = yol is not None
            ctx.execution_result = mesaj
            if yol:
                ctx.entities['screenshot_path'] = yol
            return ctx

        # 0.4 📋 Pano sihirbazı
        if ctx.intent == "CLIPBOARD":
            r = pano_komutu(ctx.normalized_input)
            if r:
                if r['tip'] == 'direct':
                    ctx.execution_success = True
                    ctx.execution_result = r['sonuc']
                    return ctx
                # 'ai' → içerik + görev LLM'e akar (PromptGenerator [PANO] bloğu ekler)
                ctx.entities['pano_icerik'] = r['icerik']
                ctx.entities['pano_gorev'] = r['gorev']

        # 0.5 🎯 Odak Modu (pomodoro) — asıl zamanlayıcı UI tarafında kurulur;
        #     burada sadece istek ayrıştırılıp entities'e yazılır
        if ctx.intent == "FOCUS_MODE":
            ml = ctx.normalized_input.lower()
            if any(k in ml for k in ['iptal', 'durdur', 'bitir', 'kapat']):
                ctx.entities['focus_action'] = 'cancel'
            elif any(k in ml for k in ['durum', 'kaldı', 'ne kadar']):
                ctx.entities['focus_action'] = 'status'
            else:
                m = re.search(r'(\d+)\s*(?:dakika|dk)', ml)
                ctx.entities['focus_action'] = 'start'
                ctx.entities['focus_minutes'] = int(m.group(1)) if m else 25
            ctx.execution_success = True
            ctx.execution_result = "🎯 Odak modu isteği alındı."  # UI tarafından ezilir
            return ctx

        # 0.75 🌙 Akşam Raporu (gün özeti + yarının hatırlatmaları)
        if ctx.intent == "EVENING_REPORT":
            ctx.execution_success = True
            ctx.execution_result = aksam_raporu_olustur(db_cursor)
            return ctx

        # 0.8 Hava Durumu — doğrudan wttr.in (arama motoru YOK, LLM YOK)
        if ctx.intent == "WEATHER":
            try:
                ctx.execution_success = True
                ctx.execution_result = hava_raporu()
                return ctx
            except Exception as e:
                print(f"[Ultron Weather] {e}")

        # 0.9 Döviz — doğrudan er-api
        if ctx.intent == "CURRENCY":
            ctx.execution_success = True
            ctx.execution_result = doviz_raporu()
            return ctx

        # 1. System Control & Volume & Music
        if ctx.intent in ("SYSTEM_CONTROL", "SET_VOLUME", "PLAY_MUSIC"):
            is_action, resp = sistem_komutu_algila(ctx.normalized_input)
            if is_action:
                ctx.execution_success = True
                ctx.execution_result = resp
                return ctx

        # 2. File Reader Operation
        if ctx.intent == "FILE_OPERATION":
            is_file, path = dosya_okuma_niyeti_algila(ctx.normalized_input)
            target = path or ctx.entities.get("file_path")
            if target:
                success, res = dosya_oku_ve_analiz_et(target)
                ctx.execution_success = success
                ctx.execution_result = res
                return ctx

        # 3. Web Search Operation
        if ctx.intent == "WEB_SEARCH":
            search_q = ctx.entities.get("search_query") or ctx.normalized_input
            success, res = canli_web_ara(search_q)
            if success:
                ctx.execution_success = True
                ctx.execution_result = res
                return ctx

        # 4. Reminders
        if ctx.intent == "CREATE_REMINDER":
            rem = hatirlatma_algila(ctx.normalized_input)
            if rem and rem.get('tip') == 'hatirlatma':
                if db_cursor and db_conn:
                    if hatirlatma_kaydet(db_cursor, db_conn, rem):
                        ctx.execution_success = True
                        ctx.execution_result = f"✅ Hatırlatma kaydedildi! '{rem['metin']}' konusunda {rem.get('detay', '')} hatırlatacağım."
                        return ctx
            elif rem and rem.get('tip') == 'gecmis_takip':
                if db_cursor:
                    rows = gecmis_getir(db_cursor)
                    if rows:
                        lines = [f"{i}. {metin} ({durum})" for i, (metin, _t, _o, durum) in enumerate(rows, 1)]
                        ctx.execution_success = True
                        ctx.execution_result = "📅 **KAYITLI HATIRLATMALARINIZ:**\n\n" + "\n".join(lines)
                        return ctx
                    else:
                        ctx.execution_success = True
                        ctx.execution_result = "📅 Henüz kayıtlı bir hatırlatmanız bulunmuyor."
                        return ctx

        # 5. Haftalık Kişisel Analiz Raporu
        if ctx.intent == "ANALYSIS_REPORT" and db_cursor:
            try:
                rapor = analiz_raporu_olustur(db_cursor)
                # HTML formatını sohbet balonunun markdown formatına çevir
                rapor = rapor.replace("<br>", "\n").replace("<b>", "**").replace("</b>", "**")
                ctx.execution_success = True
                ctx.execution_result = rapor
                return ctx
            except Exception as e:
                print(f"[Ultron Report] Analiz raporu hatası: {e}")

        # 6. Öğrenilmiş Soru-Cevap (fuzzy match) — yüksek güvende LLM'e gitmeden yanıtla
        if ctx.intent == "GENERAL_CONVERSATION" and db_cursor:
            try:
                cevap, skor = cevapla_guven_skoru_ile(db_cursor, ctx.normalized_input)
                if skor >= 85:
                    ctx.execution_success = True
                    ctx.execution_result = cevap
                    return ctx
            except Exception as e:
                print(f"[Ultron QA] Soru-cevap eşleşme hatası: {e}")

        ctx.execution_success = False
        return ctx


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
            f"[ULTRON SYSTEM CONTEXT]\n"
            f"Sen ULTRON adında Türkçe konuşan kişisel masaüstü asistanısın.\n"
            f"KURALLAR (kesinlikle uy):\n"
            f"1. KISA ve NET cevap ver — en fazla 4-5 cümle.\n"
            f"2. Bir eylemi (şarkı çalma, uygulama açma, mesaj gönderme vb.) sen "
            f"GERÇEKLEŞTİREMEZSİN; yapmış gibi ASLA anlatma. Böyle bir istek sana "
            f"düştüyse 'Bu komutu anlayamadım, şöyle deneyin: ...' de.\n"
            f"3. Emin olmadığın bilgiyi uydurma; bilmiyorsan bilmediğini söyle.\n"
            f"[KULLANICI HAFIZASI]\n{mem_str}\n"
            f"{chat_history_str}"
            f"{web_context_str}"
            f"Kullanıcı Komutu: {ctx.normalized_input}\n"
            f"Amaç: {ctx.intent}"
        )
        return ctx


# =========================================================================
# LAYER 10: LLM CORE
# =========================================================================
class LLMCoreLayer:
    def process(self, ctx: UltronContext) -> UltronContext:
        if ctx.security_level in ("CONFIRM", "DOUBLE_CONFIRM", "FORBIDDEN"):
            ctx.llm_response = ctx.security_message
            return ctx
            
        if ctx.execution_success and ctx.intent not in ("WEB_SEARCH", "GENERAL_CONVERSATION"):
            ctx.llm_response = ctx.execution_result
        else:
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
