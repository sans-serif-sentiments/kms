"""Knowledge graph built from units, contacts, systems, and relations."""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple, Union

from app.kb.indexing import get_state_store
from app.kb.models import KnowledgeChunk, RetrievalChunk

LOGGER = logging.getLogger(__name__)

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
FUNCTION_TERMS = {
    "finance",
    "sales",
    "hr",
    "security",
    "product",
    "compliance",
    "it",
    "revops",
    "wellness",
    "wellbeing",
    "legal",
    "marketing",
    "communications",
    "comms",
    "customer",
    "trust",
    "support",
    "people",
    "talent",
    "operations",
    "ops",
    "enablement",
}


def tokenize(text: str) -> Set[str]:
    if not text:
        return set()
    return set(TOKEN_PATTERN.findall(text.lower()))


def normalize_tags(raw_tags: Optional[Union[str, List[str], Set[str], Tuple[str, ...]]]) -> List[str]:
    """Return lowercase tag strings regardless of source format."""

    if not raw_tags:
        return []
    tags: List[str] = []
    if isinstance(raw_tags, str):
        candidates = raw_tags.split(",")
    elif isinstance(raw_tags, (list, tuple, set)):
        candidates = raw_tags
    else:
        return []
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        cleaned = candidate.strip().lower()
        if cleaned:
            tags.append(cleaned)
    return tags


class KnowledgeGraph:
    """Aggregate structured metadata to boost retrieval & owner lookups."""

    def __init__(self):
        self.store = get_state_store()
        self.units: List[Dict[str, str]] = []
        self.units_by_id: Dict[str, Dict[str, str]] = {}
        self.tag_index: Dict[str, Set[str]] = defaultdict(set)
        self.system_index: Dict[str, Set[str]] = defaultdict(set)
        self.function_index: Dict[str, Set[str]] = defaultdict(set)
        self.contact_index: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        self.relations: Dict[str, List[str]] = defaultdict(list)
        self.contacts: List[Dict[str, str]] = []
        self.contacts_by_key: Dict[Tuple[str, str], Dict[str, str]] = {}
        self.unit_tags: Dict[str, Set[str]] = {}
        self._fingerprint: Dict[str, object] = {"chunks": 0, "last_indexed_at": None}
        self.refresh()

    def refresh(self) -> None:
        self.units = self.store.list_all_units()
        self.units_by_id = {unit["id"]: unit for unit in self.units}
        self.contacts = self.store.list_all_contacts()
        system_rows = self.store.list_all_systems()
        relation_rows = self.store.list_all_relations()

        self.tag_index.clear()
        self.system_index.clear()
        self.function_index.clear()
        self.contact_index.clear()
        self.relations.clear()
        self.contacts_by_key = {(contact["unit_id"], contact["name"]): contact for contact in self.contacts}
        self.unit_tags = {}

        for unit in self.units:
            tags = set(normalize_tags(unit.get("tags")))
            self.unit_tags[unit["id"]] = tags
            tag_blob = " ".join(tags)
            tokens = tokenize(tag_blob) | tokenize(unit.get("category", "")) | tokenize(unit.get("title", ""))
            summary_tokens = tokenize((unit.get("summary") or "")[:280])
            tokens |= summary_tokens
            for token in tokens:
                self.tag_index[token].add(unit["id"])
            for tag in tags:
                if tag in FUNCTION_TERMS:
                    self.function_index[tag].add(unit["id"])

        for row in system_rows:
            unit_id = row["unit_id"]
            if unit_id not in self.units_by_id:
                continue
            for token in tokenize(row.get("system_name", "")):
                self.system_index[token].add(unit_id)

        for contact in self.contacts:
            tokens = tokenize(contact.get("name", "")) | tokenize(contact.get("title", ""))
            if contact.get("email"):
                tokens |= tokenize(contact["email"].replace("@", " ").replace(".", " "))
            for token in tokens:
                self.contact_index[token].append(contact)

        for relation in relation_rows:
            self.relations[relation["unit_id"]].append(relation["related_unit_id"])
        self._fingerprint = self.store.get_ingest_fingerprint()

    def _ensure_fresh(self) -> None:
        current = self.store.get_ingest_fingerprint()
        if current != self._fingerprint:
            LOGGER.info("KnowledgeGraph detected new ingestion; refreshing metadata.")
            self.refresh()

    def search(self, query: str, top_n: int = 4) -> List[RetrievalChunk]:
        self._ensure_fresh()
        if not query.strip():
            return []
        tokens = tokenize(query)
        if not tokens:
            return []

        contact_chunks = self._match_contacts(tokens)
        results: List[RetrievalChunk] = []
        seen_units: Set[str] = set()

        # Prioritize contact surfaces if present
        max_contact = max(1, top_n // 2)
        for chunk in contact_chunks[:max_contact]:
            chunk.rank = len(results) + 1
            results.append(chunk)
            seen_units.add(chunk.chunk.knowledge_unit_id)
            if len(results) >= top_n:
                return results

        function_chunks = self._match_functions(tokens, seen_units)
        for chunk in function_chunks:
            chunk.rank = len(results) + 1
            results.append(chunk)
            if len(results) >= top_n:
                return results

        unit_chunks = self._match_units(tokens, seen_units)
        for chunk in unit_chunks:
            chunk.rank = len(results) + 1
            results.append(chunk)
            if len(results) >= top_n:
                break

        return results

    def _match_contacts(self, tokens: Set[str]) -> List[RetrievalChunk]:
        scores: Dict[Tuple[str, str], float] = defaultdict(float)
        for token in tokens:
            for contact in self.contact_index.get(token, []):
                key = (contact["unit_id"], contact["name"])
                scores[key] += 1.0
        ranked: List[RetrievalChunk] = []
        for key, score in sorted(scores.items(), key=lambda item: item[1], reverse=True):
            unit_id, name = key
            contact = self.contacts_by_key.get((unit_id, name))
            if not contact:
                continue
            ranked.append(self._contact_to_chunk(contact, score, len(ranked) + 1))
        return ranked

    def _match_units(self, tokens: Set[str], seen_units: Optional[Set[str]] = None) -> List[RetrievalChunk]:
        if seen_units is None:
            seen_units = set()
        scores: Dict[str, float] = defaultdict(float)
        for token in tokens:
            for unit_id in self.tag_index.get(token, set()):
                scores[unit_id] += 1.0
            for unit_id in self.system_index.get(token, set()):
                scores[unit_id] += 0.8
            for unit_id, unit in self.units_by_id.items():
                if token in tokenize(unit.get("id", "")):
                    scores[unit_id] += 0.5
                if token in self.unit_tags.get(unit_id, set()):
                    scores[unit_id] += 0.6
        # Propagate signal via related units
        for unit_id, base_score in list(scores.items()):
            for related in self.relations.get(unit_id, []):
                scores[related] += base_score * 0.3

        ranked_units: List[RetrievalChunk] = []
        for unit_id, score in sorted(scores.items(), key=lambda item: item[1], reverse=True):
            unit = self.units_by_id.get(unit_id)
            if not unit:
                continue
            if unit_id in seen_units:
                continue
            seen_units.add(unit_id)
            ranked_units.append(self._unit_to_chunk(unit, score, len(ranked_units) + 1))
        return ranked_units

    def _match_functions(self, tokens: Set[str], seen_units: Set[str]) -> List[RetrievalChunk]:
        matches: List[RetrievalChunk] = []
        for token in tokens:
            if token not in self.function_index:
                continue
            for unit_id in self.function_index[token]:
                if unit_id in seen_units:
                    continue
                unit = self.units_by_id.get(unit_id)
                if not unit:
                    continue
                seen_units.add(unit_id)
                matches.append(self._unit_to_chunk(unit, score=1.2, rank=len(matches) + 1))
        return matches

    def _unit_to_chunk(self, unit: Dict[str, str], score: float, rank: int) -> RetrievalChunk:
        text = unit.get("summary") or unit.get("title") or ""
        chunk = KnowledgeChunk(
            chunk_id=f"{unit['id']}:graph:{rank}",
            knowledge_unit_id=unit["id"],
            source_path=unit.get("source_path", ""),
            section_name="graph",
            text=text,
            metadata={
                "category": unit.get("category", ""),
                "tags": unit.get("tags", ""),
                "version": unit.get("version", ""),
                "updated_at": unit.get("updated_at") or "",
                "confidence": unit.get("confidence", ""),
                "section": "graph",
                "source_path": unit.get("source_path", ""),
                "knowledge_unit_id": unit["id"],
                "title": unit.get("title", ""),
            },
        )
        return RetrievalChunk(chunk=chunk, score=score, rank=rank, source="graph")

    def _contact_to_chunk(self, contact: Dict[str, str], score: float, rank: int) -> RetrievalChunk:
        unit = self.units_by_id.get(contact["unit_id"])
        unit_title = unit["title"] if unit else contact["unit_id"]
        lines = [f"{contact.get('name', 'Unknown contact')} – {contact.get('title', 'No title specified')}"]
        email = contact.get("email")
        slack = contact.get("slack")
        phone = contact.get("phone")
        notes = contact.get("notes")
        if email:
            lines.append(f"Email: {email}")
        if slack:
            lines.append(f"Slack: {slack}")
        if phone:
            lines.append(f"Phone: {phone}")
        if notes:
            lines.append(notes)
        text = "\n".join(lines)
        chunk = KnowledgeChunk(
            chunk_id=f"{contact['unit_id']}:contact:{rank}",
            knowledge_unit_id=contact["unit_id"],
            source_path=unit.get("source_path", "") if unit else "",
            section_name="contacts",
            text=text,
            metadata={
                "category": unit.get("category", "") if unit else "",
                "tags": unit.get("tags", "") if unit else "",
                "version": unit.get("version", "") if unit else "",
                "updated_at": (unit.get("updated_at") if unit and unit.get("updated_at") else ""),
                "confidence": unit.get("confidence", "") if unit else "",
                "section": "contacts",
                "source_path": unit.get("source_path", "") if unit else "",
                "knowledge_unit_id": contact["unit_id"],
                "title": unit_title,
                "contact_name": contact.get("name", "") or "",
                "contact_email": email or "",
                "contact_slack": slack or "",
                "contact_phone": phone or "",
            },
        )
        return RetrievalChunk(chunk=chunk, score=score, rank=rank, source="graph")


__all__ = ["KnowledgeGraph"]
