# -*- coding: utf-8 -*-
"""
ULTRON YEREL HTTP WEBHOOK API — Mobil ve Akıllı Ev (iOS Kısayollar, Android Tasker, Home Assistant) Entegrasyonu.
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Any

_server_instance: Optional[HTTPServer] = None
_server_thread: Optional[threading.Thread] = None
_engine_ref: Optional[Any] = None

class UltronWebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Konsol gürültüsünü engelle
        pass

    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/api/status':
            self._send_json(200, {
                "status": "online",
                "app": "ULTRON Neural Core v3.0",
                "version": "3.0"
            })
        else:
            self._send_json(404, {"error": "Endpoint bulunamadı"})

    def do_POST(self):
        if self.path == '/api/command':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json(400, {"error": "Boş istek gövdesi"})
                return
            
            try:
                body_bytes = self.rfile.read(content_length)
                payload = json.loads(body_bytes.decode('utf-8'))
            except Exception as e:
                self._send_json(400, {"error": f"Geçersiz JSON: {e}"})
                return
            
            command = payload.get('command', '').strip()
            if not command:
                self._send_json(400, {"error": "'command' alanı zorunludur"})
                return
            
            channel = payload.get('channel', 'webhook')
            
            if _engine_ref is None:
                # Engine bağlanmamışsa lazy import ile dene
                try:
                    from core.engine import UltronCoreEngine
                    engine = UltronCoreEngine()
                    ctx = engine.process(command, allow_llm=True, kanal=channel)
                    resp_text = ctx.final_output or ctx.response or "İşlem tamamlandı."
                    intent = ctx.intent
                except Exception as e:
                    self._send_json(500, {"error": f"Motor çalıştırma hatası: {e}"})
                    return
            else:
                try:
                    ctx = _engine_ref.process(command, allow_llm=True, kanal=channel)
                    resp_text = ctx.final_output or ctx.response or "İşlem tamamlandı."
                    intent = ctx.intent
                except Exception as e:
                    self._send_json(500, {"error": f"Motor çalıştırma hatası: {e}"})
                    return

            self._send_json(200, {
                "success": getattr(ctx, "execution_success", True),
                "intent": intent,
                "response": resp_text
            })
        else:
            self._send_json(404, {"error": "Endpoint bulunamadı"})

def start_webhook_server(host: str = '127.0.0.1', port: int = 8899, engine: Optional[Any] = None) -> bool:
    global _server_instance, _server_thread, _engine_ref
    if _server_instance is not None:
        return True
    
    _engine_ref = engine
    try:
        server = HTTPServer((host, port), UltronWebhookHandler)
        _server_instance = server
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        _server_thread = thread
        thread.start()
        print(f"[ULTRON Webhook] API sunucusu baslatildi: http://{host}:{port}")
        return True
    except Exception as e:
        print(f"[ULTRON Webhook] Sunucu baslatilamadi: {e}")
        return False

def stop_webhook_server():
    global _server_instance, _server_thread
    if _server_instance is not None:
        try:
            _server_instance.shutdown()
            _server_instance.server_close()
        except Exception:
            pass
        _server_instance = None
        _server_thread = None
        print("[ULTRON Webhook] API sunucusu durduruldu.")
