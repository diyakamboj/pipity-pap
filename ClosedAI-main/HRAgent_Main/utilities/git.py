"""Minimal git cache helpers.

The ``HRAgent.sdk.git.cached_repo`` module was removed during the repository
cleanup. A few remaining code paths (plugin/skill fetching and the public
skills catalog) still need to clone or update a git repository into a local
cache directory. This module provides that small surface on top of the ``git``
CLI rather than restoring the full cached-repo abstraction.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


class GitCommandError(Exception):
    """Raised when a git command exits with a non-zero status."""

    def __init__(self, message: str, returncode: int = -1) -> None:
        super().__init__(message)
        self.returncode = returncode


class GitRepositoryError(Exception):
    """Raised when a directory is not a valid git repository."""


def _run_git(
    args: list[str],
    cwd: Path | None = None,
    check: bool = True,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a git command, returning the completed process."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
        timeout=timeout,
    )


def run_git_command(
    command: list[str],
    cwd: Path | str | None = None,
    timeout: int | None = None,
) -> str:
    """Run a git command list, returning its stdout.

    Raises:
        GitCommandError: If git exits with a non-zero status.
    """
    try:
        result = _run_git(command, cwd=Path(cwd) if cwd else None, timeout=timeout)
    except (subprocess.CalledProcessError, OSError) as exc:
        raise GitCommandError(str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise GitCommandError(f"git command timed out: {command}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or str(command)
        raise GitCommandError(detail, returncode=result.returncode)
    return result.stdout.strip()


def validate_git_repository(path: Path | str) -> None:
    """Raise :class:`GitRepositoryError` if ``path`` is not a git repository."""
    repo_root = Path(path).resolve()
    if not (repo_root / ".git").is_dir():
        try:
            run_git_command(["git", "rev-parse", "--git-dir"], repo_root)
        except GitCommandError as exc:
            raise GitRepositoryError(f"Not a git repository: {repo_root}") from exc


def _is_git_repo(path: Path) -> bool:
    return (path / ".git").is_dir()


def try_cached_clone_or_update(
    repo_url: str,
    repo_path: Path,
    ref: str | None = None,
    update: bool = True,
) -> bool:
    """Clone ``repo_url`` into ``repo_path`` (or update an existing clone).

    If the repository is not yet present it is cloned at ``ref`` (or the
    default branch). When ``update`` is True an existing clone is fetched and
    hard-reset to ``ref``. Returns ``True`` when ``repo_path`` holds the
    requested ref afterwards, ``False`` on any git error.
    """
    repo_path = Path(repo_path)
    try:
        if not _is_git_repo(repo_path):
            repo_path.parent.mkdir(parents=True, exist_ok=True)
            _run_git(["clone", "--no-checkout", repo_url, str(repo_path)])
        elif not update:
            return True

        _run_git(["fetch", "--all", "--tags"], cwd=repo_path)
        if ref:
            _run_git(
                ["checkout", "--force", ref, "--"], cwd=repo_path, check=False
            )
            _run_git(["reset", "--hard", f"origin/{ref}"], cwd=repo_path, check=False)
        else:
            _run_git(["checkout", "--force"], cwd=repo_path, check=False)
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


class GitHelper:
    """Small helper mirroring the removed ``GitHelper`` type.

    The remaining code only passes an instance around as an optional argument
    to fetch functions; the actual git operations are performed by
    :func:`try_cached_clone_or_update`.
    """

    def __init__(self, **kwargs: Any) -> None:
        self._kwargs = kwargs

    def clone_or_update(self, url: str, path: Path, ref: str | None = None) -> bool:
        """Clone or update ``url`` into ``path`` (see module function)."""
        return try_cached_clone_or_update(url, path, ref=ref, update=True)

    def get_current_branch(self, repo_path: Path | str) -> str | None:
        """Return the current branch name of a repository, or ``None``."""
        try:
            branch = run_git_command(["git", "branch", "--show-current"], repo_path)
        except GitCommandError:
            return None
        return branch or None
