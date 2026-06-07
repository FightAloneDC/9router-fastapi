"""Ollama Local handler — same as Ollama but for local device."""

from app.providers.ollama.handler import OllamaHandler


class OllamaLocalHandler(OllamaHandler):
    """Handler for Ollama Local provider (same behavior as Ollama)."""
    pass
