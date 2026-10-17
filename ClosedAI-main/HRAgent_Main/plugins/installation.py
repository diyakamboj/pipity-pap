"""Generic installed-extension manager.

The ``HRAgent.sdk.extensions.installation`` module was removed during the
repository cleanup. Plugin and skill installation still expose a public API
through :mod:`plugins.installed` and :mod:`skills.installed`, so this module
preserves the small generic manager those modules delegate to.

Installations live in a single directory, one subdirectory per extension, each
carrying a ``.metadata.json`` file describing the install (source, resolved
ref, enablement, install time). The manager is generic over the payload type
via an :class:`InstallationInterface`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel, Field

from utilities.git import try_cached_clone_or_update

T = TypeVar("T")

# Metadata filename written inside each installed-extension directory.
METADATA_FILENAME = ".metadata.json"


class InstallationInfo(BaseModel):
    """Metadata describing a single installed extension."""

    name: str = Field(..., description="Name of the installed extension.")
    version: str | None = Field(default=None, description="Extension version.")
    description: str | None = Field(default=None, description="Extension description.")
    enabled: bool = Field(default=True, description="Whether the extension is enabled.")
    source: str = Field(default="", description="Original source the extension came from.")
    ref: str | None = Field(default=None, description="Requested ref (branch/tag/commit).")
    resolved_ref: str | None = Field(
        default=None, description="Commit SHA actually checked out, if known."
    )
    repo_path: str | None = Field(
        default=None, description="Subdirectory within the source repository."
    )
    installed_at: float | None = Field(default=None, description="Install epoch time.")
    install_path: str = Field(default="", description="Path to the installed directory.")


class InstallationInterface(Protocol[T]):
    """Interface the manager uses to load a payload from an installed directory."""

    @staticmethod
    def load_from_dir(extension_dir: Path) -> T:
        """Load the typed extension from its installed directory."""
        ...


def _is_git_source(source: str) -> bool:
    return (
        source.startswith(("http://", "https://", "git@", "ssh://", "github:", "git+"))
        or source.endswith(".git")
    )


def _clone_git_source(
    source: str,
    ref: str | None,
    repo_path: str | None,
    cache_dir: Path,
) -> Path | None:
    """Clone/update a git source into ``cache_dir`` and return the resolved dir."""
    url = source
    if source.startswith("github:"):
        url = f"https://github.com/{source.split(':', 1)[1]}.git"
    repo_dir = cache_dir / "repos" / _safe_dirname(url)
    if not try_cached_clone_or_update(url, repo_dir, ref=ref, update=True):
        return None
    if repo_path:
        sub = repo_dir / repo_path
        return sub if sub.is_dir() else None
    return repo_dir


def _safe_dirname(url: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in url)[:120]


class InstallationManager(Generic[T]):
    """Manage extensions installed under a single directory.

    Args:
        installation_dir: Directory holding installed extensions.
        installation_interface: Loads typed payloads from installed directories.
    """

    def __init__(
        self,
        installation_dir: Path,
        installation_interface: InstallationInterface[T],
    ) -> None:
        self._installation_dir = Path(installation_dir)
        self._installation_interface = installation_interface

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _metadata_path(self, name: str) -> Path:
        return self._installation_dir / name / METADATA_FILENAME

    def _read_metadata(self, name: str) -> InstallationInfo | None:
        meta_path = self._metadata_path(name)
        if not meta_path.is_file():
            return None
        try:
            return InstallationInfo.model_validate_json(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError):
            return None

    def _write_metadata(self, info: InstallationInfo) -> None:
        meta_path = self._metadata_path(info.name)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(info.model_dump_json(indent=2), encoding="utf-8")

    def _load_payload(self, name: str) -> T | None:
        install_dir = self._installation_dir / name
        if not install_dir.is_dir():
            return None
        try:
            return self._installation_interface.load_from_dir(install_dir)
        except (FileNotFoundError, ValueError):
            return None

    def _copy_source(self, source_dir: Path, name: str) -> Path:
        """Copy ``source_dir`` into the install directory under ``name``."""
        target = self._installation_dir / name
        if target.is_dir():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_dir, target)
        return target

    def _resolve_source_dir(
        self, source: str, ref: str | None, repo_path: str | None
    ) -> Path | None:
        """Resolve ``source`` to a local directory (cloning git when needed)."""
        local = Path(source).expanduser()
        if local.is_dir():
            return local.resolve()
        if _is_git_source(source):
            return _clone_git_source(
                source, ref, repo_path, self._installation_dir.parent
            )
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def install(
        self,
        source: str,
        ref: str | None = None,
        repo_path: str | None = None,
        force: bool = False,
    ) -> InstallationInfo:
        """Install an extension from ``source`` and return its metadata."""
        source_dir = self._resolve_source_dir(source, ref, repo_path)
        if source_dir is None:
            raise ValueError(f"Unresolvable source: {source!r}")

        payload = self._installation_interface.load_from_dir(source_dir)
        name = getattr(payload, "name", None) or source_dir.name
        existing = self._read_metadata(name)
        if existing is not None and not force:
            # FileExistsError (not ValueError) so both routers map this to a 409
            # "already installed" and the skills bulk-install catch fires.
            raise FileExistsError(
                f"Extension {name!r} is already installed; pass force=True to overwrite."
            )

        install_path = self._copy_source(source_dir, name)
        info = InstallationInfo(
            name=name,
            version=getattr(payload, "version", None),
            description=getattr(payload, "description", None),
            enabled=True,
            source=source,
            ref=ref,
            resolved_ref=None,
            repo_path=repo_path,
            installed_at=time.time(),
            install_path=str(install_path),
        )
        self._write_metadata(info)
        return info

    def uninstall(self, name: str) -> bool:
        """Remove an installed extension by name. Returns False if not present."""
        install_dir = self._installation_dir / name
        if not install_dir.is_dir():
            return False
        shutil.rmtree(install_dir)
        return True

    def enable(self, name: str) -> bool:
        """Mark an installed extension as enabled. Returns False if not present."""
        info = self._read_metadata(name)
        if info is None or info.enabled:
            return info is not None
        self._write_metadata(info.model_copy(update={"enabled": True}))
        return True

    def disable(self, name: str) -> bool:
        """Mark an installed extension as disabled. Returns False if not present."""
        info = self._read_metadata(name)
        if info is None or not info.enabled:
            return info is not None
        self._write_metadata(info.model_copy(update={"enabled": False}))
        return True

    def list_installed(self) -> list[InstallationInfo]:
        """List metadata for all installed extensions, self-healing from disk."""
        if not self._installation_dir.is_dir():
            return []
        infos: list[InstallationInfo] = []
        for child in sorted(self._installation_dir.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            info = self._read_metadata(child.name)
            if info is None:
                # Dir without metadata — reconstruct a minimal record so the
                # entry is still visible and can be uninstalled.
                info = InstallationInfo(
                    name=child.name,
                    enabled=True,
                    source="",
                    installed_at=None,
                    install_path=str(child),
                )
                self._write_metadata(info)
            infos.append(info)
        return infos

    def load_installed(self) -> list[T]:
        """Load enabled installed extensions as typed payloads."""
        loaded: list[T] = []
        for info in self.list_installed():
            if not info.enabled:
                continue
            payload = self._load_payload(info.name)
            if payload is not None:
                loaded.append(payload)
        return loaded

    def get(self, name: str) -> InstallationInfo | None:
        """Return metadata for an installed extension, or None if absent."""
        return self._read_metadata(name)

    def update(self, name: str) -> InstallationInfo | None:
        """Re-fetch the source of an installed extension. Returns updated info."""
        info = self._read_metadata(name)
        if info is None:
            return None
        source_dir = self._resolve_source_dir(info.source, info.ref, info.repo_path)
        if source_dir is None:
            return None
        payload = self._load_payload(name)
        install_path = self._copy_source(source_dir, name)
        updated = info.model_copy(
            update={
                "version": getattr(payload, "version", None),
                "description": getattr(payload, "description", None),
                "resolved_ref": None,
                "installed_at": time.time(),
                "install_path": str(install_path),
            }
        )
        self._write_metadata(updated)
        return updated
