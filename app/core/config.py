"""Application configuration utilities.

This module centralises the knobs that turn the KB pipeline:
- GitHub repo paths, indexing directories, and Chroma persistence.
- Retrieval hyperparameters for lexical/vector fusion.
The broader project constraints (local-first, modular, truthful) are
restated here so every engineer sees them when tweaking settings.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


class RepoSettings(BaseModel):
    """Location of the GitHub knowledge repository clone."""

    repo_path: Path = Field(default=Path("./kb_repo"))
    branch: str = Field(default="main")
    kb_root: Path = Field(default=Path("kb"))
    repo_url: Optional[str] = Field(
        default="https://github.com/sans-serif-sentiments/knowledge-repo",
        description="Optional HTTPS URL to the remote repo (used for building GitHub links).",
    )


class IndexSettings(BaseModel):
    """Paths and knobs for the local indexes."""

    chroma_path: Path = Field(default=Path("./storage/chroma"))
    sqlite_path: Path = Field(default=Path("./storage/state.sqlite"))
    embed_model: str = Field(default="models/bge-small-en")
    reranker_model: str = Field(default="BAAI/bge-reranker-base")
    chunk_size: int = Field(default=800, description="Max characters per chunk")
    chunk_overlap: int = Field(default=100)

    @property
    def embed_model_path(self) -> Path:
        """Return the resolved embedding model path when a local folder is provided."""

        path = Path(self.embed_model)
        return path if path.exists() else path

    @property
    def reranker_model_path(self):
        """Return a local path if present; otherwise return the configured model id."""

        path = Path(self.reranker_model)
        return path if path.exists() else self.reranker_model


class RetrievalSettings(BaseModel):
    """Hybrid retrieval parameters."""

    top_n_lexical: int = 8
    top_n_vector: int = 8
    top_k_final: int = 6
    min_score_threshold: float = 0.15
    max_context_chars: int = 8000
    rerank_max_candidates: int = Field(
        default=50, description="Cap on how many fused chunks we send to the reranker."
    )


class ApiSettings(BaseModel):
    """Basic FastAPI metadata."""

    title: str = "AI-KMS"
    version: str = "0.1.0"
    debug: bool = False


class LLMSettings(BaseModel):
    """LLM runtime configuration."""

    default_model: str = "llama3.2:3b"
    base_url: str = "http://localhost:11434"
    allowed_models: List[str] = Field(default_factory=lambda: ["llama3.2:3b", "phi3:mini-128k"])
    general_model: str = Field(default="phi3:mini-128k", description="Model used for world/general intents")


class AgentSettings(BaseModel):
    """Agent orchestration toggles."""

    orchestrator: str = Field(
        default="builtin",
        description="Set to 'langgraph' to route chat through the LangGraph coordinator.",
    )


class Settings(BaseModel):
    """Root settings object exposed via dependency injection."""

    repo: RepoSettings = RepoSettings()
    index: IndexSettings = IndexSettings()
    retrieval: RetrievalSettings = RetrievalSettings()
    api: ApiSettings = ApiSettings()
    llm: LLMSettings = LLMSettings()
    agent: AgentSettings = AgentSettings()
    allowed_categories: List[str] = Field(
        default_factory=lambda: [
            "concept",
            "process",
            "policy",
            "glossary",
            "faq",
            "decision",
            "metric",
            "pattern",
            "langraph",
        ]
    )
    confidence_levels: List[str] = Field(default_factory=lambda: ["low", "medium", "high"])


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()


__all__ = ["Settings", "get_settings"]
