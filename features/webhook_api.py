# -*- coding: utf-8 -*-
"""
ULTRON YEREL HTTP WEBHOOK API — iOS Kısayollar / Android Tasker / Home Assistant.

═══════════════════════════════════════════════════════════════════════════
 ⚠️ BU MODÜL ULTRON'A KOMUT ÇALIŞTIRIR. GÜVENLİK KAPILARINI ZAYIFLATMA.
═══════════════════════════════════════════════════════════════════════════

İlk sürümde HİÇBİR kimlik doğrulaması yoktu ve şu yüzden canlıya bağlanmadı:

  1. Makinedeki HERHANGİ bir süreç komut gönderebilirdi.
  2. Daha kötüsü — ziyaret ettiğin HERHANGİ bir web sayfası gönderebilirdi.
     Tarayıcı `fetch("http://127.0.0.1:8899/api/command", {mode:"no-cors"})`
     çağrısının CEVABINI okuyamaz ama İSTEĞİ yine de gönderir. Yani zararlı
     bir sayfa Ultron'a ekran görüntüsü aldırabilir, uygulama açtırabilir,
     tuş bastırabilir, bilgisayarı kilitletebilirdi. (Riskli eylemler onay
     kartında durur — ama "güvenli" sayılanlar anında çalışır.)

ÜÇ BAĞIMSIZ KAPI (üçü de geçilmeden istek çalışmaz):

  • TOKEN       — `X-Ultron-Token` ya da `Authorization: Bearer <token>`.
                  `hmac.compare_digest` ile karşılaştırılır (zamanlama sızıntısı yok).
  • CONTENT-TYPE— POST için `application/json` ZORUNLU. HTML formları yalnızca
                  urlencoded/multipart/text-plain gönderebilir, bu yüzden
                  form tabanlı CSRF bu kapıdan geçemez.
  • ORIGIN/REFERER YOK — tarayıcı her siteler-arası istekte `Origin` başlığı
                  yollar. iOS Kısayollar, Tasker ve Home Assistant yollamaz.
                  Başlık varsa istek bir web sayfasından geliyordur → reddedilir.

Ayrıca: yalnızca 127.0.0.1'e bağlanır (dışarıdan erişilemez) ve
VARSAYILAN OLARAK KAPALIDIR (`webhook_enabled`).

Token yoksa/kısaysa sunucu BAŞLAMAZ. "Kimlik doğrulaması olmadan çalışsın"
diye bir kaçış yolu bilerek bırakılmadı — sessizce korumasız çalışan bir
sunucu, hiç çalışmayandan kötüdür.
"""

import hmac
import json
import secrets
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Optional

VARSAYILAN_PORT = 8899
# Token en az bu kadar karakter olmalı — kısa token kaba kuvvete açıktır.
ASGARI_TOKEN_UZUNLUGU = 16
# Kabul edilen azami istek gövdesi (komut cümlesi için fazlasıyla yeterli)
AZAMI_GOVDE = 64 * 1024

_server_instance: Optional[HTTPServer] = None
_server_thread: Optional[threading.Thread] = None
_engine_ref: Optional[Any] = None
_token: str = ""


def token_uret() -> str:
    """Ayarlar ekranı için yeni rastgele token üretir."""
    return secrets.token_urlsafe(32)


class UltronWebhookHandler(BaseHTTPRequestHandler):

    # Sunucu adında sürüm/teknoloji sızdırma
    server_version = "Ultron"
    sys_version = ""

    def log_message(self, format, *args):
        pass   # konsol gürültüsünü engelle

    # -- yardımcılar --------------------------------------------------------

    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        # Tarayıcı hiçbir siteye bu cevabı okutmasın
        self.send_header('Access-Control-Allow-Origin', 'null')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def _tarayicidan_mi(self) -> bool:
        """Origin/Referer taşıyan istek bir web sayfasından geliyordur."""
        return bool(self.headers.get('Origin') or self.headers.get('Referer'))

    def _token_gecerli_mi(self) -> bool:
        gelen = (self.headers.get('X-Ultron-Token') or '').strip()
        if not gelen:
            yetki = (self.headers.get('Authorization') or '').strip()
            if yetki.lower().startswith('bearer '):
                gelen = yetki[7:].strip()
        if not gelen or not _token:
            return False
        return hmac.compare_digest(gelen, _token)

    def _yetki_kapilari(self) -> bool:
        """Üç kapı. Geçemezse cevabı kendisi yazar ve False döner."""
        if self._tarayicidan_mi():
            # Saldırı olabilir — kullanıcı görsün.
            print("[ULTRON Webhook] ⛔ Tarayıcıdan gelen istek reddedildi "
                  f"(Origin: {self.headers.get('Origin') or self.headers.get('Referer')})")
            self._send_json(403, {"error": "Tarayıcı kaynaklı istekler kabul edilmiyor"})
            return False
        if not self._token_gecerli_mi():
            print("[ULTRON Webhook] ⛔ Geçersiz token ile istek reddedildi")
            self._send_json(401, {"error": "Geçersiz veya eksik token"})
            return False
        return True

    # -- uçlar --------------------------------------------------------------

    def do_GET(self):
        if self.path != '/api/status':
            self._send_json(404, {"error": "Endpoint bulunamadı"})
            return
        if not self._yetki_kapilari():
            return
        self._send_json(200, {
            "status": "online",
            "app": "ULTRON Neural Core v3.0",
            "version": "3.0",
        })

    def do_POST(self):
        if self.path != '/api/command':
            self._send_json(404, {"error": "Endpoint bulunamadı"})
            return

        try:
            uzunluk = int(self.headers.get('Content-Length', 0))
        except (TypeError, ValueError):
            uzunluk = 0
        if uzunluk > AZAMI_GOVDE:
            # Büyük gövdeyi okumadan kes — bilerek boşaltmıyoruz.
            self._send_json(413, {"error": "İstek gövdesi çok büyük"})
            return

        # ⚠️ GÖVDE HER HÂLÜKÂRDA OKUNUR (reddedecek olsak bile).
        #    Okumadan cevap yazıp bağlantıyı kapatırsak istemci 415/401 yerine
        #    "connection reset" görür (Windows'ta WinError 10053). Yani hata
        #    mesajımız hiç ulaşmaz. Boyut zaten AZAMI_GOVDE ile sınırlı.
        ham = self.rfile.read(uzunluk) if uzunluk > 0 else b''

        if not self._yetki_kapilari():
            return

        # HTML formu bu içerik türünü gönderemez → form tabanlı CSRF burada durur.
        icerik_turu = (self.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        if icerik_turu != 'application/json':
            self._send_json(415, {"error": "Content-Type: application/json zorunlu"})
            return

        if not ham:
            self._send_json(400, {"error": "Boş istek gövdesi"})
            return

        try:
            payload = json.loads(ham.decode('utf-8'))
            if not isinstance(payload, dict):
                raise ValueError('nesne bekleniyordu')
        except Exception as e:
            self._send_json(400, {"error": f"Geçersiz JSON: {e}"})
            return

        command = str(payload.get('command', '') or '').strip()
        if not command:
            self._send_json(400, {"error": "'command' alanı zorunludur"})
            return

        channel = str(payload.get('channel', 'webhook') or 'webhook')

        if _engine_ref is None:
            self._send_json(503, {"error": "Motor bağlı değil"})
            return

        try:
            ctx = _engine_ref.process(command, allow_llm=True, kanal=channel)
        except Exception as e:
            print(f"[ULTRON Webhook] Motor hatası: {type(e).__name__}")
            self._send_json(500, {"error": f"Motor çalıştırma hatası: {type(e).__name__}"})
            return

        # Riskli komutlar onay kartında durur ve YÜRÜTÜLMEZ. Çağıran bunu
        # bilmeli — yoksa "başarılı" sanıp işin yapıldığını zanneder.
        onay_bekliyor = getattr(ctx, 'security_level', '') in (
            'CONFIRM', 'DOUBLE_CONFIRM', 'FORBIDDEN')

        self._send_json(200, {
            "success": bool(getattr(ctx, "execution_success", False)),
            "intent": getattr(ctx, 'intent', None),
            "response": getattr(ctx, 'final_output', None) or getattr(ctx, 'response', None)
                        or "İşlem tamamlandı.",
            "onay_bekliyor": onay_bekliyor,
        })


def start_webhook_server(host: str = '127.0.0.1', port: int = VARSAYILAN_PORT,
                         engine: Optional[Any] = None, token: str = "") -> bool:
    """Sunucuyu başlatır. Token yoksa/kısaysa BAŞLATMAZ."""
    global _server_instance, _server_thread, _engine_ref, _token

    if _server_instance is not None:
        return True

    token = (token or "").strip()
    if len(token) < ASGARI_TOKEN_UZUNLUGU:
        print(f"[ULTRON Webhook] ⛔ Başlatılmadı: token en az "
              f"{ASGARI_TOKEN_UZUNLUGU} karakter olmalı. Ayarlar'dan üretebilirsin.")
        return False

    # Dışarıya açık bağlanma girişimini reddet — bu sunucu komut çalıştırıyor.
    if host not in ('127.0.0.1', 'localhost', '::1'):
        print(f"[ULTRON Webhook] ⛔ Başlatılmadı: yalnızca 127.0.0.1 desteklenir "
              f"(istenen: {host}).")
        return False

    _engine_ref = engine
    _token = token
    try:
        server = HTTPServer((host, port), UltronWebhookHandler)
    except Exception as e:
        print(f"[ULTRON Webhook] Sunucu baslatilamadi: {e}")
        _token = ""
        _engine_ref = None
        return False

    _server_instance = server
    thread = threading.Thread(target=server.serve_forever, daemon=True,
                             name="UltronWebhook")
    _server_thread = thread
    thread.start()
    print(f"[ULTRON Webhook] API sunucusu baslatildi: http://{host}:{port} (token korumali)")
    return True


def stop_webhook_server():
    global _server_instance, _server_thread, _engine_ref, _token
    if _server_instance is not None:
        try:
            _server_instance.shutdown()
            _server_instance.server_close()
        except Exception:
            pass
        _server_instance = None
        _server_thread = None
        _engine_ref = None
        _token = ""
        print("[ULTRON Webhook] API sunucusu durduruldu.")


def calisiyor_mu() -> bool:
    return _server_instance is not None
