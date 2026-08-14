"""Resolve A records via 8.8.8.8 so passthrough bypasses /etc/hosts."""

from __future__ import annotations

import random
import socket
import struct

_CACHE: dict[str, str] = {}


def resolve_a(hostname: str) -> str:
    if hostname in _CACHE:
        return _CACHE[hostname]
    name = hostname.rstrip(".").encode("ascii")
    tid = random.randint(0, 65535)
    header = struct.pack("!HHHHHH", tid, 0x0100, 1, 0, 0, 0)
    qname = b"".join(
        bytes([len(part)]) + part for part in name.split(b".")
    ) + b"\x00"
    query = header + qname + struct.pack("!HH", 1, 1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3)
    try:
        sock.sendto(query, ("8.8.8.8", 53))
        data, _ = sock.recvfrom(512)
    finally:
        sock.close()
    if len(data) < 12:
        raise OSError(f"DNS short reply for {hostname}")
    answers = struct.unpack("!H", data[6:8])[0]
    offset = 12
    while data[offset] != 0:
        offset += 1 + data[offset]
    offset += 5
    for _ in range(answers):
        if offset + 12 > len(data):
            break
        if data[offset] & 0xC0 == 0xC0:
            offset += 2
        else:
            while data[offset] != 0:
                offset += 1 + data[offset]
            offset += 1
        rtype, _rclass, _ttl, rdlen = struct.unpack(
            "!HHIH", data[offset:offset + 10],
        )
        offset += 10
        if rtype == 1 and rdlen == 4:
            ip = socket.inet_ntoa(data[offset:offset + 4])
            _CACHE[hostname] = ip
            return ip
        offset += rdlen
    raise OSError(f"No A record for {hostname}")
