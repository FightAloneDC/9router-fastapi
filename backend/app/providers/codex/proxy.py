"""Codex OAuth proxy server.

Runs a local HTTP server on port 1455 that auto-exchanges OAuth tokens
server-side when the Codex callback arrives.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Callable, Coroutine, Optional
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

CODEX_PORT = 1455
CODEX_PROXY_TIMEOUT_S = 300  # 5 minutes


def _render_result_page(success: bool, message: str) -> str:
    color = "#22c55e" if success else "#ef4444"
    icon = "&#10003;" if success else "&#10007;"
    title = "Authentication Successful" if success else "Authentication Failed"
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:system-ui;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#f5f5f5}}.c{{text-align:center;padding:2rem;background:#fff;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,.1)}}.i{{color:{color};font-size:3rem}}h1{{margin:1rem 0}}p{{color:#666}}</style>
</head><body><div class="c"><div class="i">{icon}</div><h1>{title}</h1><p>{message}</p><p>Closing in <span id="cd">3</span>s...</p>
<script>let n=3;const c=document.getElementById("cd");const t=setInterval(()=>{{n--;c.textContent=n;if(n<=0){{clearInterval(t);window.close();}}}},1000);</script>
</div></body></html>"""


def _make_callback_handler(
    sessions: dict,
    exchange_fn: Callable[..., Coroutine[Any, Any, dict]],
    save_fn: Callable[..., Coroutine[Any, Any, Any]],
    stop_fn: Callable[[], None],
    provider_id: str,
) -> type:
    """Create a BaseHTTPRequestHandler subclass bound to proxy state.

    Returns a class (not instance) suitable for HTTPServer.
    """

    class _CodexCallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            logger.info(f"Codex proxy: {format % args}")

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)

            if path not in ("/callback", "/auth/callback"):
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not found")
                return

            code = params.get("code", [None])[0]
            state = params.get("state", [None])[0]
            error_param = params.get("error", [None])[0]
            session = sessions.get(state) if state else None

            if session:
                try:
                    if error_param:
                        raise Exception(params.get("error_description", [error_param])[0])
                    if not code:
                        raise Exception("No authorization code received")

                    # Exchange tokens synchronously (we're in a thread)
                    loop = asyncio.new_event_loop()
                    try:
                        token_data = loop.run_until_complete(
                            exchange_fn(
                                provider_id, code, session["redirectUri"],
                                session["codeVerifier"], state or ""
                            )
                        )
                    finally:
                        loop.close()

                    # Save connection synchronously
                    loop = asyncio.new_event_loop()
                    try:
                        conn = loop.run_until_complete(
                            save_fn(provider_id, token_data)
                        )
                    finally:
                        loop.close()

                    session["status"] = "done"
                    session["connectionId"] = str(conn.id)
                    session["email"] = conn.email

                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(
                        _render_result_page(True, "You can close this window.").encode()
                    )
                except Exception as err:
                    session["status"] = "error"
                    session["error"] = str(err)
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(_render_result_page(False, str(err)).encode())
                finally:
                    stop_fn()
                return

            # No matching session — redirect to app port fallback
            app_port = "5173"
            for s in sessions.values():
                app_port = s.get("appPort", "5173")
                break
            redirect_url = f"http://localhost:{app_port}/callback?{parsed.query}"
            self.send_response(302)
            self.send_header("Location", redirect_url)
            self.end_headers()

    return _CodexCallbackHandler


class CodexProxy:
    """Manages the Codex OAuth proxy server lifecycle."""

    def __init__(
        self,
        exchange_fn: Callable[..., Coroutine[Any, Any, dict]],
        save_connection_fn: Callable[..., Coroutine[Any, Any, Any]],
    ):
        self._exchange_fn = exchange_fn
        self._save_connection_fn = save_connection_fn
        self._sessions: dict = {}
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._timer: Optional[threading.Timer] = None
        self._provider_id = "codex"

    async def _save_connection_sync(self, provider: str, token_data: dict):
        """Save connection from the proxy thread using a new async session."""
        from app.database import async_session
        async with async_session() as db:
            conn = await self._save_connection_fn(db, provider, token_data)
            await db.commit()
            return conn

    def _start_server(self) -> bool:
        """Start the HTTP server in a background thread."""
        if self._server is not None:
            return True

        try:
            handler_cls = _make_callback_handler(
                sessions=self._sessions,
                exchange_fn=self._exchange_fn,
                save_fn=self._save_connection_sync,
                stop_fn=self.stop,
                provider_id=self._provider_id,
            )
            self._server = HTTPServer(("0.0.0.0", CODEX_PORT), handler_cls)
            self._thread = threading.Thread(
                target=self._server.serve_forever, daemon=True
            )
            self._thread.start()
            logger.info(f"Codex proxy started on port {CODEX_PORT}")
            return True
        except OSError as e:
            logger.error(f"Failed to start codex proxy on port {CODEX_PORT}: {e}")
            return False

    def start(self, app_port: int, state: str, code_verifier: str, redirect_uri: str) -> dict:
        """Start proxy and register session for auto-exchange."""
        if not state or not code_verifier or not redirect_uri:
            raise ValueError("Missing state, code_verifier, or redirect_uri")

        proxy_started = self._start_server()
        if not proxy_started:
            return {"success": False, "reason": "port_busy"}

        self._sessions[state] = {
            "codeVerifier": code_verifier,
            "redirectUri": redirect_uri,
            "appPort": str(app_port),
            "status": "pending",
        }

        # Auto-stop after timeout
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(CODEX_PROXY_TIMEOUT_S, self.stop)
        self._timer.daemon = True
        self._timer.start()

        return {"success": True, "serverSide": True}

    def poll_status(self, state: str) -> dict:
        """Poll for session status."""
        if not state:
            raise ValueError("Missing state")

        session = self._sessions.get(state)
        if not session:
            return {"status": "unknown"}

        if session["status"] in ("done", "error"):
            payload = {**session}
            del self._sessions[state]
            return payload

        return {"status": session["status"]}

    def stop(self) -> None:
        """Stop the proxy server and cleanup."""
        if self._timer:
            self._timer.cancel()
            self._timer = None

        if self._server:
            self._server.shutdown()
            self._server = None
            self._thread = None
            logger.info("Codex proxy stopped")
