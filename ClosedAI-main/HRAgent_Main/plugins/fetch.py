"""Plugin fetching utilities for remote plugin sources.

Local paths are returned as-is; git sources (URLs or ``github:`` shorthand)
are cloned/updated into a cache directory via :mod:`utilities.git`.
"""

from __future__ import annotations

from pathlib import Path

from utilities.git import GitHelper, try_cached_clone_or_update


DEFAULT_CACHE_DIR = Path.home() / ".HRAgent" / "cache" / "plugins"


class PluginFetchError(Exception):
    """Raised when fetching a plugin fails."""


def _is_git_source(source: str) -> bool:
    return (
        source.startswith(("http://", "https://", "git@", "ssh://", "github:", "git+"))
        or source.endswith(".git")
    )


def _git_url(source: str) -> str:
    if source.startswith("github:"):
        return f"https://github.com/{source.split(':', 1)[1]}.git"
    return source


def _safe_dirname(url: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in url)[:120]


def fetch_plugin(
    source: str,
    cache_dir: Path | None = None,
    ref: str | None = None,
    update: bool = True,
    repo_path: str | None = None,
    git_helper: GitHelper | None = None,
) -> Path:
    """Fetch a plugin from a remote source and return the local cached path.

    Args:
        source: Plugin source - can be:
            - Any git URL (GitHub, GitLab, Bitbucket, Codeberg, self-hosted, etc.)
              e.g., "https://gitlab.com/org/repo", "git@bitbucket.org:team/repo.git"
            - "github:owner/repo" - GitHub shorthand (convenience syntax)
            - "/local/path" - Local path (returned as-is)
        cache_dir: Directory for caching. Defaults to ~/.HRAgent/cache/plugins/
        ref: Optional branch, tag, or commit to checkout.
        update: If True and cache exists, update it. If False, use cached version as-is.
        repo_path: Subdirectory path within the git repository
            (e.g., 'plugins/my-plugin' for monorepos). Only relevant for git
            sources, not local paths. If specified, the returned path will
            point to this subdirectory instead of the repository root.
        git_helper: GitHelper instance (for testing). Defaults to global instance.

    Returns:
        Path to the local plugin directory (ready for Plugin.load()).
        If repo_path is specified, returns the path to that subdirectory.

    Raises:
        PluginFetchError: If fetching fails or repo_path doesn't exist.
    """
    path, _ = fetch_plugin_with_resolution(
        source=source,
        cache_dir=cache_dir,
        ref=ref,
        update=update,
        repo_path=repo_path,
        git_helper=git_helper,
    )
    return path


def fetch_plugin_with_resolution(
    source: str,
    cache_dir: Path | None = None,
    ref: str | None = None,
    update: bool = True,
    repo_path: str | None = None,
    git_helper: GitHelper | None = None,
) -> tuple[Path, str | None]:
    """Fetch a plugin and return both the path and the resolved commit SHA.

    This is similar to fetch_plugin() but also returns the actual commit SHA
    that was checked out. This is useful for persistence - storing the resolved
    SHA ensures that conversation resume gets exactly the same plugin version.

    Args:
        source: Plugin source (see fetch_plugin for formats).
        cache_dir: Directory for caching. Defaults to ~/.HRAgent/cache/plugins/
        ref: Optional branch, tag, or commit to checkout.
        update: If True and cache exists, update it. If False, use cached version as-is.
        repo_path: Subdirectory path within the git repository.
        git_helper: GitHelper instance (for testing). Defaults to global instance.

    Returns:
        Tuple of (path, resolved_ref) where:
        - path: Path to the local plugin directory
        - resolved_ref: Commit SHA that was checked out (None for local sources)

    Raises:
        PluginFetchError: If fetching fails or repo_path doesn't exist.
    """
    resolved_cache_dir = cache_dir if cache_dir is not None else DEFAULT_CACHE_DIR

    # Local paths are returned as-is.
    local = Path(source).expanduser()
    if local.is_dir():
        return local.resolve(), None
    if source.startswith("file://"):
        return Path(source[len("file://") :]).resolve(), None

    if _is_git_source(source):
        url = _git_url(source)
        repo_dir = resolved_cache_dir / "repos" / _safe_dirname(url)
        cloned = try_cached_clone_or_update(url, repo_dir, ref=ref, update=update)
        if not cloned:
            raise PluginFetchError(f"Failed to fetch plugin from {source}")
        target = (repo_dir / repo_path) if repo_path else repo_dir
        if not target.is_dir():
            raise PluginFetchError(
                f"Plugin path not found in repository: {repo_path!r}"
            )
        return target.resolve(), None

    raise PluginFetchError(f"Unsupported plugin source: {source!r}")
