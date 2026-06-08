"""Kiro OAuth handler — Device Code flow (AWS SSO)."""

from __future__ import annotations

import json
import os
from typing import Optional

import httpx
from pydantic import BaseModel

from app.providers import PROVIDER_KIRO
from app.providers.oauth_base import DeviceCodeHandler, extract_email_from_token, decode_jwt_payload


class KiroImportRequest(BaseModel):
    refreshToken: str


class KiroSocialExchangeRequest(BaseModel):
    code: str
    codeVerifier: str
    provider: str  # "google" or "github"


class KiroOAuthHandler(DeviceCodeHandler):
    """OAuth handler for Kiro (AWS SSO)."""

    PROVIDER_ID = PROVIDER_KIRO
    CONFIG = {
        "ssoOidcEndpoint": "https://oidc.us-east-1.amazonaws.com",
        "registerClientUrl": "https://oidc.us-east-1.amazonaws.com/client/register",
        "deviceAuthUrl": "https://oidc.us-east-1.amazonaws.com/device_authorization",
        "tokenUrl": "https://oidc.us-east-1.amazonaws.com/token",
        "startUrl": "https://view.awsapps.com/start",
        "clientName": "kiro-oauth-client",
        "clientType": "public",
        "scopes": ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations"],
        "grantTypes": ["urn:ietf:params:oauth:grant-type:device_code", "refresh_token"],
        "issuerUrl": "https://identitycenter.amazonaws.com/ssoins-722374e8c3c8e6c6",
        "socialAuthEndpoint": "https://prod.us-east-1.auth.desktop.kiro.dev",
        "socialLoginUrl": "https://prod.us-east-1.auth.desktop.kiro.dev/login",
        "socialTokenUrl": "https://prod.us-east-1.auth.desktop.kiro.dev/oauth/token",
        "socialRefreshUrl": "https://prod.us-east-1.auth.desktop.kiro.dev/refreshToken",
        "authMethods": ["builder-id", "idc", "google", "github", "import"],
    }

    async def request_device_code(self, code_challenge: str = "", options: Optional[dict] = None) -> dict:
        c = self.config
        options = options or {}
        region = (options.get("region") or "").strip() or "us-east-1"
        start_url = (options.get("startUrl") or "").strip() or c["startUrl"]
        auth_method = "idc" if options.get("authMethod") == "idc" else "builder-id"
        register_url = f"https://oidc.{region}.amazonaws.com/client/register"
        device_auth_url = f"https://oidc.{region}.amazonaws.com/device_authorization"

        async with httpx.AsyncClient(timeout=30.0) as client:
            reg_resp = await client.post(
                register_url,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                json={
                    "clientName": c["clientName"],
                    "clientType": c["clientType"],
                    "scopes": c["scopes"],
                    "grantTypes": c["grantTypes"],
                    "issuerUrl": c["issuerUrl"],
                },
            )
            if reg_resp.status_code >= 400:
                raise Exception(f"Client registration failed: {reg_resp.text}")
            client_info = reg_resp.json()

            dev_resp = await client.post(
                device_auth_url,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                json={
                    "clientId": client_info["clientId"],
                    "clientSecret": client_info["clientSecret"],
                    "startUrl": start_url,
                },
            )
            if dev_resp.status_code >= 400:
                raise Exception(f"Device authorization failed: {dev_resp.text}")
            device_data = dev_resp.json()

            return {
                "device_code": device_data.get("deviceCode"),
                "user_code": device_data.get("userCode"),
                "verification_uri": device_data.get("verificationUri"),
                "verification_uri_complete": device_data.get("verificationUriComplete"),
                "expires_in": device_data.get("expiresIn"),
                "interval": device_data.get("interval", 5),
                "_clientId": client_info["clientId"],
                "_clientSecret": client_info["clientSecret"],
                "_region": region,
                "_authMethod": auth_method,
                "_startUrl": start_url,
            }

    async def poll_token(
        self, device_code: str, code_verifier: str = "", extra_data: Optional[dict] = None,
    ) -> dict:
        region = (extra_data or {}).get("_region", "us-east-1")
        token_url = f"https://oidc.{region}.amazonaws.com/token"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                token_url,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                json={
                    "clientId": (extra_data or {}).get("_clientId"),
                    "clientSecret": (extra_data or {}).get("_clientSecret"),
                    "deviceCode": device_code,
                    "grantType": "urn:ietf:params:oauth:grant-type:device_code",
                },
            )
            try:
                data = resp.json()
            except Exception:
                data = {"error": "invalid_response", "error_description": resp.text}

            if data.get("accessToken"):
                return {
                    "ok": True,
                    "data": {
                        "access_token": data["accessToken"],
                        "refresh_token": data.get("refreshToken"),
                        "expires_in": data.get("expiresIn"),
                        "profile_arn": data.get("profileArn"),
                        "_clientId": (extra_data or {}).get("_clientId"),
                        "_clientSecret": (extra_data or {}).get("_clientSecret"),
                        "_region": (extra_data or {}).get("_region"),
                        "_authMethod": (extra_data or {}).get("_authMethod"),
                        "_startUrl": (extra_data or {}).get("_startUrl"),
                    },
                }
            return {
                "ok": False,
                "data": {
                    "error": data.get("error", "authorization_pending"),
                    "error_description": data.get("error_description") or data.get("message"),
                },
            }

    def map_tokens(self, tokens: dict, extra: Optional[dict] = None) -> dict:
        email = extract_email_from_token(tokens.get("access_token", ""))
        return {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "expiresIn": tokens.get("expires_in"),
            "email": email,
            "providerSpecificData": {
                "profileArn": tokens.get("profile_arn"),
                "clientId": tokens.get("_clientId"),
                "clientSecret": tokens.get("_clientSecret"),
                "region": tokens.get("_region", "us-east-1"),
                "authMethod": tokens.get("_authMethod", "builder-id"),
                "startUrl": tokens.get("_startUrl", self.config["startUrl"]),
            },
        }

    async def validate_import_token(self, refresh_token: str) -> dict:
        """Validate and import a refresh token."""
        if not refresh_token.startswith("aorAAAAAG"):
            raise Exception("Invalid token format. Token should start with aorAAAAAG...")

        try:
            result = await self.refresh_token(refresh_token)
            return {
                "accessToken": result.get("access_token") or result.get("accessToken"),
                "refreshToken": result.get("refresh_token") or result.get("refreshToken") or refresh_token,
                "profileArn": result.get("profileArn"),
                "expiresIn": result.get("expires_in") or result.get("expiresIn"),
                "authMethod": "imported",
            }
        except Exception as e:
            raise Exception(f"Token validation failed: {e}")

    def extract_email_from_jwt(self, access_token: str) -> Optional[str]:
        """Extract email from JWT access token."""
        return extract_email_from_token(access_token)

    async def auto_import(self) -> dict:
        """Auto-detect Kiro refresh token from AWS SSO cache."""
        cache_path = os.path.expanduser("~/.aws/sso/cache")
        if not os.path.isdir(cache_path):
            return {"found": False, "error": "AWS SSO cache not found. Please login to Kiro IDE first."}

        files = os.listdir(cache_path)
        refresh_token = None
        found_file = None
        kiro_token_file = "kiro-auth-token.json"

        if kiro_token_file in files:
            try:
                with open(os.path.join(cache_path, kiro_token_file), "r") as f:
                    data = json.load(f)
                if data.get("refreshToken", "").startswith("aorAAAAAG"):
                    refresh_token = data["refreshToken"]
                    found_file = kiro_token_file
            except (json.JSONDecodeError, OSError):
                pass

        if not refresh_token:
            for file in files:
                if not file.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(cache_path, file), "r") as f:
                        data = json.load(f)
                    if data.get("refreshToken", "").startswith("aorAAAAAG"):
                        refresh_token = data["refreshToken"]
                        found_file = file
                        break
                except (json.JSONDecodeError, OSError):
                    continue

        if not refresh_token:
            return {"found": False, "error": "Kiro token not found in AWS SSO cache. Please login to Kiro IDE first."}

        return {"found": True, "refreshToken": refresh_token, "source": found_file}

    def build_import_data(self, token_data: dict, raw_refresh_token: str) -> dict:
        """Build connection save data from validated import token."""
        email = self.extract_email_from_jwt(token_data.get("accessToken", ""))
        return {
            "accessToken": token_data.get("accessToken"),
            "refreshToken": token_data.get("refreshToken", raw_refresh_token),
            "expiresIn": token_data.get("expiresIn"),
            "email": email,
            "displayName": email,
            "providerSpecificData": {
                "profileArn": token_data.get("profileArn"),
                "authMethod": "imported",
                "provider": "Imported",
            },
        }

    def build_social_save_data(self, token_data: dict, social_provider: str) -> dict:
        """Build connection save data from social login token exchange."""
        email = self.extract_email_from_jwt(token_data.get("accessToken", ""))
        return {
            **token_data,
            "email": email,
            "displayName": email,
            "providerSpecificData": {
                "profileArn": token_data.get("profileArn"),
                "authMethod": social_provider,
                "provider": social_provider.capitalize(),
            },
        }

    def build_social_login_url(self, provider: str, code_challenge: str, state: str = "") -> str:
        """Build Google/GitHub social login URL."""
        idp = "Google" if provider == "google" else "Github"
        redirect_uri = "kiro://kiro.kiroAgent/authenticate-success"
        return (
            f"{self.config['socialAuthEndpoint']}/login"
            f"?idp={idp}"
            f"&redirect_uri={redirect_uri}"
            f"&code_challenge={code_challenge}"
            f"&code_challenge_method=S256"
            f"&state={state}"
            f"&prompt=select_account"
        )

    async def exchange_social_code(self, code: str, code_verifier: str) -> dict:
        """Exchange authorization code for tokens (Social Login)."""
        redirect_uri = "kiro://kiro.kiroAgent/authenticate-success"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.config['socialAuthEndpoint']}/oauth/token",
                headers={"Content-Type": "application/json"},
                json={
                    "code": code,
                    "code_verifier": code_verifier,
                    "redirect_uri": redirect_uri,
                },
            )
        if resp.status_code >= 400:
            raise Exception(f"Token exchange failed: {resp.text}")
        data = resp.json()
        return {
            "accessToken": data.get("accessToken"),
            "refreshToken": data.get("refreshToken"),
            "profileArn": data.get("profileArn"),
            "expiresIn": data.get("expiresIn", 3600),
        }

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh token — AWS SSO OIDC or social auth."""
        c = self.config
        # Social auth refresh
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                c["socialRefreshUrl"],
                headers={"Content-Type": "application/json"},
                json={"refreshToken": refresh_token},
            )
        if resp.status_code >= 400:
            raise Exception(f"Token refresh failed: {resp.text}")
        data = resp.json()
        return {
            "access_token": data.get("accessToken"),
            "refresh_token": data.get("refreshToken"),
            "expires_in": data.get("expiresIn"),
        }
