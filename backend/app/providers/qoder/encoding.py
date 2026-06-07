"""Qoder body encoding ported from qoder2api's QoderEncoding.java.

Algorithm:
  1. base64-encode the plaintext bytes (standard alphabet).
  2. Rearrange: split into thirds, reorder as [tail][mid][head].
  3. Substitute each character via a custom alphabet mapping.

The encoded body must be sent with `&Encode=1` appended to the URL so the
server decodes in reverse. The obfuscation prevents Alibaba Cloud WAF from
pattern-matching the plaintext request body.
"""

import base64
from .constants import QODER_STD_ALPHABET, QODER_CUSTOM_ALPHABET

# Build substitution table: standard -> custom
_S2C = {}
for i in range(64):
    _S2C[QODER_STD_ALPHABET[i]] = QODER_CUSTOM_ALPHABET[i]
_S2C['='] = '$'


def qoder_encode_body(plaintext: bytes | str) -> str:
    """Encode plaintext using Qoder's WAF-bypass scheme.

    Args:
        plaintext: bytes or string to encode

    Returns:
        Encoded string
    """
    if isinstance(plaintext, str):
        plaintext = plaintext.encode('utf-8')

    # Step 1: base64 encode
    std = base64.b64encode(plaintext).decode('ascii')
    n = len(std)

    if n == 0:
        return ""

    # Step 2: rearrange [tail][mid][head]
    a = n // 3
    rearranged = std[n - a:] + std[a:n - a] + std[:a]

    # Step 3: substitute characters
    result = []
    for ch in rearranged:
        result.append(_S2C.get(ch, ch))

    return ''.join(result)
