"""Hybrid retrieval combining BM25, Chroma, and optional reranking."""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Dict, List, Optional
import os

from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from app.core.config import get_settings
from app.kb.graph import KnowledgeGraph
from app.kb.indexing import get_state_store, get_vector_index
from app.kb.models import KnowledgeChunk, RetrievalChunk, RetrievalResult

LOGGER = logging.getLogger(__name__)


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def simple_tokenize(text: str) -> List[str]:
    """Lowercase tokeniser that drops punctuation for consistent lexical scoring."""

    return TOKEN_PATTERN.findall(text.lower())


class LexicalIndex:
    def __init__(self):
        self.store = get_state_store()
        self.chunks: Dict[str, KnowledgeChunk] = {}
        self.ids: List[str] = []
        self.tokenized_docs: List[List[str]] = []
        self.bm25: Optional[BM25Okapi] = None
        self._fingerprint: Dict[str, object] = {"chunks": 0, "last_indexed_at": None}
        self.refresh()

    def refresh(self) -> None:
        self.chunks.clear()
        documents: List[List[str]] = []
        rows = self.store.list_chunks()
        for row in rows:
            metadata = json.loads(row["metadata_json"]) if row.get("metadata_json") else {}
            chunk = KnowledgeChunk(
                chunk_id=row["chunk_id"],
                knowledge_unit_id=row["knowledge_unit_id"],
                source_path=row["source_path"],
                section_name=row["section_name"],
                text=row["text"],
                metadata=metadata,
            )
            self.chunks[chunk.chunk_id] = chunk
            documents.append(simple_tokenize(chunk.text))
        self.ids = list(self.chunks.keys())
        self.tokenized_docs = documents
        self.bm25 = BM25Okapi(documents) if documents else None
        self._fingerprint = self.store.get_ingest_fingerprint()

    def _is_stale(self) -> bool:
        current = self.store.get_ingest_fingerprint()
        return current != self._fingerprint

    def _matches_prefix(self, chunk_id: str, unit_id: str, allowed_prefixes: Optional[List[str]]) -> bool:
        if not allowed_prefixes:
            return True
        return any(unit_id.startswith(prefix) for prefix in allowed_prefixes)

    def search(
        self,
        query: str,
        top_n: int,
        allowed_prefixes: Optional[List[str]] = None,
    ) -> List[RetrievalChunk]:
        if self._is_stale():
            LOGGER.info("Lexical index detected new ingestion; refreshing BM25 corpus.")
            self.refresh()
        if not self.bm25:
            return []
        tokens = simple_tokenize(query)
        scores = self.bm25.get_scores(tokens)
        scored = sorted(
            zip(self.ids, scores), key=lambda item: item[1], reverse=True
        )[:top_n]
        results: List[RetrievalChunk] = []
        for rank, (_id, score) in enumerate(scored):
            if score <= 0:
                continue
            chunk = self.chunks[_id]
            unit_id = chunk.knowledge_unit_id
            if not self._matches_prefix(_id, unit_id, allowed_prefixes):
                continue
            results.append(
                RetrievalChunk(chunk=chunk, score=float(score), rank=rank + 1, source="lexical")
            )
        return results


class HybridRetriever:
    """Coordinate lexical, vector, and reranker stages."""

    def __init__(self):
        self.settings = get_settings()
        self.rerank_max_candidates = int(
            os.getenv(
                "RETRIEVAL__RERANK_MAX_CANDIDATES",
                self.settings.retrieval.rerank_max_candidates,
            )
        )
        self.lexical = LexicalIndex()
        self.vector_index = get_vector_index()
        self.graph = KnowledgeGraph()
        self._reranker: Optional[CrossEncoder] = None
        LOGGER.info("HybridRetriever initialised with lexical, vector, and graph indexes.")

    def _normalize_query(self, query: str) -> str:
        return " ".join(query.strip().lower().split())

    def _reciprocal_rank_fusion(self, candidates: List[List[RetrievalChunk]]) -> List[RetrievalChunk]:
        fusion_scores: Dict[str, float] = defaultdict(float)
        chunk_map: Dict[str, RetrievalChunk] = {}
        for result in candidates:
            for chunk in result:
                fusion_scores[chunk.chunk.chunk_id] += 1.0 / (50 + chunk.rank)
                if chunk.chunk.chunk_id not in chunk_map:
                    chunk_map[chunk.chunk.chunk_id] = chunk
        ranked = sorted(
            chunk_map.values(), key=lambda rc: fusion_scores[rc.chunk.chunk_id], reverse=True
        )
        for idx, chunk in enumerate(ranked):
            chunk.rank = idx + 1
            chunk.score = fusion_scores[chunk.chunk.chunk_id] * 100.0
        return ranked

    def _maybe_rerank(self, query: str, chunks: List[RetrievalChunk]) -> List[RetrievalChunk]:
        if not chunks:
            return chunks
        max_candidates = max(1, self.rerank_max_candidates)
        candidates = chunks[:max_candidates]
        try:
            reranker = self._get_reranker()
        except Exception as exc:  # pragma: no cover - model load errors
            LOGGER.warning("Reranker unavailable: %s", exc)
            return chunks
        pairs = [[query, chunk.chunk.text] for chunk in candidates]
        try:
            scores = reranker.predict(pairs)
        except Exception as exc:  # pragma: no cover - inference issues
            LOGGER.warning("Reranker predict failed; continuing without rerank: %s", exc)
            return chunks
        for chunk, score in zip(candidates, scores):
            chunk.score = float(score)
        reranked = sorted(candidates + chunks[len(candidates) :], key=lambda rc: rc.score, reverse=True)
        return reranked

    def _get_reranker(self) -> CrossEncoder:
        if not self._reranker:
            model_path = self.settings.index.reranker_model_path
            LOGGER.info("Loading reranker model %s", model_path)
            self._reranker = CrossEncoder(str(model_path))
        return self._reranker

    def _vector_search(
        self, query: str, top_n: int, allowed_prefixes: Optional[List[str]] = None
    ) -> List[RetrievalChunk]:
        try:
            results = self.vector_index.query(query, top_n)
        except Exception as exc:  # pragma: no cover
            LOGGER.error("Vector search failed: %s", exc)
            return []
        out: List[RetrievalChunk] = []
        for rank, item in enumerate(results):
            chunk_id = item["chunk_id"]
            metadata = item.get("metadata", {})
            chunk = self.lexical.chunks.get(chunk_id)
            if not chunk:
                chunk = KnowledgeChunk(
                    chunk_id=chunk_id,
                    knowledge_unit_id=metadata.get("knowledge_unit_id", ""),
                    source_path=metadata.get("source_path", ""),
                    section_name=metadata.get("section", ""),
                    text=item.get("document", ""),
                    metadata=metadata,
                )
            if not self.lexical._matches_prefix(chunk_id, chunk.knowledge_unit_id, allowed_prefixes):
                continue
            distance = float(item.get("score") or item.get("distance") or 0.0)
            score = 1.0 / (1.0 + distance)
            out.append(
                RetrievalChunk(chunk=chunk, score=score, rank=rank + 1, source="vector")
            )
        return out

    def retrieve(
        self,
        query: str,
        min_score_override: Optional[float] = None,
        allowed_prefixes: Optional[List[str]] = None,
    ) -> RetrievalResult:
        normalized = self._normalize_query(query)
        lexical_chunks = self.lexical.search(
            normalized, self.settings.retrieval.top_n_lexical, allowed_prefixes
        )
        vector_chunks = self._vector_search(
            normalized, self.settings.retrieval.top_n_vector, allowed_prefixes
        )
        graph_chunks = self.graph.search(normalized, self.settings.retrieval.top_k_final)
        fused = self._reciprocal_rank_fusion([lexical_chunks, vector_chunks, graph_chunks])
        if vector_chunks:
            fused = self._maybe_rerank(normalized, fused)  # rerank before thresholding when possible
        threshold = (
            min_score_override
            if min_score_override is not None
            else self.settings.retrieval.min_score_threshold
        )
        filtered = [c for c in fused if c.score >= threshold]
        if not filtered:
            reranked: List[RetrievalChunk] = []
        else:
            reranked = filtered[: self.settings.retrieval.top_k_final]
        debug = {
            "lexical": [
                {"chunk_id": c.chunk.chunk_id, "score": c.score, "rank": c.rank} for c in lexical_chunks
            ],
            "vector": [
                {"chunk_id": c.chunk.chunk_id, "score": c.score, "rank": c.rank} for c in vector_chunks
            ],
            "graph": [
                {"chunk_id": c.chunk.chunk_id, "score": c.score, "rank": c.rank} for c in graph_chunks
            ],
            "fused": [
                {"chunk_id": c.chunk.chunk_id, "score": c.score, "rank": c.rank} for c in fused
            ],
            "threshold": [{"value": threshold}],
        }
        return RetrievalResult(query=query, selected_chunks=reranked, debug=debug)

    def refresh_sources(self) -> None:
        LOGGER.info("Refreshing lexical BM25 index and knowledge graph metadata")
        self.lexical.refresh()
        self.graph.refresh()


__all__ = ["HybridRetriever"]
