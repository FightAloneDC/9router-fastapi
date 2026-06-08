"""Cursor OAuth handler — Import Token (no OAuth flow)."""

from __future__ import annotations

import os
import platform
import re
import sqlite3
import subprocess
from typing import Optional

from pydantic import BaseModel

from app.providers import PROVIDER_CURSOR
from app.providers.oauth_base import ImportTokenHandler


class CursorImportRequest(BaseModel):
    accessToken: str
    machineId: str


class CursorOAuthHandler(ImportTokenHandler):
    """OAuth handler for Cursor (import token directly)."""

    PROVIDER_ID = PROVIDER_CURSOR
    CONFIG = {
        "apiEndpoint": "https://api2.cursor.sh",
        "chatEndpoint": "/aiserver.v1.ChatService/StreamUnifiedChatWithTools",
        "modelsEndpoint": "/aiserver.v1.AiService/GetDefaultModelNudgeData",
        "api3Endpoint": "https://api3.cursor.sh",
        "agentEndpoint": "https://agent.api5.cursor.sh",
        "agentNonPrivacyEndpoint": "https://agentn.api5.cursor.sh",
        "clientVersion": "3.1.0",
        "clientType": "ide",
        "tokenStoragePaths": {
            "linux": "~/.config/Cursor/User/globalStorage/state.vscdb",
            "macos": "/Users/<user>/Library/Application Support/Cursor/User/globalStorage/state.vscdb",
            "windows": "%APPDATA%\\Cursor\\User\\globalStorage\\state.vscdb",
        },
        "dbKeys": {
            "accessToken": "cursorAuth/accessToken",
            "machineId": "storage.serviceMachineId",
        },
    }

    async def auto_import(self) -> dict:
        """Auto-detect and import token from Cursor IDE's local SQLite database."""
        # Platform check on Linux
        if platform.system().lower() == "linux":
            if not self._is_cursor_installed():
                return {
                    "found": False,
                    "error": "Cursor config files found but Cursor IDE does not appear to be installed. Skipping auto-import.",
                }

        system = platform.system().lower()
        db_path = os.path.expanduser("~/.config/Cursor/User/globalStorage/state.vscdb")
        if system == "darwin":
            db_path = os.path.expanduser(
                "~/Library/Application Support/Cursor/User/globalStorage/state.vscdb"
            )
        elif system == "windows":
            appdata = os.environ.get("APPDATA", "")
            db_path = os.path.join(appdata, "Cursor", "User", "globalStorage", "state.vscdb")

        if not os.path.exists(db_path):
            if system == "windows":
                return {"windowsManual": True, "error": "Could not auto-detect on Windows"}
            raise Exception("Could not find Cursor token. Please enter it manually.")

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            access_token_key = self.config["dbKeys"]["accessToken"]
            machine_id_key = self.config["dbKeys"]["machineId"]

            cursor.execute(
                "SELECT key, value FROM itemTable WHERE key IN (?, ?)",
                (access_token_key, machine_id_key),
            )
            rows = cursor.fetchall()
            conn.close()

            data = {row[0]: row[1] for row in rows}
            access_token = data.get(access_token_key, "")
            machine_id = data.get(machine_id_key, "")

            if not access_token:
                raise Exception("Access token not found in Cursor database")

            return {"found": True, "accessToken": access_token, "machineId": machine_id}
        except sqlite3.Error as e:
            raise Exception(f"Failed to read Cursor database: {e}")

    def _is_cursor_installed(self) -> bool:
        """Check if Cursor IDE is installed on this system."""
        try:
            result = subprocess.run(["which", "cursor"], capture_output=True, timeout=5)
            if result.returncode == 0:
                return True
        except Exception:
            pass
        return os.path.exists(os.path.expanduser("~/.local/share/applications/cursor.desktop"))

    async def validate_import_token(self, access_token: str, machine_id: str) -> dict:
        """Validate and import a token from Cursor IDE."""
        if not access_token or not isinstance(access_token, str):
            raise Exception("Access token is required")
        if not machine_id or not isinstance(machine_id, str):
            raise Exception("Machine ID is required")
        if len(access_token) < 50:
            raise Exception("Invalid token format. Token appears too short.")

        cleaned = machine_id.replace("-", "")
        if not re.match(r"^[a-f0-9]{32,}$", cleaned, re.IGNORECASE):
            raise Exception("Invalid machine ID format. Expected UUID format.")

        return {
            "accessToken": access_token,
            "machineId": machine_id,
            "expiresIn": 86400,
            "authMethod": "imported",
        }

    async def import_token(self, access_token: str, **kwargs) -> dict:
        """Import token via the generic import_token dispatch (used by /exchange endpoint)."""
        machine_id = kwargs.get("machineId", "")
        return await self.validate_import_token(access_token, machine_id)

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        return {
            "accessToken": tokens.get("accessToken"),
            "refreshToken": None,
            "expiresIn": tokens.get("expiresIn", 86400),
            "providerSpecificData": {
                "machineId": tokens.get("machineId"),
                "authMethod": "imported",
            },
        }
