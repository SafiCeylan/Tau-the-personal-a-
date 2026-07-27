"""
ULTRON CORE ENGINE v1.0 — Central Pipeline Orchestration Engine
Executes all 14 layers in strict architecture order with zero hallucination & interactive security.
"""

from core.context import UltronContext
from core.layers.pipeline_layers import (
    InputCaptureLayer, NormalizationLayer, IntentAnalyzerLayer,
    EntityExtractionLayer, MemoryContextLayer, SecurityAnalyzerLayer,
    TaskPlannerLayer, ToolSelectionEngineLayer, PromptGeneratorLayer,
    LLMCoreLayer, ActionPlannerLayer, ExecutionEngineLayer,
    ResultCheckerLayer, ResponseBuilderLayer
)
from core.layers.routine_engine import RoutineEngine
from core.layers.self_reflection import SelfReflectionEngine
from core.context_manager import BAGLAM
from core.plan_executor import PlanYurutucu
from core.planner import BEKLIYOR, ONAY_BEKLIYOR, cok_adimli_olabilir, plan_uret


# Onay bekleyen planlar kanal başına tutulur. Telefondan başlatılan bir planın
# onayı masaüstünde verilmemeli (dosya arama sonuçlarındaki kanal ayrımıyla
# aynı gerekçe).
_ONAY_KELIMELERI = ("evet", "onaylıyorum", "onayla", "tamam", "olur", "yap", "devam")
_RET_KELIMELERI = ("hayır", "hayir", "iptal", "vazgeç", "vazgec", "dur", "yapma")


class UltronCoreEngine:
    def __init__(self, db_manager=None, cursor=None, conn=None, config=None):
        self.db = db_manager
        self.cursor = cursor
        self.conn = conn
        self.config = config or {}
        # {kanal: (Plan, onaylanan_gorev_idleri)}
        self.bekleyen_planlar = {}

        # Initialize 14 layers
        self.l1_capture = InputCaptureLayer()
        self.l2_norm = NormalizationLayer()
        self.l3_intent = IntentAnalyzerLayer(self.config)
        self.l4_entity = EntityExtractionLayer()
        self.l5_memory = MemoryContextLayer(db_manager, self.config)
        self.l6_security = SecurityAnalyzerLayer()
        self.l7_planner = TaskPlannerLayer()
        self.l8_tools = ToolSelectionEngineLayer()
        self.l9_prompt = PromptGeneratorLayer()
        self.l10_llm = LLMCoreLayer(self.config)
        self.l11_action = ActionPlannerLayer()
        self.l12_exec = ExecutionEngineLayer()
        self.l13_checker = ResultCheckerLayer()
        self.l14_response = ResponseBuilderLayer()

        # Autonomous Engines
        self.routine_engine = RoutineEngine(db_manager)
        self.self_reflection = SelfReflectionEngine()

    def update_config(self, config: dict):
        """Ayarlar kaydedilince yeni config'i canlı uygular (yeniden başlatma gerekmez)."""
        self.config = config or {}
        self.l3_intent.config = self.config
        self.l5_memory.config = self.config
        self.l10_llm.config = self.config

    def process(self, raw_input: str, input_type: str = "text", recent_context: list = None,
                allow_llm: bool = False, kanal: str = "desktop") -> UltronContext:
        """
        Executes the 14-layer pipeline sequentially for every user prompt.

        allow_llm: True ise LLM cevabı da engine İÇİNDE üretilir (final_output hazır
        gelir) — zamanlanmış görevler ve Telegram bunu kullanır. False ise (masaüstü)
        enriched_prompt bırakılır; UI streaming worker'ıyla cevabı kendisi akıtır.

        kanal: komutun geldiği yer ("desktop" veya Telegram chat_id). Dosya arama
        sonuçları kanal başına tutulur — telefondaki "2'yi gönder" masaüstünde
        yapılmış aramanın dosyasını göndermesin.

        SQLite bağlantıları thread'ler arasında paylaşılamadığı için her çağrıda
        (worker thread'de çalışsa bile güvenli olacak şekilde) kendi bağlantısını açar.
        """
        own_conn = None
        cursor, conn = self.cursor, self.conn
        if self.db is not None:
            try:
                own_conn = self.db.get_connection()
                conn = own_conn
                cursor = conn.cursor()
            except Exception as e:
                print(f"[Ultron Engine] DB bağlantısı açılamadı, mevcut bağlantı kullanılacak: {e}")
                own_conn = None

        try:
            return self._run_pipeline(raw_input, input_type, recent_context, cursor, conn,
                                      allow_llm, kanal)
        finally:
            if own_conn is not None:
                try:
                    own_conn.close()
                except Exception:
                    pass

    def _run_pipeline(self, raw_input, input_type, recent_context, cursor, conn,
                      allow_llm=False, kanal="desktop") -> UltronContext:
        # 1. Input Capture
        ctx = self.l1_capture.process(raw_input, input_type)
        ctx.kanal = kanal or "desktop"
        if recent_context:
            ctx.recent_context = recent_context

        # 2. Input Normalization (Fixes typos: chorome -> chrome)
        ctx = self.l2_norm.process(ctx)

        # 2.4 CONTEXT MANAGER (Faz 2) — eksik referansları doldur.
        #     Niyet analizinden ÖNCE olmalı: "onu anneme gönder" cümlesinde
        #     dosya adı yoksa FILE_TRANSFER regex'i eşleşmez ve komut sohbete düşer.
        ctx = self._baglami_uygula(ctx)

        # 2.5 Onay bekleyen bir plan varsa, bu mesaj onay/ret cevabı olabilir.
        #     Niyet analizinden ÖNCE bakılır: "evet" tek başına anlamsız bir
        #     cümledir, boru hattı onu sohbete yollar ve plan sonsuza kadar asılı kalır.
        if ctx.kanal in self.bekleyen_planlar:
            cevaplandi, ctx = self._bekleyen_plani_isle(ctx, cursor, conn)
            if cevaplandi:
                return self.l14_response.process(ctx)

        # 3. Intent Analyzer
        ctx = self.l3_intent.process(ctx)

        # 4. Entity Extraction
        ctx = self.l4_entity.process(ctx)

        # 5. Memory Context
        ctx = self.l5_memory.process(ctx)

        # 6. Security Analyzer (0-100+ Risk Rating)
        ctx = self.l6_security.process(ctx)

        # SECURITY INTERCEPT: If confirmation is needed or forbidden, STOP IMMEDIATELY!
        if ctx.security_level in ("CONFIRM", "DOUBLE_CONFIRM", "FORBIDDEN"):
            ctx.execution_success = False
            ctx.execution_result = ctx.security_message
            return self.l14_response.process(ctx)

        # Routine Engine Check (Autonomous Workflows)
        is_routine, routine_output = self.routine_engine.check_and_execute_routine(ctx)
        if is_routine:
            ctx.execution_success = True
            ctx.execution_result = routine_output
            ctx.verification_passed = True
            return self.l14_response.process(ctx)

        # 7. Task Planner
        ctx = self.l7_planner.process(ctx)

        # 8. Tool Selection Engine
        ctx = self.l8_tools.process(ctx)

        # 12. PLANNER (Faz 1) → yoksa Execution Engine
        #
        # ⚠️ SIRA NEDEN BÖYLE: planner'ı yürütmeden SONRA çalıştırmak işe yaramaz.
        # Canlı testte "önce hava durumuna bak, sonra dövizi söyle, en son not al"
        # cümlesini regex `NOTE_TAKE` sandı, içeriği "al" olan saçma bir not
        # kaydetti ve "başarılı" olduğu için planner kapısı hiç açılmadı.
        # Çok adımlı bir cümlede tek bir intent'in kazanması ZATEN hatadır.
        #
        # "Deterministik önce" kuralı bozulmuyor: kapı yalnızca cümlede açık
        # sıralama/koşul ifadesi varsa açılır ("sonra", "bulamazsan"...).
        # "chrome aç" gibi tek komutlar bu kapıdan geçmez, planner'ı görmez.
        planlandi = False
        if self.config.get('planner_enabled', True) and cok_adimli_olabilir(ctx.normalized_input):
            ctx, planlandi = self._plani_kur_ve_calistir(ctx, cursor, conn)

        if not planlandi:
            ctx = self.l12_exec.process(ctx, db_cursor=cursor, db_conn=conn)
            # 12.6 RECOVERY (Faz 4) — hedefe ulaşılamadıysa alternatif üret.
            #
            # İki tetikleyici var, ikisi de gerekli:
            #   • hata_tipi işaretli → araç düzgün çalıştı ama aradığını bulamadı
            #     ("dosya bulunamadı" başarılı bir çıktıdır, hedefe ulaşmaz)
            #   • basarili=False + mesaj var → araç denedi ve hata verdi
            #
            # "Üstlenmedi" (execution_result boş) durumunda kurtarma YAPILMAZ:
            # orada bir hata yok, komut zaten sohbete ait.
            if ctx.son_arac and ctx.execution_result and (
                getattr(ctx.son_arac_sonucu, 'hata_tipi', None)
                or not ctx.execution_success
            ):
                ctx = self._kurtarmayi_dene(ctx, cursor, conn)

        # Self-Reflection Check (Auto-Correction & Self-Retry on failure)
        if not ctx.execution_success and ctx.intent == "FILE_OPERATION":
            reflected, corrected_output = self.self_reflection.reflect_and_retry(ctx)
            if reflected:
                ctx.execution_success = True
                ctx.execution_result = corrected_output
                ctx.verification_passed = True

        # 9. Prompt Generator (Builds enriched prompt with live web data and multi-turn chat history)
        ctx = self.l9_prompt.process(ctx)

        # 10. LLM Core (allow_llm=True ise cevabı burada üretir)
        ctx = self.l10_llm.process(ctx, allow_llm=allow_llm)

        # 11. Action Planner
        ctx = self.l11_action.process(ctx)

        # 13. Result Checker
        ctx = self.l13_checker.process(ctx)

        # Bağlamdan doldurulan referansı kullanıcıya BİLDİR. Sessiz tahmin,
        # yanlış dosyanın fark edilmeden gönderilmesi demektir.
        if ctx.baglam_notlari and ctx.execution_result:
            ctx.execution_result = (
                f"_(bağlamdan: {', '.join(ctx.baglam_notlari)})_\n\n"
                f"{ctx.execution_result}"
            )

        # Bağlamı güncelle — bir sonraki "onu gönder" bunu kullanacak
        self._baglami_kaydet(ctx)

        # 14. Response Builder
        ctx = self.l14_response.process(ctx)

        return ctx

    # =====================================================================
    # RECOVERY YARDIMCISI (Faz 4)
    # =====================================================================
    def _kurtarmayi_dene(self, ctx, cursor, conn):
        """Tek adımlı komut başarısız olduğunda alternatif üretir."""
        from core.recovery import kurtar, kurtarma_raporu

        try:
            kurtarma = kurtar(
                ctx.son_arac, ctx.son_arac_argumanlari, ctx.son_arac_sonucu,
                db_cursor=cursor, db_conn=conn, kanal=ctx.kanal,
            )
        except Exception as e:
            print(f"[Ultron Kurtarma] {e}")
            return ctx

        if not kurtarma.denendi:
            return ctx

        ctx.execution_result = kurtarma_raporu(ctx.execution_result, kurtarma)
        # ⚠️ AŞAĞI ÇEKME YOK. Araç zaten başarılıysa (örn. "bulunamadı" mesajı)
        # kurtarma başarısız diye False yaparsak arayüz mesajı göstermeyi
        # bırakır ve cevabı LLM üretir → Ultron olmayan dosyayı anlatır.
        ctx.execution_success = kurtarma.basarili or ctx.execution_success
        return ctx

    # =====================================================================
    # CONTEXT MANAGER YARDIMCILARI (Faz 2)
    # =====================================================================
    def _baglami_uygula(self, ctx):
        """Cümledeki eksik referansları bağlamdan doldurur."""
        try:
            cozulmus, notlar = BAGLAM.coz(ctx.normalized_input, ctx.kanal)
        except Exception as e:
            print(f"[Ultron Baglam] Referans çözülemedi: {e}")
            return ctx
        if notlar:
            ctx.normalized_input = cozulmus
            ctx.baglam_notlari = notlar
        return ctx

    def _baglami_kaydet(self, ctx):
        """
        Konuşmanın durumunu günceller.

        Sadece BAŞARILI komutlar bağlamı değiştirir: başarısız bir komutun
        konusu "en son konuşulan şey" sayılmamalı.
        """
        if not ctx.execution_success:
            return
        try:
            alanlar = {'son_intent': ctx.intent}

            # Son dosya: arama TEK sonuç verdiyse o dosyadır. Birden fazlaysa
            # kullanıcı henüz seçmemiştir — tahmin etme.
            if ctx.intent in ("FILE_SEARCH", "FILE_TRANSFER", "FILE_INDEX"):
                from features import file_index
                sonuclar = file_index.son_sonuclari_al(ctx.kanal)
                if len(sonuclar) == 1:
                    alanlar['son_dosya'] = sonuclar[0].get('ad') or sonuclar[0].get('yol')

            if ctx.intent in ("WHATSAPP_MESSAGE", "EMAIL_MESSAGE"):
                alici = self._aliciyi_coz(ctx)
                if alici:
                    alanlar['son_kisi'] = alici

            if ctx.intent == "SYSTEM_CONTROL" and ctx.entities.get('app_name'):
                alanlar['son_uygulama'] = ctx.entities['app_name']

            BAGLAM.hatirla(ctx.kanal, **alanlar)
        except Exception as e:
            print(f"[Ultron Baglam] Bağlam kaydedilemedi: {e}")

    @staticmethod
    def _aliciyi_coz(ctx):
        metin = ctx.normalized_input
        try:
            from features.actions.whatsapp_control import whatsapp_gonderim_ayristir
            wa = whatsapp_gonderim_ayristir(metin)
            if wa:
                return wa[0]
        except Exception:
            pass
        try:
            from features.email_control import email_gonderim_ayristir
            ep = email_gonderim_ayristir(metin)
            if ep:
                return ep[0]
        except Exception:
            pass
        return None

    # =====================================================================
    # PLANNER YARDIMCILARI (Faz 1)
    # =====================================================================
    def _plani_kur_ve_calistir(self, ctx, cursor, conn):
        """
        Plan üretir, yürütür ve sonucu bağlama yazar → (ctx, planlandi).

        `planlandi=False` ise akış normal tek-adımlı yürütmeye düşer: Ollama
        kapalıysa, plan boş çıktıysa ya da model hata verdiyse Ultron çalışmaya
        devam etmeli — planner bir iyileştirmedir, tek nokta arıza değil.
        """
        plan, hata = plan_uret(ctx.normalized_input, self.config)
        if hata:
            print(f"[Ultron Planner] Plan üretilemedi: {hata}")
            return ctx, False
        if plan is None or not plan.gorevler:
            return ctx, False

        ctx.subtasks = [g.eylem for g in plan.gorevler]
        sonuc = PlanYurutucu(
            db_cursor=cursor, db_conn=conn, kanal=ctx.kanal
        ).calistir(plan)
        return self._plan_sonucunu_isle(ctx, plan, sonuc, onaylananlar=set()), True

    def _plan_sonucunu_isle(self, ctx, plan, sonuc, onaylananlar):
        if sonuc.veri:
            ctx.entities.update(sonuc.veri)

        if sonuc.onay_bekleyen:
            # Planı askıya al; kullanıcının bir sonraki mesajı onay/ret olabilir.
            # DİKKAT: onay kümesine SADECE kullanıcının açıkça onayladığı adımlar
            # girer. "Henüz sırası gelmemiş" riskli bir adımı onaylanmış saymak,
            # ikinci turda o adımın sorulmadan yürütülmesine yol açardı.
            self.bekleyen_planlar[ctx.kanal] = (plan, set(onaylananlar))
            ctx.execution_success = True   # LLM'e DÜŞMEMELİ, soruyu biz soruyoruz
            ctx.execution_result = f"{plan.ozet()}\n\n{sonuc.ozet()}"
            return ctx

        self.bekleyen_planlar.pop(ctx.kanal, None)
        ctx.execution_success = sonuc.basarili
        ctx.execution_result = f"{plan.ozet()}\n\n{sonuc.ozet()}"
        return ctx

    def _bekleyen_plani_isle(self, ctx, cursor, conn):
        """
        Askıdaki planın onay/ret cevabını işler → (cevaplandi, ctx).

        Onay/ret dışında bir şey yazıldıysa plan DÜŞÜRÜLÜR: kullanıcı konuyu
        değiştirmiştir, üç mesaj sonra gelen "evet" eski planı tetiklememeli.
        """
        plan, onaylananlar = self.bekleyen_planlar[ctx.kanal]
        kucuk = (ctx.normalized_input or "").lower().strip(" .!?")

        if any(k == kucuk or kucuk.startswith(k + " ") for k in _RET_KELIMELERI):
            self.bekleyen_planlar.pop(ctx.kanal, None)
            ctx.execution_success = True
            ctx.execution_result = "❌ Plan iptal edildi."
            return True, ctx

        if not any(k == kucuk or kucuk.startswith(k + " ") for k in _ONAY_KELIMELERI):
            # Konu değişti — planı düşür ve mesajı normal akışa bırak
            self.bekleyen_planlar.pop(ctx.kanal, None)
            return False, ctx

        bekleyen = next((g for g in plan.gorevler if g.durum == ONAY_BEKLIYOR), None)
        if bekleyen is None:
            self.bekleyen_planlar.pop(ctx.kanal, None)
            return False, ctx

        onaylananlar = set(onaylananlar) | {bekleyen.id}
        # Adım artık onaylı — bekleme durumundan çıkar ki yürütücü onu çalıştırsın
        bekleyen.durum = BEKLIYOR
        sonuc = PlanYurutucu(
            db_cursor=cursor, db_conn=conn, kanal=ctx.kanal,
            onaylanan_gorevler=onaylananlar,
        ).calistir(plan)
        return True, self._plan_sonucunu_isle(ctx, plan, sonuc, onaylananlar)
