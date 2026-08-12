"""Qoder COSY signing.

⚠️  CRITICAL: Do NOT modify this provider without user approval.
    Extensive investigation and trial-error has been done.
    See docs/archives/qoder-docs/BUG-FIXING-LOG.md before making any changes.

Qoder uses two auth shapes in qodercli:
- Plain bearer headers for a few account/config endpoints.
- ``Bearer COSY.{payload}.{signature}`` for `/algo` service endpoints such as
  model list and chat generation.

This module implements the second shape used by provider model/chat requests.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
from typing import Any
from urllib.parse import urlparse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .constants import (
    QODER_CLIENT_TYPE,
    QODER_DATA_POLICY,
    QODER_IDE_VERSION,
    QODER_LOGIN_VERSION,
    QODER_MACHINE_TYPE,
    QODER_RSA_PUBLIC_KEY,
)


def _generate_aes_key() -> str:
    """Generate a 16-byte AES key from the first 16 chars of a UUID."""
    return str(uuid.uuid4())[:16]


def _pkcs7_pad(data: bytes, block_size: int) -> bytes:
    padding_len = block_size - (len(data) % block_size)
    return data + bytes([padding_len] * padding_len)


def _aes_encrypt_cbc_base64(plaintext: str, key_str: str) -> str:
    key_bytes = key_str.encode("utf-8")
    if len(key_bytes) != 16:
        raise ValueError(f"AES key must be 16 bytes, got {len(key_bytes)}")

    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(key_bytes[:16]))
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(_pkcs7_pad(plaintext.encode("utf-8"), 16))
    encrypted += encryptor.finalize()
    return base64.b64encode(encrypted).decode("ascii")


def _rsa_encrypt_base64(data: str) -> str:
    public_key = serialization.load_pem_public_key(QODER_RSA_PUBLIC_KEY.encode("utf-8"))
    encrypted = public_key.encrypt(data.encode("utf-8"), padding.PKCS1v15())
    return base64.b64encode(encrypted).decode("ascii")


def _encrypt_user_info(user_info: dict[str, Any]) -> tuple[str, str]:
    aes_key = _generate_aes_key()
    # qodercli payload JSON is compact; spaces here change the encrypted block.
    plaintext = json.dumps(user_info, separators=(",", ":"))
    return _rsa_encrypt_base64(aes_key), _aes_encrypt_cbc_base64(plaintext, aes_key)


def _md5_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.md5(data).hexdigest()


def _compute_sig_path(request_url: str) -> str:
    """Strip the leading /algo prefix from the request path."""
    parsed = urlparse(request_url)
    pathname = parsed.path or ""
    if pathname.startswith("/algo"):
        return pathname[len("/algo"):]
    return pathname


def generate_machine_id() -> str:
    """Generate a fresh machine UUID."""
    return str(uuid.uuid4())


def build_cosy_headers(
    body: bytes,
    request_url: str,
    user_id: str,
    auth_token: str,
    name: str = "",
    email: str = "",
    machine_id: str = "",
    date: str | None = None,
) -> dict[str, str]:
    """Build COSY headers for Qoder `/algo` service endpoints."""
    if not user_id:
        raise ValueError("cosy: user id is empty")
    if not auth_token:
        raise ValueError("cosy: auth token is empty")

    machine_id = machine_id or generate_machine_id()
    timestamp = date or str(int(time.time()))
    cosy_key, info = _encrypt_user_info({
        "uid": user_id,
        "security_oauth_token": auth_token,
        "name": name or "",
        "aid": "",
        "email": email or "",
    })

    payload_json = json.dumps({
        "version": "v1",
        "requestId": str(uuid.uuid4()),
        "info": info,
        "cosyVersion": QODER_IDE_VERSION,
        "ideVersion": "",
    }, separators=(",", ":"))
    payload_b64 = base64.b64encode(payload_json.encode("utf-8")).decode("ascii")

    sig_path = _compute_sig_path(request_url)
    sig_input = "\n".join([
        payload_b64,
        cosy_key,
        timestamp,
        body.decode("latin1"),
        sig_path,
    ])
    signature = _md5_hex(sig_input.encode("latin1"))

    return {
        "Accept": "text/event-stream",
        "Authorization": f"Bearer COSY.{payload_b64}.{signature}",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Cosy-Business-Product": "cli",
        "Cosy-Business-Type": "agent",
        "Cosy-ClientType": QODER_CLIENT_TYPE,
        "Cosy-Data-Policy": QODER_DATA_POLICY,
        "Cosy-Date": timestamp,
        "Cosy-Key": cosy_key,
        "Cosy-MachineId": machine_id,
        "Cosy-MachineToken": machine_id,
        "Cosy-MachineType": QODER_MACHINE_TYPE,
        "Cosy-Scene": "assistant",
        "Cosy-User": user_id,
        "Cosy-Version": QODER_IDE_VERSION,
        "Login-Version": QODER_LOGIN_VERSION,
        "User-Agent": f"Qoder/{QODER_IDE_VERSION}",
    }
