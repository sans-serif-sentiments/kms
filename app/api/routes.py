"""FastAPI app exposing health, sync, query, and inspection endpoints."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from app.agents.langgraph_runner import LangGraphCoordinator
except Exception:  # pragma: no cover - optional dependency
    LangGraphCoordinator = None  # type: ignore[assignment]
from app.chat.store import get_chat_store
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.kb.ingestion import ingest_kb
from app.kb.indexing import get_state_store
from app.kb.repo_sync import RepoSyncError, git_pull
from app.rag.pipeline import RAGPipeline
from app.kb.repo_sync import list_markdown_files
from pathlib import Path
import frontmatter
import yaml
import os
import io
import zipfile
from typing import List, Optional
try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - optional
    pd = None
try:
    import PyPDF2  # type: ignore
except Exception:  # pragma: no cover - optional
    PyPDF2 = None

configure_logging()
app = FastAPI(title="AI-KMS", version="0.1.0")

static_dir = Path("frontend/dist")
if static_dir.exists():
    app.mount("/ui", StaticFiles(directory=static_dir, html=True), name="ui")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
pipeline = RAGPipeline()
chat_store = get_chat_store()
_langgraph_coordinator: Optional[LangGraphCoordinator] = None
if get_settings().agent.orchestrator.lower() == "langgraph":
    _langgraph_coordinator = LangGraphCoordinator(pipeline)


def get_app_settings() -> Settings:
    return get_settings()


class ChatMessage(BaseModel):
    role: str
    content: str


class QueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = None
    debug: bool = False
    history: list[ChatMessage] = []
    model: Optional[str] = None
    session_id: Optional[str] = None
    min_score_threshold: Optional[float] = None
    allow_external: bool = False


class UploadRequest(BaseModel):
    """Upload a markdown doc into the KB."""

    id: str = Field(..., description="KB ID, e.g., LG-XYZ")
    title: str
    category: str
    body: str = Field(..., description="Markdown body (without frontmatter).")
    tags: Optional[list[str]] = None
    contacts: list[dict] = Field(default_factory=list)
    related_units: Optional[list[str]] = None
    systems: Optional[list[str]] = None
    version: Optional[str] = "0.1.0"
    dry_run: bool = False


class SessionRequest(BaseModel):
    name: Optional[str] = None


@app.get("/")
def root() -> dict:
    """Provide a simple landing response for the root path."""

    response = {
        "message": "AI-KMS API is running.",
        "docs": "/docs",
        "endpoints": ["/health", "/sync", "/query", "/inspect/units", "/inspect/unit/{id}"],
    }
    if static_dir.exists():
        response["ui"] = "/ui"
    return response


@app.get("/health")
def health(settings: Settings = Depends(get_app_settings)) -> dict:
    store = get_state_store()
    stats = store.get_stats()
    return {
        "status": "ok",
        "repo": str(settings.repo.repo_path),
        "units": stats["units"],
        "last_indexed_at": store.get_last_indexed_at(),
    }


@app.post("/sync")
def sync_kb() -> dict:
    try:
        pull_sha = git_pull()
    except RepoSyncError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    ingest_info = ingest_kb()
    pipeline.refresh_indexes()
    return {"pull": pull_sha, **ingest_info["summary"]}


@app.post("/query")
def query_kb(payload: QueryRequest) -> dict:
    model = payload.model
    settings = get_settings()
    if model and model not in settings.llm.allowed_models:
        raise HTTPException(status_code=400, detail=f"Model {model} not allowed")
    history: list[dict] = []
    if payload.session_id:
        session = chat_store.load_session(payload.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="session_not_found")
        history = [{"role": msg["role"], "content": msg["content"]} for msg in session["messages"]]
    elif payload.history:
        history = [message.model_dump() for message in payload.history]
    if _langgraph_coordinator:
        result = _langgraph_coordinator.answer(
            payload.question,
            top_k=payload.top_k,
            debug=payload.debug,
            history=history,
            model=model,
            min_score_override=payload.min_score_threshold,
            allow_external=payload.allow_external,
        )
    else:
        result = pipeline.answer_question(
            payload.question,
            payload.top_k,
            payload.debug,
            history,
            model=model,
            min_score_override=payload.min_score_threshold,
            allow_external=payload.allow_external,
        )
    if payload.session_id:
        chat_store.append_message(
            payload.session_id,
            "user",
            payload.question,
            {"debug": payload.debug, "model": model or settings.llm.default_model},
        )
        chat_store.append_message(
            payload.session_id,
            "assistant",
            result["answer"],
            {
                "sources": result.get("sources", []),
                "model": result.get("model"),
                "confidence": result.get("confidence"),
                "source_type": result.get("source_type"),
            },
        )
        result["session_id"] = payload.session_id
    return result


@app.get("/chat/greet")
def chat_greet(name: Optional[str] = Query(default=None)) -> dict:
    """Return a friendly greeting that explains the assistant role."""

    return pipeline.generate_greeting(name)


@app.post("/chat/session")
def chat_session(payload: SessionRequest) -> dict:
    session = chat_store.create_session(payload.name)
    greeting = pipeline.generate_greeting(payload.name)
    chat_store.append_message(session["session_id"], "assistant", greeting["message"], {"type": "greeting"})
    return {"session_id": session["session_id"], "greeting": greeting["message"], "name": session.get("name")}


@app.get("/chat/session/{session_id}")
def chat_session_history(session_id: str):
    session = chat_store.load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/chat/models")
def chat_models() -> dict:
    """List allowed LLM models for chat."""

    settings = get_settings()
    return {"default": settings.llm.default_model, "allowed": settings.llm.allowed_models}


@app.post("/upload")
def upload_doc(payload: UploadRequest) -> dict:
    """Upload a markdown document into the KB, then reindex."""

    settings = get_settings()
    if payload.category not in settings.allowed_categories and payload.category != "langraph":
        raise HTTPException(status_code=400, detail=f"Invalid category {payload.category}")
    kb_root = settings.repo.repo_path / settings.repo.kb_root
    kb_root.mkdir(parents=True, exist_ok=True)
    target_dir = kb_root / "uploads"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{payload.id}.md"

    fm = {
        "id": payload.id,
        "title": payload.title,
        "category": payload.category,
        "tags": payload.tags or [],
        "version": payload.version or "0.1.0",
        "contacts": payload.contacts or [],
        "related_units": payload.related_units or [],
        "systems": payload.systems or [],
    }
    post = frontmatter.Post(payload.body, **fm)
    if payload.dry_run:
        return {
            "message": "Dry run only - no files written",
            "preview_text": (payload.body or "")[:1200],
            "path": str(target_path.relative_to(settings.repo.repo_path)),
            "indexed": 0,
            "skipped": 0,
            "deleted": 0,
            "chunks": 0,
        }
    target_path.write_text(frontmatter.dumps(post), encoding="utf-8")

    ingest_info = ingest_kb(force=True)
    pipeline.refresh_indexes()
    return {
        "message": "Uploaded and indexed",
        "path": str(target_path.relative_to(settings.repo.repo_path)),
        **ingest_info["summary"],
    }


def _extract_pdf_text(file: UploadFile) -> str:
    if not PyPDF2:
        raise HTTPException(status_code=400, detail="PDF support requires PyPDF2; install it in the backend.")
    try:
        reader = PyPDF2.PdfReader(file.file)
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        return text.strip()
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=400, detail=f"Failed to read PDF: {exc}") from exc


def _extract_xlsx_text(file_bytes: bytes) -> str:
    if not pd:
        raise HTTPException(status_code=400, detail="XLSX support requires pandas; install it in the backend.")
    try:
        buffer = io.BytesIO(file_bytes)
        frames = pd.read_excel(buffer, sheet_name=None)
        parts: List[str] = []
        for sheet_name, df in frames.items():
            parts.append(f"# Sheet: {sheet_name}")
            try:
                parts.append(df.to_markdown(index=False))
            except Exception:
                parts.append(df.to_csv(index=False))
        return "\n\n".join(parts)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=400, detail=f"Failed to read XLSX: {exc}") from exc


def _extract_from_zip(file_bytes: bytes, target_dir: Path) -> List[str]:
    saved_paths: List[str] = []
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            ext = os.path.splitext(name)[1].lower()
            data = zf.read(name)
            if ext in {".md", ".markdown"}:
                out_path = target_dir / os.path.basename(name)
                out_path.write_bytes(data)
                saved_paths.append(str(out_path))
            elif ext == ".pdf":
                if not PyPDF2:
                    continue
                reader = PyPDF2.PdfReader(io.BytesIO(data))
                text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
                out_path = target_dir / f"{os.path.splitext(os.path.basename(name))[0]}.md"
                post = frontmatter.Post(text, **{"id": os.path.splitext(os.path.basename(name))[0], "title": name, "category": "upload"})
                out_path.write_text(frontmatter.dumps(post), encoding="utf-8")
                saved_paths.append(str(out_path))
            elif ext in {".xlsx", ".xls"}:
                out_path = target_dir / f"{os.path.splitext(os.path.basename(name))[0]}.md"
                text = _extract_xlsx_text(data)
                post = frontmatter.Post(text, **{"id": os.path.splitext(os.path.basename(name))[0], "title": name, "category": "upload"})
                out_path.write_text(frontmatter.dumps(post), encoding="utf-8")
                saved_paths.append(str(out_path))
    return saved_paths


def _require_contacts(contacts: Optional[str]) -> list[dict]:
    if not contacts:
        raise HTTPException(status_code=400, detail="contacts are required (format: name|email per line)")
    parsed: list[dict] = []
    for line in contacts.splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split("|")]
        if not parts or not parts[0]:
            continue
        contact = {"name": parts[0]}
        if len(parts) > 1 and parts[1]:
            contact["email"] = parts[1]
        parsed.append(contact)
    if not parsed:
        raise HTTPException(status_code=400, detail="contacts are required (format: name|email per line)")
    return parsed


@app.post("/upload/file")
async def upload_file(
    file: UploadFile = File(...),
    id: str = Form(...),
    title: str = Form(...),
    category: str = Form(...),
    tags: str = Form(""),
    version: str = Form("0.1.0"),
    contacts: str = Form(""),
    dry_run: bool = Form(False),
):
    """Upload a file (PDF/Markdown) into the KB, then reindex."""

    settings = get_settings()
    if category not in settings.allowed_categories and category != "langraph":
        raise HTTPException(status_code=400, detail=f"Invalid category {category}")
    contact_list = _require_contacts(contacts)

    kb_root = settings.repo.repo_path / settings.repo.kb_root
    kb_root.mkdir(parents=True, exist_ok=True)
    target_dir = kb_root / "uploads"
    target_dir.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1].lower()

    saved_paths: List[str] = []
    if ext in {".md", ".markdown"}:
        body_bytes = await file.read()
        body_text = body_bytes.decode("utf-8", errors="ignore")
        fm = {
            "id": id,
            "title": title,
            "category": category,
            "tags": [t.strip() for t in tags.split(",") if t.strip()],
            "version": version or "0.1.0",
            "contacts": contact_list,
            "related_units": [],
            "systems": [],
        }
        target_path = target_dir / f"{id}{ext if ext else '.md'}"
        post = frontmatter.Post(body_text, **fm)
        if dry_run:
            return {
                "message": "Dry run only - no files written",
                "paths": [str(target_path.relative_to(settings.repo.repo_path))],
                "preview_text": body_text[:1200],
                "indexed": 0,
                "skipped": 0,
                "deleted": 0,
                "chunks": 0,
            }
        target_path.write_text(frontmatter.dumps(post), encoding="utf-8")
        saved_paths.append(str(target_path.relative_to(settings.repo.repo_path)))
    elif ext == ".pdf":
        body_text = _extract_pdf_text(file)
        fm = {
            "id": id,
            "title": title,
            "category": category,
            "tags": [t.strip() for t in tags.split(",") if t.strip()],
            "version": version or "0.1.0",
            "contacts": contact_list,
            "related_units": [],
            "systems": [],
        }
        target_path = target_dir / f"{id}.md"
        post = frontmatter.Post(body_text, **fm)
        if dry_run:
            return {
                "message": "Dry run only - no files written",
                "paths": [str(target_path.relative_to(settings.repo.repo_path))],
                "preview_text": body_text[:1200],
                "indexed": 0,
                "skipped": 0,
                "deleted": 0,
                "chunks": 0,
            }
        target_path.write_text(frontmatter.dumps(post), encoding="utf-8")
        saved_paths.append(str(target_path.relative_to(settings.repo.repo_path)))
    elif ext in {".xlsx", ".xls"}:
        body_bytes = await file.read()
        body_text = _extract_xlsx_text(body_bytes)
        fm = {
            "id": id,
            "title": title,
            "category": category,
            "tags": [t.strip() for t in tags.split(",") if t.strip()],
            "version": version or "0.1.0",
            "contacts": contact_list,
            "related_units": [],
            "systems": [],
        }
        target_path = target_dir / f"{id}.md"
        post = frontmatter.Post(body_text, **fm)
        if dry_run:
            return {
                "message": "Dry run only - no files written",
                "paths": [str(target_path.relative_to(settings.repo.repo_path))],
                "preview_text": body_text[:1200],
                "indexed": 0,
                "skipped": 0,
                "deleted": 0,
                "chunks": 0,
            }
        target_path.write_text(frontmatter.dumps(post), encoding="utf-8")
        saved_paths.append(str(target_path.relative_to(settings.repo.repo_path)))
    else:
        raise HTTPException(status_code=400, detail="Only .md, .pdf, .xlsx/.xls uploads are supported.")

    ingest_info = ingest_kb(force=True)
    pipeline.refresh_indexes()
    return {
        "message": "File(s) uploaded and indexed",
        "paths": saved_paths,
        **ingest_info["summary"],
    }


@app.get("/inspect/units")
def inspect_units(
    category: Optional[str] = Query(default=None),
    tag: Optional[str] = Query(default=None),
    updated_since: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
):
    store = get_state_store()
    return {
        "items": store.list_units(category, tag, updated_since, limit, offset),
        "limit": limit,
        "offset": offset,
    }


@app.get("/inspect/unit/{unit_id}")
def inspect_unit(unit_id: str):
    store = get_state_store()
    unit = store.get_unit(unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    chunks = [row for row in store.list_chunks() if row["knowledge_unit_id"] == unit_id]
    return {"unit": unit, "chunks": chunks}


__all__ = ["app"]
