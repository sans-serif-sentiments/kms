"""Ingestion pipeline: scan repo, parse markdown, chunk, and index."""
from __future__ import annotations

import logging
from typing import Dict, List, Set

from app.core.config import get_settings
from app.kb import parser, repo_sync
from app.kb.indexing import get_state_store, get_vector_index
from app.kb.models import KnowledgeUnit

LOGGER = logging.getLogger(__name__)


def ingest_kb(force: bool = False) -> Dict[str, object]:
    """Run ingestion and return summary statistics."""

    settings = get_settings()
    files = repo_sync.list_markdown_files()
    state_store = get_state_store()
    vector_index = get_vector_index()
    counters = {"indexed": 0, "skipped": 0, "chunks": 0, "deleted": 0}
    units: List[KnowledgeUnit] = []
    processed_paths: Set[str] = set()
    for path in files:
        parsed = parser.parse_file(path, str(settings.repo.repo_path))
        if not parsed:
            counters["skipped"] += 1
            continue
        unit, file_hash = parsed
        processed_paths.add(unit.source_path)
        stored_hash = state_store.get_file_hash(unit.source_path)
        if not force and stored_hash == file_hash:
            counters["skipped"] += 1
            continue
        chunks = parser.chunk_unit(unit, settings.index.chunk_size, settings.index.chunk_overlap)
        state_store.upsert_chunks(chunks.values())
        state_store.upsert_unit(unit)
        state_store.sync_contacts(unit)
        state_store.sync_relations(unit)
        state_store.sync_systems(unit)
        vector_index.upsert(chunks.values())
        state_store.update_file(unit.source_path, file_hash)
        counters["indexed"] += 1
        counters["chunks"] += len(chunks)
        units.append(unit)
        LOGGER.info("Indexed %s with %d chunks", unit.source_path, len(chunks))
    removed_paths = set(state_store.list_known_files()) - processed_paths
    if removed_paths:
        LOGGER.info("Pruning %d files removed from kb_repo", len(removed_paths))
        for source_path in sorted(removed_paths):
            unit_ids = state_store.get_unit_ids_for_source(source_path)
            for unit_id in unit_ids:
                chunk_ids = state_store.list_chunk_ids_for_unit(unit_id)
                vector_index.delete_chunks(chunk_ids)
                state_store.delete_unit(unit_id)
                counters["deleted"] += 1
            state_store.delete_file_record(source_path)
    if removed_paths:
        LOGGER.info("Removed %d stale units from index", counters["deleted"])
    LOGGER.info(
        "Ingestion complete: indexed=%d skipped=%d deleted=%d chunks=%d",
        counters["indexed"],
        counters["skipped"],
        counters["deleted"],
        counters["chunks"],
    )
    return {"summary": counters, "units": units}


__all__ = ["ingest_kb"]
