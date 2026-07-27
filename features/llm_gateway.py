# -*- coding: utf-8 -*-
"""
LLM Ağ Geçidi — sağlayıcı seçimi tek yerden.

Önceden `llm_uret` yalnızca ui/tau_window.py içindeydi; bu yüzden LLM cevabı
üretme yeteneği UI'a bağlıydı. Sonuç: `engine.process()`'i tek başına kullanan
yerler (zamanlanmış görevler, Telegram köprüsü) LLM cevabı ALAMIYORDU — sadece
deterministik execution üreten komutlar çalışıyordu.

Bu modül LLM çağrısını UI'dan ayırır; hem masaüstü hem engine hem Telegram
aynı kapıyı kullanır. Böylece LLM çağrısı artık engine'in içine (LLMCoreLayer)
taşınabilir.
"""

from features.kobold import kobold_generate
from features.ollama import ollama_generate
from features.gemini import gemini_generate
from features.tau_backend import tau_backend_soru_sor


def llm_uret(provider, prompt, config, context=None):
    """Seçili sağlayıcıdan yanıt üretir → (cevap, güncel_bağlam)."""
    if provider == 'ollama':
        return ollama_generate(
            prompt,
            ollama_url=config.get('ollama_url', 'http://127.0.0.1:11434'),
            model=config.get('ollama_model', 'gemma3:4b'),
            context=context,
        )
    if provider == 'gemini':
        return gemini_generate(
            prompt,
            api_key=config.get('gemini_api_key'),
            model=config.get('gemini_model', 'gemini-1.5-flash'),
            context=context,
        )
    if provider == 'kobold':
        return kobold_generate(
            prompt,
            kobold_url=config.get('kobold_url', 'http://localhost:5001'),
            context=context,
        )
    if provider == 'tau_backend':
        ans = tau_backend_soru_sor(
            prompt,
            backend_url=config.get('tau_backend_url'),
            api_key=config.get('tau_api_key'),
            timeout=config.get('tau_timeout', 30),
            endpoint=config.get('tau_endpoint', '/chat'),
        )
        return ans, context
    return f"Bilinmeyen AI sağlayıcı: '{provider}'", context
