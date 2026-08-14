"""HTTPS MITM listener — spawned as a child process.

Listens on MITM_PORT (default 443), presents a forged leaf cert via SNI,
logs matching IDE traffic, and passthroughs to the real origin IP
(resolved via 8.8.8.8 so /etc/hosts does not loop).
"""

from __future__ import annotations

import asyncio
import json
import os
import ssl
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.services.mitm.cert import generate_leaf_cert, generate_root_ca
from app.services.mitm.dns_resolve import resolve_a
from app.services.mitm.hosts import URL_PATTERNS, get_tool_for_host
from app.services.mitm.paths import CA_CERT, CA_KEY, MITM_DIR

PORT = int(os.environ.get("MITM_PORT", "443"))
INGEST_URL = os.environ.get("MITM_INGEST_URL", "")
INGEST_TOKEN = os.environ.get("MITM_INGEST_TOKEN", "")
LEAF_DIR = MITM_DIR / "leaf"
LEAF_DIR.mkdir(parents=True, exist_ok=True)


def _leaf_files(hostname: str) -> tuple[Path, Path]:
    safe = hostname.replace("/", "_")
    crt = LEAF_DIR / f"{safe}.crt"
    key = LEAF_DIR / f"{safe}.key"
    if not crt.is_file() or not key.is_file():
        cert_pem, key_pem = generate_leaf_cert(hostname)
        crt.write_bytes(cert_pem)
        key.write_bytes(key_pem)
    return crt, key


def _sni_callback(
    ssl_sock: ssl.SSLSocket,
    server_name: str | None,
    _initial: ssl.SSLContext,
) -> None:
    host = server_name or "localhost"
    crt, key = _leaf_files(host)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(crt), str(key))
    ssl_sock.context = ctx


def _ingest(entry: dict) -> None:
    if not INGEST_URL:
        return
    payload = json.dumps(entry).encode("utf-8")
    req = Request(
        INGEST_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Mitm-Token": INGEST_TOKEN,
        },
    )
    try:
        urlopen(req, timeout=2).read()
    except (URLError, TimeoutError, OSError):
        pass


async def _read_http_request(
    reader: asyncio.StreamReader,
) -> tuple[str, str, str, dict[str, str], bytes]:
    header_blob = await reader.readuntil(b"\r\n\r\n")
    head, _sep, _ = header_blob.partition(b"\r\n\r\n")
    lines = head.decode("iso-8859-1").split("\r\n")
    method, path, proto = lines[0].split(" ", 2)
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()
    length = int(headers.get("content-length") or "0")
    body = await reader.readexactly(length) if length else b""
    return method, path, proto, headers, body


async def _passthrough(
    writer: asyncio.StreamWriter,
    method: str,
    path: str,
    headers: dict[str, str],
    body: bytes,
    target_host: str,
) -> tuple[int, float]:
    started = time.monotonic()
    ip = await asyncio.to_thread(resolve_a, target_host)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    reader, up = await asyncio.open_connection(
        ip, 443, ssl=ctx, server_hostname=target_host,
    )
    hdrs = dict(headers)
    hdrs["host"] = target_host
    lines = [f"{method} {path} HTTP/1.1"]
    for key, value in hdrs.items():
        if key in ("proxy-connection",):
            continue
        lines.append(f"{key}: {value}")
    raw = ("\r\n".join(lines) + "\r\n\r\n").encode("iso-8859-1") + body
    up.write(raw)
    await up.drain()
    first = await reader.readline()
    writer.write(first)
    rest = await reader.read(256 * 1024)
    writer.write(rest)
    await writer.drain()
    up.close()
    try:
        await up.wait_closed()
    except OSError:
        pass
    status = 502
    try:
        status = int(first.decode("iso-8859-1").split(" ", 2)[1])
    except (IndexError, ValueError):
        pass
    return status, (time.monotonic() - started) * 1000


async def _handle(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    try:
        method, path, _proto, headers, body = await _read_http_request(reader)
        if path == "/_mitm_health":
            payload = json.dumps({"ok": True, "pid": os.getpid()}).encode()
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: " + str(len(payload)).encode() + b"\r\n\r\n"
                + payload
            )
            await writer.drain()
            return
        host = headers.get("host", "").split(":")[0]
        tool = get_tool_for_host(host)
        patterns = URL_PATTERNS.get(tool or "", [])
        interesting = bool(tool) and any(p in path for p in patterns)
        status, latency = await _passthrough(
            writer, method, path, headers, body, host or "localhost",
        )
        if interesting:
            preview = body[:500].decode("utf-8", errors="replace")
            await asyncio.to_thread(_ingest, {
                "tool": tool,
                "direction": "request",
                "method": method,
                "url": f"https://{host}{path}",
                "status_code": status,
                "latency_ms": int(latency),
                "body_preview": preview or None,
            })
    except Exception:
        try:
            writer.write(
                b"HTTP/1.1 502 Bad Gateway\r\n"
                b"Content-Length: 0\r\n\r\n"
            )
            await writer.drain()
        except OSError:
            pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except OSError:
            pass


async def _main() -> None:
    generate_root_ca(force=False)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(CA_CERT), str(CA_KEY))
    ctx.sni_callback = _sni_callback
    server = await asyncio.start_server(
        _handle, "0.0.0.0", PORT, ssl=ctx,
    )
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(_main())
