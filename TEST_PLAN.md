# AI-KMS Edge Test Matrix

| Area | Test | Steps | Expected |
| --- | --- | --- | --- |
| Ingestion | Missing frontmatter | Create `kb_repo/kb/foo.md` without `id/title/category`, run `make index` | File skipped; warning logged; process continues |
| Ingestion | Invalid category | Set category outside enum, run `make index` | Warning + skip |
| Ingestion | Large file | Add 1MB markdown, run `make index` | Chunking completes; SQLite/Chroma entries created |
| Embeddings | Model folder missing | Rename `models/bge-small-en`, run `make index` | Hashing fallback warning; indexing still works |
| Embeddings | Corrupt weights | Delete `model.safetensors`, run uvicorn | Startup fails with guidance to reinstall via git-lfs |
| Retrieval | High threshold | POST `/query` with `min_score_threshold=0.9` | Response uses fallback message, no hallucinations |
| Retrieval | Low threshold | POST `/query` with `min_score_threshold=0` | Returns best-chunk answer with sources |
| Retrieval | No matches | Ask topic not in KB | Friendly “not in KB” response |
| RAG small talk | Ask "hello" | Short greeting reply, no citations |
| Sessions | Invalid session id | POST `/query` with random `session_id` | 404 `session_not_found` |
| API | Missing payload | POST `/query` with `{}` | HTTP 422 validation error |
| API | `/sync` run | POST `/sync` | Returns pull result + summary |
| Frontend | Backend down | stop uvicorn, send message | UI shows “Failed to fetch” toast |
| Frontend | Advanced drawer | Toggle, change min score, send | Query uses new value (see debug block) |
| Frontend | Action buttons | Copy/Draft/Download per message | Clipboard/email/download triggered |
| Frontend | Transcript export | Click “Export transcript” | Downloads `.txt` with conversation |
| End-to-end | HR leave query | Ask “How do I apply for PTO?” | Response cites HR-002 and lists HR contacts |
| End-to-end | Security incident | “What happens if SEV1 incident?” | Response cites SEC-002 |
| End-to-end | Finance travel | “Hotel cap tier-1?” | Response cites FIN-001 |
| Performance | Parallel queries | Send 10 curl requests simultaneously | All return JSON < 2s |
| Observability | `/health` | GET `/health` before/after index | `units` increments |

Run these before releases:
1. `make index`
2. `uvicorn app.api.routes:app --host 127.0.0.1 --port 8300`
3. `npm run dev`
4. Execute curl/Postman scripts above.
