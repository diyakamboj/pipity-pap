"""Backend-only OAuth configuration: one centralized file for every MCP.

Some OAuth providers (Google, Slack, GitHub) don't support dynamic client
registration, so authorizing against them requires a pre-registered
"application" -- a client_id/client_secret pair created once by whoever
deploys HRAgent, in that provider's developer console. These are *deployment*
secrets, not end-user credentials: the person clicking "Connect" in the MCP
setup popup should never see, enter, or need to know about them.

This module is the single place all of that lives: per-provider client
id/secret, and the shared local OAuth callback redirect_uri every provider
app must register (see ``redirect_uri`` below -- one fixed value is used for
every provider since only one OAuth job runs at a time; see
``runtime.server.mcp_router._supersede_active_oauth_jobs``). It is one JSON
file, not a .env, so the whole OAuth surface for every environment
(dev/staging/prod) lives in one clearly structured, versionable-by-copy place
instead of scattered across shell exports.

The file lives outside the git working tree by default (the same
``~/.HRAgent`` directory that already holds the settings-encryption secret
key -- see ``runtime.server.config._secret_key_path``), so there is no way to
accidentally commit real credentials. Its location can be overridden with
``OH_OAUTH_PROVIDERS_CONFIG_PATH`` for containerized deployments that mount
it from a secret volume, or to point at a different file per environment
(dev/staging/prod) without editing code.

File format (see ``config/oauth_providers.example.json`` for a template)::

    {
      "redirect_uri": "http://localhost:8765/callback",
      "providers": {
        "google": {"client_id": "...", "client_secret": "..."},
        "slack": {"client_id": "...", "client_secret": "..."},
        "github": {"client_id": "...", "client_secret": "..."}
      }
    }

Integrations opt into a provider entry by setting ``provider`` on their
``.mcp.json`` template's ``auth.authentication`` block (see
``MCPOAuthAuthentication.provider``). Providers with no entry here simply
fall back to dynamic client registration (Linear, Notion, Jira/Atlassian) or
report a clear "not configured" error instead of attempting a doomed DCR
call (Google, Slack, GitHub).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, SecretStr, ValidationError

from runtime.telemetry.logger import get_logger


logger = get_logger(__name__)

# Used only when the config file is missing or omits `redirect_uri` (e.g. a
# fresh checkout before an administrator has set one up), so the backend
# still starts and OAuth attempts fail with a clear "not configured" message
# instead of an import-time crash.
DEFAULT_OAUTH_REDIRECT_URI = "http://localhost:8765/callback"


class OAuthProviderCredentials(BaseModel):
    client_id: str
    client_secret: SecretStr | None = None


class _OAuthConfigFile(BaseModel):
    redirect_uri: str = DEFAULT_OAUTH_REDIRECT_URI
    providers: dict[str, OAuthProviderCredentials] = {}


def oauth_providers_config_path() -> Path:
    """Filesystem location of the OAuth configuration file.

    Mirrors ``runtime.server.config._secret_key_path``'s precedence
    (``OH_PERSISTENCE_DIR``, else ``~/.HRAgent``) so both secret files live
    in the same place by default, with a dedicated override for deployments
    that want to mount just this one from a secret store, or point at a
    different file per environment.
    """
    override = os.environ.get("OH_OAUTH_PROVIDERS_CONFIG_PATH")
    if override:
        return Path(override)
    env_dir = os.environ.get("OH_PERSISTENCE_DIR")
    base = Path(env_dir) if env_dir else Path.home() / ".HRAgent"
    user_path = base / "oauth_providers.json"
    if user_path.exists():
        return user_path
    repo_path = Path(__file__).resolve().parent.parent / "config" / "oauth_providers.json"
    if repo_path.exists():
        return repo_path
    return user_path


# Re-read whenever the file's mtime changes, so editing it takes effect
# without a server restart -- there's no other cache invalidation trigger
# for a file that lives outside anything else the app watches.
_cache = _OAuthConfigFile()
_cache_mtime: float | None = None
_warned_missing = False


def _load() -> _OAuthConfigFile:
    global _cache, _cache_mtime, _warned_missing

    path = oauth_providers_config_path()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        if not _warned_missing:
            logger.info(
                "No OAuth config at %s -- integrations requiring a "
                "pre-registered app (Google, Slack, GitHub) will report "
                "'not configured' until an administrator creates one. See "
                "config/oauth_providers.example.json.",
                path,
            )
            _warned_missing = True
        _cache, _cache_mtime = _OAuthConfigFile(), None
        return _cache

    _warned_missing = False
    if _cache_mtime == mtime:
        return _cache

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Failed to parse OAuth config at %s", path, exc_info=True)
        _cache, _cache_mtime = _OAuthConfigFile(), mtime
        return _cache

    if not isinstance(raw, dict):
        logger.warning("OAuth config at %s must be a JSON object", path)
        _cache, _cache_mtime = _OAuthConfigFile(), mtime
        return _cache

    providers: dict[str, OAuthProviderCredentials] = {}
    for name, entry in raw.get("providers", {}).items():
        if name.startswith("_"):
            continue  # convention for a "_comment" style annotation key
        try:
            providers[name] = OAuthProviderCredentials.model_validate(entry)
        except ValidationError:
            logger.warning(
                "Skipping invalid OAuth provider config entry %r in %s",
                name,
                path,
                exc_info=True,
            )

    redirect_uri = raw.get("redirect_uri") or DEFAULT_OAUTH_REDIRECT_URI

    _cache = _OAuthConfigFile(redirect_uri=redirect_uri, providers=providers)
    _cache_mtime = mtime
    return _cache


def get_oauth_provider_credentials(provider: str) -> OAuthProviderCredentials | None:
    """The configured client_id/secret for ``provider``, or None if unset."""
    return _load().providers.get(provider)


def configured_oauth_providers() -> frozenset[str]:
    """Names of every provider with valid credentials configured."""
    return frozenset(_load().providers.keys())


def get_oauth_redirect_uri() -> str:
    """The local callback URL every OAuth job redirects back to.

    One shared value for every provider (see the module docstring) --
    provider apps must register this exact URL. Falls back to
    ``DEFAULT_OAUTH_REDIRECT_URI`` if the config file doesn't set one.
    """
    return _load().redirect_uri


def get_oauth_callback_port() -> int:
    """The port parsed out of ``get_oauth_redirect_uri()``.

    The callback is always a local loopback HTTP listener (see
    ``fastmcp.client.oauth_callback``), so only the port from the configured
    redirect_uri is actually used to bind it.
    """
    parsed = urlparse(get_oauth_redirect_uri())
    return parsed.port or urlparse(DEFAULT_OAUTH_REDIRECT_URI).port  # type: ignore[return-value]
