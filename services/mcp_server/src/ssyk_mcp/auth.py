from __future__ import annotations

import hmac
import os
from typing import Any, List, Optional

from pydantic import AnyHttpUrl

from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.auth.providers.debug import DebugTokenVerifier
from fastmcp.server.auth.providers.jwt import JWTVerifier


def _split_csv(value: Optional[str]) -> List[str]:
    if value is None:
        return []
    stripped = value.strip()
    if stripped == "":
        return []
    return [part.strip() for part in stripped.split(",") if part.strip()]


def _is_truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def build_auth(*, base_url: str) -> Optional[Any]:
    """Build RemoteAuthProvider (OAuth 2.0 / DCR) from environment.

    Environment variables:
      - AUTH_ENABLED: true/false
      - AUTH_JWKS_URI: https://.../.well-known/jwks.json
      - AUTH_ISSUER: https://issuer.example.com
      - AUTH_AUDIENCE: expected token audience
      - AUTHORIZATION_SERVERS: comma-separated list of OAuth issuer base URLs (defaults to AUTH_ISSUER)
      - AUTH_ALLOWED_REDIRECT_URIS: comma-separated patterns; omit to default to localhost-only
      - FASTMCP_BASE_URL: server base URL used in discovery metadata (e.g., https://your-domain)

    Notes:
      - If AUTH_ALLOWED_REDIRECT_URIS is set but empty (""), we pass an empty list,
        which allows all redirect URIs (not recommended for production).
    """

    # Production requirement: static Bearer token auth via MCP_API_KEY.
    # Copilot Studio can be configured to send `Authorization: Bearer <token>`.
    api_key = (os.getenv("MCP_API_KEY") or "").strip()
    if api_key:
        def _validate(token: str) -> bool:
            # Constant-time comparison.
            return bool(token) and hmac.compare_digest(token, api_key)

        # DebugTokenVerifier supports custom validation callables (sync/async).
        # We use it here for a simple opaque token check.
        return DebugTokenVerifier(
            validate=_validate,
            client_id="mcp-api-key",
            scopes=["api:access"],
        )  # type: ignore[return-value]

    if not _is_truthy(os.getenv("AUTH_ENABLED")):
        return None

    jwks_uri = os.getenv("AUTH_JWKS_URI")
    issuer = os.getenv("AUTH_ISSUER")
    audience = os.getenv("AUTH_AUDIENCE")

    missing = [name for name, val in {
        "AUTH_JWKS_URI": jwks_uri,
        "AUTH_ISSUER": issuer,
        "AUTH_AUDIENCE": audience,
    }.items() if not val]

    if missing:
        raise ValueError(
            "AUTH_ENABLED is true but required auth env vars are missing: " + ", ".join(missing)
        )

    authorization_servers_raw = os.getenv("AUTHORIZATION_SERVERS") or issuer
    authorization_servers = [AnyHttpUrl(url) for url in _split_csv(authorization_servers_raw)]

    allowed_redirect_raw = os.getenv("AUTH_ALLOWED_REDIRECT_URIS")
    allowed_client_redirect_uris: Optional[List[str]]
    if allowed_redirect_raw is None:
        allowed_client_redirect_uris = None
    else:
        allowed_client_redirect_uris = _split_csv(allowed_redirect_raw)

    token_verifier = JWTVerifier(
        jwks_uri=jwks_uri,
        issuer=issuer,
        audience=audience,
    )

    return RemoteAuthProvider(
        token_verifier=token_verifier,
        authorization_servers=authorization_servers,
        base_url=base_url,
        allowed_client_redirect_uris=allowed_client_redirect_uris,
    )
