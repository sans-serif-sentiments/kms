"""Repo synchronisation helpers."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from git import Repo
from git.exc import GitCommandError

from app.core.config import get_settings

LOGGER = logging.getLogger(__name__)


class RepoSyncError(RuntimeError):
    """Raised when git pull cannot complete automatically."""


def git_pull() -> str:
    """Run `git pull` on the configured repository."""

    settings = get_settings()
    repo_path = settings.repo.repo_path
    repo = Repo(str(repo_path))
    origin = repo.remotes.origin
    LOGGER.info("Pulling latest changes for %s", repo_path)
    try:
        result = origin.pull(settings.repo.branch, ff_only=True)
    except GitCommandError as exc:  # pragma: no cover - requires divergent branches
        stderr = getattr(exc, "stderr", "") or ""
        hint = (
            "Git pull failed because the local kb_repo has diverged from origin. "
            "Run `cd kb_repo && git fetch origin && git rebase origin/main` (or resolve conflicts) before /sync."
        )
        if "rebase" in stderr.lower() or "divergent" in stderr.lower():
            hint = (
                "Git pull failed: repository has local commits. "
                "Resolve by running `cd kb_repo && git fetch origin && git rebase origin/main`, "
                "then re-run `make update-kb`."
            )
        LOGGER.error("git pull failed: %s", exc)
        raise RepoSyncError(hint) from exc
    return ",".join(ref.commit.hexsha[:7] for ref in result)


def list_markdown_files() -> List[Path]:
    """Return all markdown files under kb root."""

    settings = get_settings()
    kb_dir = settings.repo.repo_path / settings.repo.kb_root
    if not kb_dir.exists():
        LOGGER.warning("KB directory %s missing", kb_dir)
        return []
    return sorted([p for p in kb_dir.rglob("*.md") if p.is_file()])


__all__ = ["git_pull", "list_markdown_files", "RepoSyncError"]
