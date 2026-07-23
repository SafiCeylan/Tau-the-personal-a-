"""
Online mode has been removed.

This module previously contained Gemini/online API helpers. To avoid accidental
external API calls the functions have been replaced with lightweight stubs
that return a clear message indicating online mode is disabled.
"""

def gemini_api_ile_soru_sor(*args, **kwargs):
    """Stub kept for compatibility. Online mode is disabled."""
    return "Online mod devre dışı bırakıldı. Lütfen offline modu kullanın."
