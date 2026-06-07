"""Minimax CN handler — same as Minimax but CN endpoint."""

from app.providers.minimax.handler import MinimaxHandler


class MinimaxCnHandler(MinimaxHandler):
    """Handler for Minimax CN provider."""

    ENDPOINT = "https://api.minimaxi.com/v1/get_voice"
