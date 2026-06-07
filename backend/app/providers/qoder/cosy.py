"""Qoder COSY (hybrid RSA+AES+MD5) signing.

Ported from 9router Node.js implementation (src/lib/qoder/cosy.js).

Every signed request carries:
  - an AES-128-CBC payload of the user info, the AES key wrapped in RSA
  - an MD5 signature over `payload || cosyKey || timestamp || body || sigPath`
  - the body's MD5 hash + length so the server can validate integrity
  - 17 Cosy-* / X-* headers fingerprinting the client (machine id, IDE
    version, organization id, etc.)

Authorization header format: Bearer COSY.{payloadB64}.{sig}
"""

import base64
import hashlib
import json
import time
import uuid
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .constants import (
    QODER_CLIENT_TYPE,
    QODER_DATA_POLICY,
    QODER_IDE_VERSION,
    QODER_LOGIN_VERSION,
    QODER_MACHINE_OS,
    QODER_MACHINE_TYPE,
    QODER_RSA_PUBLIC_KEY,
)


def _generate_aes_key() -> str:
    """Generate a 16-byte AES key from first 16 chars of UUID (with hyphens)."""
    return str(uuid.uuid4())[:16]


def _pkcs7_pad(data: bytes, block_size: int) -> bytes:
    """PKCS7 padding."""
    padding_len = block_size - (len(data) % block_size)
    return data + bytes([padding_len] * padding_len)


def _aes_encrypt_cbc_base64(plaintext: str, key_str: str) -> str:
    """AES-128-CBC encrypt and return base64."""
    key_bytes = key_str.encode('utf-8')
    if len(key_bytes) != 16:
        raise ValueError(f"AES key must be 16 bytes, got {len(key_bytes)}")

    iv = key_bytes[:16]
    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv))
    encryptor = cipher.encryptor()

    padded = _pkcs7_pad(plaintext.encode('utf-8'), 16)
    encrypted = encryptor.update(padded) + encryptor.finalize()

    return base64.b64encode(encrypted).decode('ascii')


def _rsa_encrypt_base64(data: str) -> str:
    """RSA encrypt with public key and return base64."""
    public_key = serialization.load_pem_public_key(QODER_RSA_PUBLIC_KEY.encode('utf-8'))

    encrypted = public_key.encrypt(
        data.encode('utf-8'),
        padding.PKCS1v15()
    )

    return base64.b64encode(encrypted).decode('ascii')


def _encrypt_user_info(user_info: dict[str, Any]) -> tuple[str, str]:
    """Encrypt user info with AES, wrap AES key with RSA.

    Returns:
        (cosyKey, info) as base64 strings
    """
    aes_key = _generate_aes_key()
    plaintext = json.dumps(user_info)
    info_b64 = _aes_encrypt_cbc_base64(plaintext, aes_key)
    cosy_key_b64 = _rsa_encrypt_base64(aes_key)

    return cosy_key_b64, info_b64


def _md5_hex(data: bytes | str) -> str:
    """Compute MD5 hex digest."""
    if isinstance(data, str):
        data = data.encode('utf-8')
    return hashlib.md5(data).hexdigest()


def _compute_sig_path(request_url: str) -> str:
    """Strip the leading /algo prefix from the request path."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(request_url)
        pathname = parsed.path or ""
    except Exception:
        return ""

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
) -> dict[str, str]:
    """Build COSY signing headers for a request.

    Args:
        body: Request body bytes
        request_url: Full URL being requested
        user_id: Qoder user ID
        auth_token: Access token (dt-xxx or jt-xxx)
        name: User display name
        email: User email
        machine_id: Machine UUID

    Returns:
        Dict of headers to add to the request
    """
    if not user_id:
        raise ValueError("cosy: user id is empty")
    if not auth_token:
        raise ValueError("cosy: auth token is empty")

    # Encrypt user info
    cosy_key, info = _encrypt_user_info({
        "uid": user_id,
        "security_oauth_token": auth_token,
        "name": name or "",
        "aid": "",
        "email": email or "",
    })

    timestamp = str(int(time.time()))
    request_id = str(uuid.uuid4())

    # Build payload JSON
    payload_json = json.dumps({
        "version": "v1",
        "requestId": request_id,
        "info": info,
        "cosyVersion": QODER_IDE_VERSION,
        "ideVersion": "",
    })
    payload_b64 = base64.b64encode(payload_json.encode('utf-8')).decode('ascii')

    # Compute signature
    sig_path = _compute_sig_path(request_url)
    sig_input = f"{payload_b64}\n{cosy_key}\n{timestamp}\n{body.decode('latin1')}\n{sig_path}"
    sig = _md5_hex(sig_input.encode('latin1'))

    # Generate machine ID if not provided
    if not machine_id:
        machine_id = generate_machine_id()

    # Compute body hash and length
    body_hash = _md5_hex(body)
    body_length = str(len(body))

    # Build Authorization header: Bearer COSY.{payloadB64}.{sig}
    auth_value = f"Bearer COSY.{payload_b64}.{sig}"

    return {
        "Authorization": auth_value,
        "Cosy-Key": cosy_key,
        "Cosy-User": user_id,
        "Cosy-Date": timestamp,
        "Cosy-Version": QODER_IDE_VERSION,
        "Cosy-Machineid": machine_id,
        "Cosy-Machinetoken": machine_id,
        "Cosy-Machinetype": QODER_MACHINE_TYPE,
        "Cosy-Machineos": QODER_MACHINE_OS,
        "Cosy-Clienttype": QODER_CLIENT_TYPE,
        "Cosy-Clientip": "127.0.0.1",
        "Cosy-Bodyhash": body_hash,
        "Cosy-Bodylength": body_length,
        "Cosy-Sigpath": sig_path,
        "Cosy-Data-Policy": QODER_DATA_POLICY,
        "Cosy-Organization-Id": "",
        "Cosy-Organization-Tags": "",
        "Login-Version": QODER_LOGIN_VERSION,
        "X-Request-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Encoding": "identity",
        "User-Agent": "Qoder/1.0.0",
    }
