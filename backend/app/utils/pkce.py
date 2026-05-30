"""PKCE (Proof Key for Code Exchange) utility functions.

Generates code verifiers, code challenges (S256), and random state tokens
for OAuth flows. Ported from the original Next.js implementation.
"""

import base64
import hashlib
import secrets


def generate_code_verifier() -> str:
    """Generate a PKCE code verifier (43-128 characters, base64url-encoded)."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")


def generate_code_challenge(verifier: str) -> str:
    """Generate PKCE code challenge from verifier using S256 method."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def generate_state() -> str:
    """Generate random state token for CSRF protection."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")


def generate_pkce() -> dict:
    """Generate a complete PKCE pair with state.

    Returns:
        dict with keys: codeVerifier, codeChallenge, state
    """
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    state = generate_state()

    return {
        "codeVerifier": code_verifier,
        "codeChallenge": code_challenge,
        "state": state,
    }
