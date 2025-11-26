#!/usr/bin/env python3
"""Simple KB metadata lint: ensures required fields and contacts exist."""
from __future__ import annotations

from pathlib import Path
from typing import List

import frontmatter

KB_ROOT = Path(__file__).resolve().parent.parent / "kb_repo" / "kb"
REQUIRED_FIELDS = ["id", "title", "category"]


def main() -> None:
    warnings: List[str] = []
    for path in KB_ROOT.rglob("*.md"):
        try:
            post = frontmatter.load(path)
        except Exception as exc:  # pragma: no cover - malformed file
            warnings.append(f"{path}: could not parse frontmatter ({exc})")
            continue
        metadata = post.metadata or {}
        missing = [field for field in REQUIRED_FIELDS if field not in metadata]
        if missing:
            warnings.append(f"{path}: missing metadata fields {missing}")
        contacts = metadata.get("contacts") or []
        if not contacts:
            warnings.append(f"{path}: no contacts defined")
    if warnings:
        print("KB lint warnings:")
        for warning in warnings:
            print("-", warning)
        raise SystemExit(1)
    print("KB lint passed: all files contain required metadata and contacts.")


if __name__ == "__main__":
    main()
