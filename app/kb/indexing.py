"""Index management for vector store and sqlite metadata."""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from uuid import uuid4

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import HashingVectorizer
import os
import tempfile

os.environ.setdefault("CHROMA_TELEMETRY_ENABLED", "FALSE")
TMP_DIR = Path("./tmp")
TMP_DIR.mkdir(exist_ok=True)
os.environ.setdefault("TMPDIR", str(TMP_DIR.resolve()))
tempfile.tempdir = os.environ["TMPDIR"]

from app.core.config import get_settings
from app.kb.models import KnowledgeChunk, KnowledgeUnit

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class StateStore:
    """SQLite backed metadata store tracking files and chunks."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.ensure_schema()

    def ensure_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                source_path TEXT PRIMARY KEY,
                file_hash TEXT NOT NULL,
                indexed_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                knowledge_unit_id TEXT NOT NULL,
                source_path TEXT NOT NULL,
                section_name TEXT,
                text TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS units (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                tags TEXT,
                version TEXT,
                source_path TEXT,
                updated_at TEXT,
                author TEXT,
                confidence TEXT,
                summary TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS session_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS unit_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit_id TEXT NOT NULL,
                name TEXT NOT NULL,
                title TEXT,
                email TEXT,
                slack TEXT,
                phone TEXT,
                notes TEXT,
                priority INTEGER,
                FOREIGN KEY(unit_id) REFERENCES units(id) ON DELETE CASCADE
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS unit_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit_id TEXT NOT NULL,
                related_unit_id TEXT NOT NULL,
                relation_type TEXT DEFAULT 'related',
                FOREIGN KEY(unit_id) REFERENCES units(id) ON DELETE CASCADE
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS unit_systems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit_id TEXT NOT NULL,
                system_name TEXT NOT NULL,
                FOREIGN KEY(unit_id) REFERENCES units(id) ON DELETE CASCADE
            )
            """
        )
        self._conn.commit()

    def get_file_hash(self, source_path: str) -> Optional[str]:
        cur = self._conn.cursor()
        cur.execute("SELECT file_hash FROM files WHERE source_path=?", (source_path,))
        row = cur.fetchone()
        return row["file_hash"] if row else None

    def update_file(self, source_path: str, file_hash: str) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO files(source_path, file_hash, indexed_at)
            VALUES(?, ?, ?)
            ON CONFLICT(source_path) DO UPDATE SET file_hash=excluded.file_hash, indexed_at=excluded.indexed_at
            """,
            (source_path, file_hash, datetime.utcnow().isoformat()),
        )
        self._conn.commit()

    def upsert_chunks(self, chunks: Iterable[KnowledgeChunk]) -> None:
        cur = self._conn.cursor()
        for chunk in chunks:
            cur.execute(
                """
                INSERT INTO chunks(chunk_id, knowledge_unit_id, source_path, section_name, text, metadata_json)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id) DO UPDATE SET
                    knowledge_unit_id=excluded.knowledge_unit_id,
                    source_path=excluded.source_path,
                    section_name=excluded.section_name,
                    text=excluded.text,
                    metadata_json=excluded.metadata_json
                """,
                (
                    chunk.chunk_id,
                    chunk.knowledge_unit_id,
                    chunk.source_path,
                    chunk.section_name,
                    chunk.text,
                    json.dumps(chunk.metadata),
                ),
            )
        self._conn.commit()

    def list_chunks(self) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM chunks")
        rows = cur.fetchall()
        return [dict(row) for row in rows]

    def get_stats(self) -> Dict[str, int]:
        cur = self._conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM chunks")
        chunks = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM files")
        files = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM units")
        units = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM sessions")
        sessions = cur.fetchone()["cnt"]
        return {"chunks": chunks, "files": files, "units": units, "sessions": sessions}

    def get_last_indexed_at(self) -> Optional[str]:
        cur = self._conn.cursor()
        cur.execute("SELECT MAX(indexed_at) AS ts FROM files")
        row = cur.fetchone()
        return row["ts"] if row and row["ts"] else None

    def get_ingest_fingerprint(self) -> Dict[str, object]:
        """Return lightweight fingerprint used to detect ingestion changes."""

        cur = self._conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM chunks")
        chunks = cur.fetchone()["cnt"]
        cur.execute("SELECT MAX(indexed_at) AS ts FROM files")
        row = cur.fetchone()
        return {"chunks": chunks, "last_indexed_at": row["ts"] if row and row["ts"] else None}

    def list_known_files(self) -> List[str]:
        """Return all source paths tracked in the files table."""

        cur = self._conn.cursor()
        cur.execute("SELECT source_path FROM files")
        rows = cur.fetchall()
        return [row["source_path"] for row in rows]

    def get_unit_ids_for_source(self, source_path: str) -> List[str]:
        cur = self._conn.cursor()
        cur.execute("SELECT id FROM units WHERE source_path=?", (source_path,))
        rows = cur.fetchall()
        return [row["id"] for row in rows]

    def list_chunk_ids_for_unit(self, unit_id: str) -> List[str]:
        cur = self._conn.cursor()
        cur.execute("SELECT chunk_id FROM chunks WHERE knowledge_unit_id=?", (unit_id,))
        rows = cur.fetchall()
        return [row["chunk_id"] for row in rows]

    def delete_file_record(self, source_path: str) -> None:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM files WHERE source_path=?", (source_path,))
        self._conn.commit()

    def delete_unit(self, unit_id: str) -> None:
        """Delete unit + dependent rows (chunks, contacts, relations, systems)."""

        cur = self._conn.cursor()
        cur.execute("DELETE FROM chunks WHERE knowledge_unit_id=?", (unit_id,))
        cur.execute("DELETE FROM unit_contacts WHERE unit_id=?", (unit_id,))
        cur.execute("DELETE FROM unit_relations WHERE unit_id=?", (unit_id,))
        cur.execute("DELETE FROM unit_systems WHERE unit_id=?", (unit_id,))
        cur.execute("DELETE FROM units WHERE id=?", (unit_id,))
        self._conn.commit()

    def upsert_unit(self, unit) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO units(id, title, category, tags, version, source_path, updated_at, author, confidence, summary)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                category=excluded.category,
                tags=excluded.tags,
                version=excluded.version,
                source_path=excluded.source_path,
                updated_at=excluded.updated_at,
                author=excluded.author,
                confidence=excluded.confidence,
                summary=excluded.summary
            """,
            (
                unit.id,
                unit.title,
                str(unit.category),
                ",".join(unit.tags),
                unit.version,
                unit.source_path,
                unit.updated_at,
                unit.author,
                str(unit.confidence),
                unit.summary or "",
            ),
        )
        self._conn.commit()

    def sync_contacts(self, unit: KnowledgeUnit) -> None:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM unit_contacts WHERE unit_id=?", (unit.id,))
        for contact in unit.contacts:
            cur.execute(
                """
                INSERT INTO unit_contacts(unit_id, name, title, email, slack, phone, notes, priority)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    unit.id,
                    contact.name,
                    contact.title,
                    contact.email,
                    contact.slack,
                    contact.phone,
                    contact.notes,
                    contact.priority,
                ),
            )
        self._conn.commit()

    def sync_relations(self, unit: KnowledgeUnit) -> None:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM unit_relations WHERE unit_id=?", (unit.id,))
        for related in unit.related_units:
            if not related:
                continue
            cur.execute(
                """
                INSERT INTO unit_relations(unit_id, related_unit_id, relation_type)
                VALUES(?, ?, ?)
                """,
                (unit.id, related, "related"),
            )
        self._conn.commit()

    def sync_systems(self, unit: KnowledgeUnit) -> None:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM unit_systems WHERE unit_id=?", (unit.id,))
        for system_name in unit.systems:
            if not system_name:
                continue
            cur.execute(
                """
                INSERT INTO unit_systems(unit_id, system_name)
                VALUES(?, ?)
                """,
                (unit.id, system_name),
            )
        self._conn.commit()

    def list_units(
        self,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        updated_since: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, str]]:
        clauses = []
        params: List[str] = []
        if category:
            clauses.append("category=?")
            params.append(category)
        if tag:
            clauses.append("tags LIKE ?")
            params.append(f"%{tag}%")
        if updated_since:
            clauses.append("updated_at >= ?")
            params.append(updated_since)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        query = f"SELECT * FROM units {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cur = self._conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        return [dict(row) for row in rows]

    def list_all_units(self) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM units")
        rows = cur.fetchall()
        return [dict(row) for row in rows]

    def list_all_contacts(self) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT unit_id, name, title, email, slack, phone, notes, priority
            FROM unit_contacts
            ORDER BY COALESCE(priority, 1000) ASC, name ASC
            """
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]

    def list_all_relations(self) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT unit_id, related_unit_id, relation_type
            FROM unit_relations
            """
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]

    def list_all_systems(self) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT unit_id, system_name
            FROM unit_systems
            """
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]

    # Session management -------------------------------------------------
    def create_session(self, name: Optional[str] = None) -> str:
        session_id = uuid4().hex[:8]
        now = datetime.utcnow().isoformat()
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO sessions(id, name, created_at, updated_at)
            VALUES(?, ?, ?, ?)
            """,
            (session_id, name, now, now),
        )
        self._conn.commit()
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM sessions WHERE id=?", (session_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def touch_session(self, session_id: str) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE sessions SET updated_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), session_id),
        )
        self._conn.commit()

    def add_session_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO session_messages(session_id, role, content, metadata_json, created_at)
            VALUES(?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                json.dumps(metadata or {}),
                datetime.utcnow().isoformat(),
            ),
        )
        self._conn.commit()
        self.touch_session(session_id)

    def list_session_messages(self, session_id: str) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT role, content, metadata_json, created_at
            FROM session_messages
            WHERE session_id=?
            ORDER BY id ASC
            """,
            (session_id,),
        )
        rows = cur.fetchall()
        result: List[Dict[str, str]] = []
        for row in rows:
            metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
            result.append(
                {
                    "role": row["role"],
                    "content": row["content"],
                    "metadata": metadata,
                    "created_at": row["created_at"],
                }
            )
        return result

    def get_unit(self, unit_id: str) -> Optional[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM units WHERE id=?", (unit_id,))
        row = cur.fetchone()
        return dict(row) if row else None


class VectorIndex:
    """Wrapper around Chroma persistent collection."""

    def __init__(self, path: Path, collection: str = "knowledge_chunks"):
        settings = get_settings()
        self.client = chromadb.PersistentClient(
            path=str(path),
            settings=ChromaSettings(allow_reset=False, anonymized_telemetry=False),
        )
        self.embedding_fn = ResilientEmbeddingFunction(settings.index.embed_model)
        self.collection = self.client.get_or_create_collection(
            name=collection, embedding_function=self.embedding_fn
        )

    def upsert(self, chunks: Iterable[KnowledgeChunk]) -> None:
        ids = []
        documents = []
        metadatas = []
        for chunk in chunks:
            ids.append(chunk.chunk_id)
            documents.append(chunk.text)
            metadatas.append(chunk.metadata)
        if ids:
            self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    def query(self, query_text: str, top_k: int) -> List[Dict[str, str]]:
        result = self.collection.query(query_texts=[query_text], n_results=top_k)
        hits: List[Dict[str, str]] = []
        if not result or not result.get("ids"):
            return hits
        for idx, chunk_id in enumerate(result["ids"][0]):
            hits.append(
                {
                    "chunk_id": chunk_id,
                    "score": float(result["distances"][0][idx]) if result.get("distances") else 0.0,
                    "metadata": result["metadatas"][0][idx],
                    "document": result["documents"][0][idx],
                }
            )
        return hits

    def delete_chunks(self, chunk_ids: Iterable[str]) -> None:
        ids = [chunk_id for chunk_id in chunk_ids if chunk_id]
        if ids:
            self.collection.delete(ids=ids)


def _resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def get_state_store() -> StateStore:
    settings = get_settings()
    resolved = _resolve_path(settings.index.sqlite_path)
    return StateStore(resolved)


def get_vector_index() -> VectorIndex:
    settings = get_settings()
    resolved = _resolve_path(settings.index.chroma_path)
    return VectorIndex(resolved)


class HashingEmbeddingFunction(embedding_functions.EmbeddingFunction):
    """Simple hashing-based fallback embedding function."""

    def __init__(self, n_features: int = 512):
        self.vectorizer = HashingVectorizer(n_features=n_features, alternate_sign=False, norm=None)

    def __call__(self, input: List[str]):
        matrix = self.vectorizer.transform(input)
        dense = matrix.toarray()
        return dense.tolist()


class ResilientEmbeddingFunction(embedding_functions.EmbeddingFunction):
    """Tries to use a SentenceTransformer but falls back to hashing if unavailable."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._fn = self._load_sentence_transformer(model_name)

    def _load_sentence_transformer(self, model_name: str):
        try:
            local_path = Path(model_name)
            if local_path.exists():
                LOGGER.info("Loading embedding model from %s", local_path)
                return LocalSentenceTransformerEmbedding(local_path)
            LOGGER.info("Loading embedding model %s from hub", model_name)
            return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("Could not load %s (%s); using hashing embeddings.", model_name, exc)
            return HashingEmbeddingFunction()

    def __call__(self, input: List[str]):
        try:
            return self._fn(input)
        except Exception as exc:  # pragma: no cover - runtime failure
            if isinstance(self._fn, HashingEmbeddingFunction):
                raise
            LOGGER.warning("Embedding model %s failed (%s); switching to hashing.", self.model_name, exc)
            self._fn = HashingEmbeddingFunction()
            return self._fn(input)


class LocalSentenceTransformerEmbedding(embedding_functions.EmbeddingFunction):
    """Embedding function that loads SentenceTransformer from a local directory."""

    def __init__(self, path: Path):
        self._model = SentenceTransformer(str(path))

    def __call__(self, input: List[str]):
        embeddings = self._model.encode(input, convert_to_numpy=True, normalize_embeddings=False)
        return embeddings.tolist()


__all__ = ["StateStore", "VectorIndex", "get_state_store", "get_vector_index"]
