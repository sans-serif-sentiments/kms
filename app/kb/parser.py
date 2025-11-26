"""Markdown parser that converts YAML frontmatter files into KnowledgeUnit objects."""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import frontmatter

from app.core.config import get_settings
from app.kb.models import Confidence, Contact, KnowledgeChunk, KnowledgeUnit

LOGGER = logging.getLogger(__name__)
SECTION_PATTERN = re.compile(r"^(#+)\\s+(.+)$", re.MULTILINE)


def read_file_hash(path: Path) -> Tuple[str, str]:
    """Return file text and sha256 hash."""

    text = path.read_text(encoding="utf-8")
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_sections(body: str) -> Dict[str, str]:
    """Split markdown by headings and return named sections."""

    sections: Dict[str, str] = {}
    matches = list(SECTION_PATTERN.finditer(body))
    if not matches:
        sections["body"] = body.strip()
        return sections

    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        heading = match.group(2).strip().lower()
        key = heading.lower()
        sections[key] = body[start:end].strip()
    return sections


def derive_summary(sections: Dict[str, str], body: str) -> str:
    """Generate a short summary from sections or body."""

    candidates = [sections.get("summary"), sections.get("overview"), sections.get("body"), body]
    for candidate in candidates:
        if candidate:
            snippet = candidate.strip()
            return snippet[:280]
    return ""


def normalize_contacts(raw_contacts: Optional[object]) -> List[Contact]:
    """Convert frontmatter contact definitions into Contact models."""

    if not raw_contacts:
        return []
    items: List[Dict[str, object]] = []
    if isinstance(raw_contacts, dict):
        raw_list = [raw_contacts]
    elif isinstance(raw_contacts, list):
        raw_list = raw_contacts
    else:
        raw_list = [raw_contacts]
    for entry in raw_list:
        if isinstance(entry, Contact):
            items.append(entry.dict())
            continue
        if isinstance(entry, str):
            items.append({"name": entry})
            continue
        if isinstance(entry, dict):
            normalized = {key: value for key, value in entry.items()}
            if "name" not in normalized and "title" in normalized:
                normalized["name"] = str(normalized["title"])
            items.append(normalized)
    contacts: List[Contact] = []
    for data in items:
        try:
            contacts.append(Contact(**data))
        except Exception as exc:
            LOGGER.warning("Skipping malformed contact %s: %s", data, exc)
    return contacts


def parse_file(path: Path, source_repo: str) -> Optional[Tuple[KnowledgeUnit, str]]:
    """Parse markdown into KnowledgeUnit and return along with file hash."""

    settings = get_settings()
    text, file_hash = read_file_hash(path)
    post = frontmatter.loads(text)
    metadata = post.metadata
    missing = [key for key in ("id", "title", "category") if key not in metadata]
    if missing:
        LOGGER.warning("Skipping %s due to missing metadata: %s", path, missing)
        return None
    category = str(metadata["category"]).lower()
    if category not in settings.allowed_categories:
        LOGGER.warning("Skipping %s due to invalid category %s", path, category)
        return None
    confidence = metadata.get("confidence", "medium")
    if confidence not in settings.confidence_levels:
        LOGGER.warning("Normalising confidence %s to low for %s", confidence, path)
        confidence = "low"
    body = post.content.strip()
    sections = parse_sections(body)
    summary = metadata.get("summary") or derive_summary(sections, body)
    base_path = Path(source_repo)
    try:
        relative_path = str(path.relative_to(base_path))
    except ValueError:
        relative_path = str(path)
    contacts = normalize_contacts(metadata.get("contacts"))
    unit = KnowledgeUnit(
        id=str(metadata["id"]),
        title=str(metadata["title"]),
        category=category,
        tags=metadata.get("tags", []),
        version=str(metadata.get("version", "0.0.1")),
        source_repo=source_repo,
        source_path=relative_path,
        source_type=str(metadata.get("source_type", "markdown")),
        created_at=metadata.get("created_at"),
        updated_at=metadata.get("updated_at"),
        author=metadata.get("author"),
        confidence=confidence,
        summary=summary,
        body=body,
        sections=sections,
        contacts=contacts,
        related_units=metadata.get("related_units", []),
        systems=metadata.get("systems", []),
    )
    return unit, file_hash


def chunk_unit(unit: KnowledgeUnit, chunk_size: int = 800, overlap: int = 100) -> Dict[str, KnowledgeChunk]:
    """Create retrieval chunks from a KnowledgeUnit using section-aware chunking."""

    chunks: Dict[str, KnowledgeChunk] = {}
    for section_name, text in unit.sections.items():
        normalized = section_name.replace(" ", "_")
        if not text:
            continue
        start = 0
        idx = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            chunk_text = text[start:end]
            chunk_id = f"{unit.id}:{normalized}:{idx}"
            metadata = {
                "category": str(unit.category),
                "tags": ",".join(unit.tags),
                "version": unit.version,
                "updated_at": unit.updated_at or "",
                "confidence": str(unit.confidence),
                "section": section_name,
                "source_path": unit.source_path,
                "knowledge_unit_id": unit.id,
                "title": unit.title,
                "contacts": ";".join([contact.name for contact in unit.contacts if contact.name]),
                "systems": ",".join(unit.systems),
                "related_units": ",".join(unit.related_units),
            }
            chunks[chunk_id] = KnowledgeChunk(
                chunk_id=chunk_id,
                knowledge_unit_id=unit.id,
                source_path=unit.source_path,
                section_name=section_name,
                text=chunk_text,
                metadata=metadata,
            )
            idx += 1
            if end == len(text):
                break
            start = max(0, end - overlap)
    if not chunks:
        chunk_id = f"{unit.id}:body:0"
        chunks[chunk_id] = KnowledgeChunk(
            chunk_id=chunk_id,
            knowledge_unit_id=unit.id,
            source_path=unit.source_path,
            section_name="body",
            text=unit.body,
            metadata={
                "category": str(unit.category),
                "tags": ",".join(unit.tags),
                "version": unit.version,
                "updated_at": unit.updated_at or "",
                "confidence": str(unit.confidence),
                "section": "body",
                "source_path": unit.source_path,
                "knowledge_unit_id": unit.id,
                "title": unit.title,
                "contacts": ";".join([contact.name for contact in unit.contacts if contact.name]),
                "systems": ",".join(unit.systems),
                "related_units": ",".join(unit.related_units),
            },
        )
    return chunks


__all__ = ["parse_file", "chunk_unit"]
