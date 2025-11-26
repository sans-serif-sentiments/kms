"""Data models for knowledge units, chunks, and retrieval results."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class Category(str, Enum):
    concept = "concept"
    process = "process"
    policy = "policy"
    glossary = "glossary"
    faq = "faq"
    decision = "decision"
    metric = "metric"
    pattern = "pattern"
    langraph = "langraph"


class Confidence(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Contact(BaseModel):
    """Structured point-of-contact metadata surfaced in graph + responses."""

    name: str
    title: Optional[str] = None
    email: Optional[str] = None
    slack: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    priority: Optional[int] = Field(default=None, description="Lower numbers rank higher")


class KnowledgeUnit(BaseModel):
    """Represents a parsed markdown file with structured metadata."""

    id: str
    title: str
    category: Category
    tags: List[str] = Field(default_factory=list)
    version: str = "0.0.1"
    source_repo: str
    source_path: str
    source_type: str = "markdown"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    author: Optional[str] = None
    confidence: Confidence = Confidence.medium
    summary: Optional[str] = None
    body: str
    sections: Dict[str, str] = Field(default_factory=dict)
    contacts: List[Contact] = Field(default_factory=list)
    related_units: List[str] = Field(default_factory=list)
    systems: List[str] = Field(default_factory=list)

    @validator("tags", pre=True)
    def ensure_list(cls, value: Optional[List[str]]):  # type: ignore[override]
        if value is None:
            return []
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    @validator("created_at", "updated_at", pre=True)
    def normalize_datetime(cls, value: Optional[str]):  # type: ignore[override]
        if value in (None, ""):
            return None
        try:
            # Accept ISO or plain date
            parsed = datetime.fromisoformat(str(value))
            return parsed.isoformat()
        except ValueError:
            return str(value)

    @validator("related_units", "systems", pre=True)
    def ensure_str_list(cls, value):  # type: ignore[override]
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value


class KnowledgeChunk(BaseModel):
    """Atomic retrieval unit derived from a KnowledgeUnit."""

    chunk_id: str
    knowledge_unit_id: str
    source_path: str
    section_name: str
    text: str
    metadata: Dict[str, str]


class RetrievalChunk(BaseModel):
    """Chunk plus retrieval score metadata."""

    chunk: KnowledgeChunk
    score: float
    rank: int
    source: str


class RetrievalResult(BaseModel):
    """Result returned by the hybrid retrieval stage."""

    query: str
    selected_chunks: List[RetrievalChunk]
    debug: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)


__all__ = [
    "KnowledgeUnit",
    "KnowledgeChunk",
    "RetrievalChunk",
    "RetrievalResult",
    "Category",
    "Confidence",
    "Contact",
]
