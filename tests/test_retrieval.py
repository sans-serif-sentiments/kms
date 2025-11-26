from app.kb.retrieval import HybridRetriever


def test_retrieve_no_chunks(monkeypatch):
    retriever = HybridRetriever()
    result = retriever.retrieve("What is knowledge management?")
    assert result.query.startswith("what is")
    assert result.selected_chunks == []
    assert set(result.debug.keys()) == {"lexical", "vector", "fused"}
