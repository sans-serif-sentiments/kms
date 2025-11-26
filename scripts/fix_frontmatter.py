#!/usr/bin/env python3
"""Auto-fix missing frontmatter for LangGraph markdown files.

Adds minimal required metadata (id/title/category/contacts) when absent, without
overwriting existing fields. Intended to keep ingestion from skipping new docs.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Tuple

import frontmatter

KB_LANGRAPH_ROOT = Path(__file__).resolve().parents[1] / "kb_repo" / "kb" / "langraph"
DEFAULT_CONTACT = {
    "name": "LangGraph Docs Steward",
    "email": "langgraph-docs@company.com",
    "notes": "Maintains LangGraph KB metadata and ingestion readiness.",
    "priority": 1,
}


def derive_id(path: Path) -> str:
    stem = path.stem
    slug = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").upper()
    return f"LG-{slug}"


def derive_title(post: frontmatter.Post, path: Path) -> str:
    # Prefer first H1 in content
    match = re.search(r"^#\\s+(.+)$", post.content, flags=re.MULTILINE)
    if match:
        return match.group(1).strip()
    # Fallback to filename
    return path.stem.replace("-", " ").replace("_", " ").title()


def ensure_metadata(post: frontmatter.Post, path: Path) -> Tuple[frontmatter.Post, bool]:
    changed = False
    meta: Dict[str, object] = dict(post.metadata or {})
    if "id" not in meta:
        meta["id"] = derive_id(path)
        changed = True
    if "title" not in meta:
        meta["title"] = derive_title(post, path)
        changed = True
    if "category" not in meta:
        meta["category"] = "langraph"
        changed = True
    contacts = meta.get("contacts") or []
    if not contacts:
        meta["contacts"] = [DEFAULT_CONTACT]
        changed = True
    post.metadata = meta
    return post, changed


def main() -> None:
    if not KB_LANGRAPH_ROOT.exists():
        print(f"LangGraph KB path not found: {KB_LANGRAPH_ROOT}")
        return

    fixed = 0
    scanned = 0
    for path in KB_LANGRAPH_ROOT.rglob("*.md"):
        scanned += 1
        try:
            post = frontmatter.load(path)
        except Exception as exc:  # pragma: no cover - malformed file
            print(f"Skipping {path}: cannot parse frontmatter ({exc})")
            continue
        post, changed = ensure_metadata(post, path)
        if changed:
            path.write_text(frontmatter.dumps(post), encoding="utf-8")
            fixed += 1
    print(f"Scanned {scanned} langraph files; updated {fixed}.")


if __name__ == "__main__":
    main()
