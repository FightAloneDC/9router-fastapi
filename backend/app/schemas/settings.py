"""Pydantic schemas for settings."""

from typing import Any, Dict, Optional

from pydantic import BaseModel


class SettingsOut(BaseModel):
    """Current application settings — mirrors all fields from original settingsRepo.js."""

    # Auth
    requireApiKey: bool = False
    requireLogin: bool = True
    authMode: str = "password"  # password, oidc
    # OIDC
    oidcIssuerUrl: str = ""
    oidcClientId: str = ""
    # oidcClientSecret is intentionally excluded from GET responses
    oidcScopes: str = "openid profile email"
    oidcLoginLabel: str = "Sign in with OIDC"
    oidcConfigured: bool = False
    # Cloud/Tunnel
    cloudEnabled: bool = False
    tunnelEnabled: bool = False
    tunnelUrl: str = ""
    tunnelProvider: str = "cloudflare"
    tunnelDashboardAccess: bool = True
    # Tailscale
    tailscaleEnabled: bool = False
    tailscaleUrl: str = ""
    # Proxy
    outboundProxyEnabled: bool = False
    outboundProxyUrl: str = ""
    outboundNoProxy: str = ""
    # Routing Strategy
    comboStrategy: str = "fallback"  # fallback, round-robin, random
    stickyRoundRobinLimit: int = 3
    providerStrategies: Dict[str, Any] = {}
    comboStickyRoundRobinLimit: int = 1
    comboStrategies: Dict[str, Any] = {}
    # Observability
    enableObservability: bool = True
    observabilityMaxRecords: int = 1000
    observabilityBatchSize: int = 20
    observabilityFlushIntervalMs: int = 5000
    observabilityMaxJsonSize: int = 5
    # MITM
    mitmRouterBaseUrl: str = "http://localhost:20128"
    # DNS Tool
    dnsToolEnabled: Dict[str, Any] = {}
    # Misc
    rtkEnabled: bool = True
    cavemanEnabled: bool = False
    cavemanLevel: str = "full"  # full, minimal, off
    # Runtime-injected (not stored)
    enableRequestLogs: bool = False
    enableTranslator: bool = False
    hasPassword: bool = False


class SettingsUpdate(BaseModel):
    """Partial settings update — all fields optional."""

    # Auth
    requireApiKey: Optional[bool] = None
    requireLogin: Optional[bool] = None
    authMode: Optional[str] = None
    # OIDC
    oidcIssuerUrl: Optional[str] = None
    oidcClientId: Optional[str] = None
    oidcClientSecret: Optional[str] = None
    oidcScopes: Optional[str] = None
    oidcLoginLabel: Optional[str] = None
    # Cloud/Tunnel
    cloudEnabled: Optional[bool] = None
    tunnelEnabled: Optional[bool] = None
    tunnelUrl: Optional[str] = None
    tunnelProvider: Optional[str] = None
    tunnelDashboardAccess: Optional[bool] = None
    # Tailscale
    tailscaleEnabled: Optional[bool] = None
    tailscaleUrl: Optional[str] = None
    # Proxy
    outboundProxyEnabled: Optional[bool] = None
    outboundProxyUrl: Optional[str] = None
    outboundNoProxy: Optional[str] = None
    # Routing Strategy
    comboStrategy: Optional[str] = None
    stickyRoundRobinLimit: Optional[int] = None
    providerStrategies: Optional[Dict[str, Any]] = None
    comboStickyRoundRobinLimit: Optional[int] = None
    comboStrategies: Optional[Dict[str, Any]] = None
    # Observability
    enableObservability: Optional[bool] = None
    observabilityMaxRecords: Optional[int] = None
    observabilityBatchSize: Optional[int] = None
    observabilityFlushIntervalMs: Optional[int] = None
    observabilityMaxJsonSize: Optional[int] = None
    # MITM
    mitmRouterBaseUrl: Optional[str] = None
    # DNS Tool
    dnsToolEnabled: Optional[Dict[str, Any]] = None
    # Misc
    rtkEnabled: Optional[bool] = None
    cavemanEnabled: Optional[bool] = None
    cavemanLevel: Optional[str] = None
    # Password change (handled specially in router)
    newPassword: Optional[str] = None
    currentPassword: Optional[str] = None
