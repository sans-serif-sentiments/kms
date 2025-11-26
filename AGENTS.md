# AI-KMS Agents

This document clarifies which autonomous (or human-assisted) agents own each part of the system so new contributors know where to plug in automation or workflows.

## 1. Repo Sync Agent
- **Purpose:** Keep the local `kb_repo/` clone aligned with GitHub.
- **Entry point:** `app/kb/repo_sync.py:git_pull`
- **Responsibilities:**
  - Watch for upstream updates (GitHub webhooks or cron).
  - Execute `git pull` + `ingest_kb()`.
  - Report changed files and indexing stats.
- **Escalation:** If conflicts arise or metadata validation fails, notify the Knowledge Steward (human) with affected paths.

## 2. Ingestion & Indexing Agent
- **Purpose:** Parse markdown, validate frontmatter, chunk content, and update SQLite/Chroma.
- **Entry point:** `app/kb/ingestion.py:ingest_kb`
- **Responsibilities:**
  - Enforce schema requirements (required fields, valid categories/confidences).
  - Generate deterministic chunk IDs and metadata for retrieval, logging warnings when data quality issues appear.
  - Maintain the `files`, `chunks`, and `units` tables for inspection APIs.
- **Escalation:** Emit warnings when metadata is missing; a downstream QC agent or human should triage.

## 3. Retrieval Agent
- **Purpose:** Serve hybrid lexical/vector retrieval with reranking.
- **Entry point:** `app/kb/retrieval.py:HybridRetriever`
- **Responsibilities:**
  - Keep BM25 corpus in sync with SQLite chunks.
  - Query Chroma, perform reciprocal-rank fusion, rerank with CrossEncoder, and expose debug traces.
  - Flag empty or low-confidence results so the RAG layer can abstain.

## 4. RAG Answering Agent
- **Purpose:** Compose prompts, call the LLM backend, and return answers with citations.
- **Entry point:** `app/rag/pipeline.py:RAGPipeline`
- **Responsibilities:**
  - Format selected chunks with section/source metadata.
  - Enforce truthfulness guardrails: if no relevant chunks, respond with "No relevant knowledge found"; if low confidence, warn the user.
  - Track cited sources for downstream evaluation.
- **Escalation:** If the LLM backend is unavailable, bubble up an operational alert and skip answering.

## 5. Evaluation Agent
- **Purpose:** Run regression-style checks on the RAG pipeline.
- **Entry point:** `app/eval/evaluator.py`
- **Responsibilities:**
  - Iterate over `app/eval/dataset.yaml`, call the RAG pipeline, and compute citation/overlap metrics.
  - Produce human-readable summaries for QA sessions.

## 6. API Agent
- **Purpose:** Expose the FastAPI surface and basic observability endpoints.
- **Entry point:** `app/api/routes.py`
- **Responsibilities:**
  - Provide `/health`, `/sync`, `/query`, `/inspect/*` routes.
  - Return system stats (unit counts, last indexed times) for monitoring dashboards.
  - Relay debug traces when clients request `debug=true`.

## 7. Future Hooks
- **Graph Agent:** Placeholder in `app/kb/graph.py` for entity/relation extraction and knowledge graph sync.
- **Multi-Source Agent:** Extend ingestion to new backends (Notion/Confluence/DB) using the `KnowledgeUnit` abstraction.

Each agent can be automated (e.g., run via cron, GitHub Action, or background worker) or executed manually via the corresponding CLI/HTTP entry point. Keep logging enabled (`app/core/logging.py`) so all agent activities are observable.
