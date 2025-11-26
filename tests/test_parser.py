from pathlib import Path

from app.kb import parser


def build_markdown() -> str:
    return """---\nid: PE-001\ntitle: Prompt Engineering Fundamentals\ncategory: concept\ntags: [prompting, LLMs]\nversion: 1.2.0\nupdated_at: 2025-11-17\ncreated_at: 2025-10-01\nauthor: Shailesh\nsource_repo: sample\nconfidence: high\n---\n\n# Summary\nShort description.\n\n# Details\nMore text here about prompt engineering.\n"""


def test_parse_file(tmp_path):
    repo = tmp_path / "repo"
    file_path = repo / "kb" / "sample.md"
    file_path.parent.mkdir(parents=True)
    file_path.write_text(build_markdown())
    parsed = parser.parse_file(file_path, str(repo))
    assert parsed is not None
    unit, file_hash = parsed
    assert unit.id == "PE-001"
    assert unit.sections.get("summary")
    assert file_hash


def test_chunk_unit(tmp_path):
    repo = tmp_path / "repo"
    file_path = repo / "kb" / "sample.md"
    file_path.parent.mkdir(parents=True)
    file_path.write_text(build_markdown())
    parsed = parser.parse_file(file_path, str(repo))
    assert parsed is not None
    unit, _ = parsed
    chunks = parser.chunk_unit(unit, chunk_size=20, overlap=5)
    assert chunks
    # ensure chunk metadata carries essential attributes
    first_chunk = next(iter(chunks.values()))
    assert first_chunk.metadata["knowledge_unit_id"] == unit.id
