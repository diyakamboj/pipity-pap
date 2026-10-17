"""Skill fetching utilities for AgentSkills sources.

Local paths are returned as-is; git sources (URLs or ``github:`` shorthand)
are cloned/updated into a cache directory via :mod:`utilities.git`.
"""

from __future__ import annotations

from pathlib import Path

from utilities.git import GitHelper, try_cached_clone_or_update


DEFAULT_CACHE_DIR = Path.home() / ".HRAgent" / "cache" / "skills"


class SkillFetchError(Exception):
    """Raised when fetching a skill fails."""


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


def fetch_skill(
    source: str,
    cache_dir: Path | None = None,
    ref: str | None = None,
    update: bool = True,
    repo_path: str | None = None,
    git_helper: GitHelper | None = None,
) -> Path:
    """Fetch a skill from a source and return the local path.

    Args:
        source: Skill source - git URL, GitHub shorthand, or local path.
        cache_dir: Directory for caching. Defaults to ~/.HRAgent/cache/skills/.
        ref: Optional branch, tag, or commit to checkout.
        update: If True and cache exists, update it.
        repo_path: Subdirectory path within the repository.
        git_helper: GitHelper instance (for testing).

    Returns:
        Path to the local skill directory.
    """
    path, _ = fetch_skill_with_resolution(
        source=source,
        cache_dir=cache_dir,
        ref=ref,
        update=update,
        repo_path=repo_path,
        git_helper=git_helper,
    )
    return path


def fetch_skill_with_resolution(
    source: str,
    cache_dir: Path | None = None,
    ref: str | None = None,
    update: bool = True,
    repo_path: str | None = None,
    git_helper: GitHelper | None = None,
) -> tuple[Path, str | None]:
    """Fetch a skill and return both the path and resolved commit SHA.

    Args:
        source: Skill source (git URL, GitHub shorthand, or local path).
        cache_dir: Directory for caching. Defaults to ~/.HRAgent/cache/skills/.
        ref: Optional branch, tag, or commit to checkout.
        update: If True and cache exists, update it.
        repo_path: Subdirectory path within the repository.
        git_helper: GitHelper instance (for testing).

    Returns:
        Tuple of (path, resolved_ref) where resolved_ref is the commit SHA for git
        sources and None for local paths.

    Raises:
        SkillFetchError: If fetching the skill fails.
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
            raise SkillFetchError(f"Failed to fetch skill from {source}")
        target = (repo_dir / repo_path) if repo_path else repo_dir
        if not target.is_dir():
            raise SkillFetchError(f"Skill path not found in repository: {repo_path!r}")
        return target.resolve(), None

    raise SkillFetchError(f"Unsupported skill source: {source!r}")
