"""Simple evaluation harness to validate retrieval-answering loop."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import yaml

from app.rag.pipeline import RAGPipeline


def load_dataset(path: Path) -> List[Dict[str, object]]:
    return yaml.safe_load(path.read_text())


def token_overlap(expected: str, answer: str) -> float:
    exp_tokens = set(expected.lower().split())
    ans_tokens = set(answer.lower().split())
    if not exp_tokens:
        return 0.0
    return len(exp_tokens & ans_tokens) / len(exp_tokens)


def run_eval(dataset_path: Path = Path("app/eval/dataset.yaml")) -> List[Dict[str, object]]:
    data = load_dataset(dataset_path)
    pipeline = RAGPipeline()
    results = []
    for item in data:
        rag_result = pipeline.answer_question(item["question"], debug=True)
        overlap = token_overlap(item["expected_answer"], rag_result.get("answer", ""))
        sources = [source["source_path"] for source in rag_result.get("sources", [])]
        expected_sources = item.get("expected_sources", [])
        source_match = bool(set(sources) & set(expected_sources))
        retrieval_summary = summarize_retrieval_debug(rag_result.get("debug", {}))
        results.append(
            {
                "id": item["id"],
                "question": item["question"],
                "overlap": overlap,
                "source_match": source_match,
                "answer": rag_result.get("answer"),
                "sources": sources,
                "retrieval": retrieval_summary,
            }
        )
    return results


def summarize_retrieval_debug(debug: Dict[str, object]) -> Dict[str, object]:
    retrieval_debug = debug.get("retrieval", {}) if debug else {}
    summary: Dict[str, object] = {}
    for stage in ("lexical", "vector", "graph"):
        stage_hits = retrieval_debug.get(stage, []) if isinstance(retrieval_debug, dict) else []
        summary[f"{stage}_hits"] = len(stage_hits)
        summary[f"{stage}_top_score"] = stage_hits[0]["score"] if stage_hits else 0.0
    selected_chunks = debug.get("selected", []) if isinstance(debug, dict) else []
    total_chars = sum(len(chunk.get("text", "")) for chunk in selected_chunks)
    summary["context_chars"] = total_chars
    summary["selected_chunks"] = len(selected_chunks)
    return summary


def main():  # pragma: no cover - CLI helper
    reports = run_eval()
    for report in reports:
        print(f"Question: {report['question']}")
        print(f"Overlap: {report['overlap']:.2f} | Source match: {report['source_match']}")
        print(f"Answer: {report['answer'][:200]}...")
        print("Sources:", report["sources"])
        print("---")


if __name__ == "__main__":  # pragma: no cover
    main()
