"""Minimal marketplace models and registry.

The ``HRAgent.sdk.marketplace`` package was removed during the repository
cleanup. Marketplace support (loading plugins/skills registered by a source
repository) is still wired into conversation loading and the server catalogs,
so this module preserves the small model + registry surface those paths use.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from utilities.git import try_cached_clone_or_update
from utilities.path import to_posix_path


class MarketplaceNotFoundError(Exception):
    """Raised when a named marketplace cannot be found or loaded."""


class PluginNotFoundError(Exception):
    """Raised when a requested plugin cannot be found in a marketplace."""


class PluginResolutionError(Exception):
    """Raised when a plugin source cannot be resolved."""

# Locations, in priority order, where a marketplace manifest may live inside a
# repository clone.
_MARKETPLACE_MANIFEST_CANDIDATES = (
    "marketplaces/default.json",
    ".plugin/marketplace.json",
    "marketplace.json",
)

_DEFAULT_MARKETPLACE_CACHE = Path.home() / ".HRAgent" / "cache" / "marketplaces"


class MarketplaceEntrySource(BaseModel):
    """Structured source for a marketplace plugin/skill entry."""

    source: str = Field(..., description="Repository URL or shorthand.")
    ref: str | None = Field(default=None, description="Branch/tag/commit to check out.")
    path: str | None = Field(default=None, description="Subpath within the repository.")


class MarketplacePlugin(BaseModel):
    """A single plugin advertised by a marketplace manifest."""

    name: str
    source: str | MarketplaceEntrySource
    description: str | None = None


class MarketplaceSkill(BaseModel):
    """A single skill advertised by a marketplace manifest."""

    name: str
    source: str | MarketplaceEntrySource
    description: str | None = None


class MarketplaceIntegration(BaseModel):
    """A single MCP integration advertised by a marketplace manifest.

    Integrations follow the plugin installation model: each one is a normal
    plugin directory (``plugin.json`` + ``.mcp.json``) whose ``.mcp.json``
    registers external MCP servers. ``category``/``authentication``/``tools``
    mirror the plugin manifest fields so the catalog UI can render them without
    reading the plugin directory itself.
    """

    name: str
    source: str | MarketplaceEntrySource
    description: str | None = None
    category: str | None = Field(
        default=None, description="Marketplace category, e.g. 'Communication'."
    )
    authentication: str | None = Field(
        default=None, description="Auth method label, e.g. 'OAuth 2.0' / 'API Key'."
    )
    tools: list[str] = Field(
        default_factory=list, description="Tool names exposed by the integration."
    )
    mcp: bool = Field(default=True, description="True when this is an MCP integration.")
    setup: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Dynamic setup schema (auth method + fields) for the UI form. "
            "Loaded from the integration's plugin.json at catalog-build time."
        ),
    )
    servers: dict[str, Any] | None = Field(
        default=None,
        description="The integration's .mcp.json 'mcpServers' map, loaded from its directory.",
    )


class Marketplace(BaseModel):
    """A marketplace manifest (``marketplaces/default.json`` or similar)."""

    path: str | None = Field(
        default=None, description="Local path to the marketplace repository clone."
    )
    plugins: list[MarketplacePlugin] = Field(default_factory=list)
    skills: list[MarketplaceSkill] = Field(default_factory=list)
    integrations: list[MarketplaceIntegration] = Field(
        default_factory=list,
        description="MCP integrations advertised by this marketplace.",
    )

    @classmethod
    def load(cls, repo_path: Path) -> "Marketplace":
        """Load the marketplace manifest found under ``repo_path``.

        Raises:
            FileNotFoundError: If no marketplace manifest exists under ``repo_path``.
            ValueError: If the manifest is not valid JSON.
        """
        repo_path = Path(repo_path)
        for candidate in _MARKETPLACE_MANIFEST_CANDIDATES:
            manifest_file = repo_path / candidate
            if manifest_file.is_file():
                data = json.loads(manifest_file.read_text(encoding="utf-8"))
                return cls.model_validate({**data, "path": to_posix_path(repo_path)})
        raise FileNotFoundError(
            f"No marketplace manifest found under {repo_path} "
            f"(looked for {', '.join(_MARKETPLACE_MANIFEST_CANDIDATES)})"
        )

    def resolve_plugin_source(self, entry: MarketplacePlugin) -> tuple[str, str | None, str | None]:
        """Resolve a plugin entry to attachable ``(source, ref, repo_path)``.

        Relative string sources are rewritten to absolute paths inside the
        marketplace clone; structured sources keep their components.
        """
        return self._resolve_entry_source(entry)

    def resolve_skill_source(self, entry: MarketplaceSkill) -> tuple[str, str | None, str | None]:
        """Resolve a skill entry to ``(source, ref, repo_path)``."""
        return self._resolve_entry_source(entry)

    def resolve_integration_source(self, entry: MarketplaceIntegration) -> tuple[str, str | None, str | None]:
        """Resolve an integration entry to ``(source, ref, repo_path)``.

        Relative string sources (e.g. ``./integrations/gmail``) are rewritten
        to absolute paths inside the marketplace clone, so they flow through
        ``InstallationManager`` unchanged.
        """
        return self._resolve_entry_source(entry)

    def load_integration_contents(
        self, entry: MarketplaceIntegration
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Load an integration's setup schema and .mcp.json servers.

        Reads ``plugin.json`` (``setup``) and ``.mcp.json`` (``mcpServers``)
        from the integration's resolved local directory. Returns
        ``(setup, servers)``, both None when the integration does not resolve
        to a local directory or the files are missing.
        """
        try:
            source, _, _ = self.resolve_integration_source(entry)
        except Exception:  # noqa: BLE001 — missing dir is a soft failure
            return None, None
        base = Path(source)
        if not base.is_dir():
            return None, None

        setup: dict[str, Any] | None = None
        manifest = base / "plugin.json"
        if manifest.is_file():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                setup = data.get("setup") if isinstance(data, dict) else None
            except Exception:  # noqa: BLE001 — malformed manifest, keep going
                setup = None

        servers: dict[str, Any] | None = None
        mcp_file = base / ".mcp.json"
        if mcp_file.is_file():
            try:
                data = json.loads(mcp_file.read_text(encoding="utf-8"))
                servers = data.get("mcpServers") if isinstance(data, dict) else None
            except Exception:  # noqa: BLE001 — malformed .mcp.json, keep going
                servers = None
        return setup, servers

    def _resolve_entry_source(self, entry: Any) -> tuple[str, str | None, str | None]:
        raw = entry.source
        if isinstance(raw, str):
            if self.path and (raw.startswith(("./", "../")) or Path(raw).is_absolute()):
                return (str((Path(self.path) / raw).resolve()), None, None)
            return (raw, None, None)
        return (raw.source, raw.ref, raw.path)


class MarketplaceRegistration(BaseModel):
    """A named registration of a marketplace source repository."""

    name: str
    source: str
    ref: str | None = None
    auto_load: bool | list[str] = Field(
        default=False,
        description=(
            "True to auto-load everything, or a list of plugin names to "
            "auto-load. False (default) auto-loads nothing."
        ),
    )
    marketplace_path: str | None = Field(
        default=None,
        description="Relative path of the marketplace manifest within the source.",
    )

    def auto_loads_plugin(self, name: str) -> bool:
        """Whether this registration auto-loads the named plugin."""
        return self._auto_loads(name)

    def auto_loads_skill(self, name: str) -> bool:
        """Whether this registration auto-loads the named skill."""
        return self._auto_loads(name)

    def _auto_loads(self, name: str) -> bool:
        if self.auto_load is True:
            return True
        if isinstance(self.auto_load, list):
            return name in self.auto_load
        return False


class MarketplaceRegistry:
    """Registry over a list of :class:`MarketplaceRegistration` instances."""

    def __init__(self, registrations: list[MarketplaceRegistration]) -> None:
        self.registrations = list(registrations)

    def get_auto_load_registrations(self) -> list[MarketplaceRegistration]:
        """Registrations that auto-load plugins/skills."""
        return [r for r in self.registrations if r.auto_load]

    def get_marketplace(self, name: str) -> tuple[Marketplace, Path]:
        """Clone/update the named registration's repo and load its manifest.

        Returns:
            A ``(marketplace, marketplace_path)`` pair where ``marketplace_path``
            is the local repository clone.

        Raises:
            KeyError: If no registration matches ``name``.
            FileNotFoundError: If the source cannot be cloned or has no manifest.
            ValueError: If the manifest is invalid.
        """
        registration = next(
            (r for r in self.registrations if r.name == name), None
        )
        if registration is None:
            raise KeyError(f"No marketplace registered with name {name!r}")

        cache_dir = _DEFAULT_MARKETPLACE_CACHE / _safe_dirname(registration.name)
        repo_path = cache_dir / "repo"
        if not try_cached_clone_or_update(
            registration.source, repo_path, ref=registration.ref, update=True
        ):
            raise FileNotFoundError(
                f"Failed to clone marketplace {name!r} from {registration.source}"
            )

        if registration.marketplace_path:
            manifest_file = repo_path / registration.marketplace_path
            if not manifest_file.is_file():
                raise FileNotFoundError(
                    f"Marketplace manifest not found: {manifest_file}"
                )
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
            marketplace = Marketplace.model_validate(
                {**data, "path": to_posix_path(repo_path)}
            )
            return marketplace, repo_path

        return Marketplace.load(repo_path), repo_path


def _safe_dirname(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name)[:80]
