# AI-KMS

AI-KMS is a local-first Knowledge Management + Retrieval-Augmented Generation stack. It ingests markdown policies from a GitHub repo, indexes them in SQLite + Chroma, and exposes a FastAPI/React front end backed by local embeddings and an Ollama LLM. See the [architecture diagram](./assets/architecture.md) for a visual overview.

## Tool Stack
- **Backend:** Python 3.11, FastAPI, SentenceTransformers, PyTorch (MPS/CPU), ChromaDB, SQLite.
- **LLM Runtime:** Ollama with `llama3.2:3b` or `phi3:mini-128k`.
- **General Knowledge Engine:** configurable lightweight local model (`LLMSettings.general_model`, default `llama3.2:1b`) for world/external queries.
- **Embeddings:** Local `models/bge-small-en` (downloaded via Git LFS) with dynamic fallback to hashing if unavailable.
- **Frontend:** React + Vite + TypeScript, `react-markdown`, Lucide icons.
- **Deployment:** `uvicorn app.api.routes:app` + `npm run build && serve`. No external dependencies beyond Git/Ollama.

## How Knowledge Flows
For a detailed sequence, check the [query flow diagram](./assets/query_flow.md).
1. `make index` pulls `kb_repo/kb/**.md`, parses YAML frontmatter, and chunks sections.
2. Metadata lands in `storage/state.sqlite`; embeddings go to `storage/chroma` using local BGE weights.
3. Hybrid retrieval (BM25 + Chroma + tag-based graph) fuses scores; optional reranker (`BAAI/bge-reranker-base`).
4. FastAPI `/query` builds structured prompts (Direct Support, Contacts, Next Steps, Confidence) and calls Ollama.
5. React UI renders answers with citations, copy/draft/download actions, and advanced tuning (model/min score/debug).

## Deployment Guide
### Prereqs
- Python 3.11, Node 20+, Git LFS, Ollama.

### Setup
```bash
git clone <this repo>
cd AI-KMS
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

### Fetch embeddings
```bash
git lfs install
git clone https://huggingface.co/BAAI/bge-small-en models/bge-small-en
```

### Index KB
```bash
make index            # reads kb_repo and updates SQLite + Chroma
make run              # start API on http://127.0.0.1:8300 in another terminal
make update-kb        # calls /sync -> git pull --ff-only + ingest
```
`make update-kb` requires the API to be running; it will fail if your local `kb_repo` has uncommitted or divergent changes. Resolve git conflicts first, then rerun.

### Run backend
```bash
source .venv/bin/activate
# optional: use LangGraph orchestration instead of builtin pipeline
export AGENT__ORCHESTRATOR=langgraph
uvicorn app.api.routes:app --host 127.0.0.1 --port 8300
```

### Run frontend
```bash
cd frontend
npm run dev           # http://127.0.0.1:5173
```

### Production build
```bash
cd frontend
npm run build
cd ..
uvicorn app.api.routes:app --host 0.0.0.0 --port 8300
# serve frontend/dist via any static server or behind nginx
```

## Key Features
- Hybrid retrieval with per-query `min_score_threshold` overrides and graph/tag awareness; LangGraph orchestrator routes requests by intent (small talk, wellness, world question, policy).
- Friendly fallback/clarification flow; small-talk detection avoids overlong KB answers.
- UI action bar (copy, draft email, download) + advanced drawer for power users.
- Session persistence and transcript export.
- Confidence signal returned with every answer and rendered in the UI.

## Repository Layout
```
app/       # FastAPI, ingestion, retrieval, RAG pipeline
kb_repo/   # Markdown knowledge base (Git source of truth)
models/    # Local embeddings (BGE)
frontend/  # React + Vite console
storage/   # SQLite + Chroma persistence
USE_CASES.md # Domain use cases and pain points
```

## Use Cases
See [USE_CASES.md](./USE_CASES.md) for mapped journeys (HR leave, Security incident response, Finance travel, IT assets, Enablement messaging).

## Observability
- Logs print ingest stats and retrieval debug scores.
- `/health` returns repo path, unit count, last indexed timestamp.
- Frontend advanced drawer exposes debug flag to fetch raw retrieval traces.

## Contributing
1. Add or edit Markdown under `kb_repo/kb/*`. Keep frontmatter aligned with `app/kb/models.py`.
2. Run `make index` to refresh embeddings.
3. When reorganising `kb_repo`, ensure `git pull --ff-only` still succeeds so `/sync` can run non-interactively.
4. Submit PRs with tests/notes (`frontend` has `npm run lint/build`).

## License
Internal demo; adapt licensing as needed for your org.
