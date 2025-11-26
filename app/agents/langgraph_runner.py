"""LangGraph-based orchestration for the AI-KMS assistant."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.metrics import log_orchestrator_metrics
from app.rag.intent import IntentType, analyse_intent
from app.rag.pipeline import RAGPipeline


class GraphState(TypedDict, total=False):
    """Shared state object passed between LangGraph nodes."""

    question: str
    intent: str
    params: Dict[str, Any]
    pipeline_result: Dict[str, Any]
    confidence: str
    handled: bool
    metrics: Dict[str, Any]


def _detect_intent(state: GraphState) -> GraphState:
    question = state.get("question", "")
    intent = analyse_intent(question)
    intent_label = str(intent.value if isinstance(intent, IntentType) else intent)
    state["intent"] = intent_label
    metrics = state.setdefault("metrics", {})
    metrics["intent"] = intent_label
    params = state.setdefault("params", {})
    if intent_label == IntentType.LANGGRAPH.value:
        current = params.get("min_score_override", 0.15)
        params["min_score_override"] = min(current if current is not None else 0.15, 0.1)
    if intent_label == IntentType.WELLNESS.value:
        params["mode"] = "wellness"
    if intent_label == IntentType.WORLD.value:
        params["mode"] = "world"
    if intent_label == "ops":
        params["debug"] = True
    return state


def _resolve_confidence(result: Dict[str, Any]) -> str:
    if result.get("confidence"):
        return str(result["confidence"])
    sources: List[Dict[str, str]] = result.get("sources", []) or []
    if len(sources) >= 3:
        return "high"
    if len(sources) == 0:
        return "low"
    return "medium"


class LangGraphCoordinator:
    """Wraps LangGraph orchestration around the existing RAG pipeline."""

    def __init__(self, pipeline: Optional[RAGPipeline] = None):
        self.pipeline = pipeline or RAGPipeline()
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(GraphState)

        def intent_node(state: GraphState) -> GraphState:
            return _detect_intent(state)

        def special_node(state: GraphState) -> GraphState:
            intent_label = state.get("intent")
            params = state.get("params") or {}
            metrics = state.setdefault("metrics", {})
            if intent_label in {
                IntentType.SMALL_TALK.value,
                IntentType.GRATITUDE.value,
                IntentType.WELLNESS.value,
                IntentType.WORLD.value,
                IntentType.CLARIFICATION.value,
            }:
                result = self.pipeline.answer_question(
                    state["question"],
                    top_k=params.get("top_k"),
                    debug=params.get("debug", False),
                    history=params.get("history"),
                    model=params.get("model"),
                    min_score_override=params.get("min_score_override"),
                    allow_external=params.get("allow_external", False),
                )
                state["pipeline_result"] = result
                state["confidence"] = _resolve_confidence(result)
                state["handled"] = True
                metrics["handled_by"] = "special"
            else:
                state["handled"] = False
            return state

        def rag_node(state: GraphState) -> GraphState:
            if state.get("handled"):
                return state
            params = state.get("params") or {}
            result = self.pipeline.answer_question(
                state["question"],
                top_k=params.get("top_k"),
                debug=params.get("debug", False),
                history=params.get("history"),
                model=params.get("model"),
                min_score_override=params.get("min_score_override"),
                allow_external=params.get("allow_external", False),
            )
            state["pipeline_result"] = result
            state["confidence"] = _resolve_confidence(result)
            metrics = state.setdefault("metrics", {})
            metrics["handled_by"] = "rag"
            return state

        def gate_node(state: GraphState) -> GraphState:
            confidence = state.get("confidence", "medium")
            result = state.get("pipeline_result", {})
            debug = result.get("debug") or {}
            debug.setdefault("orchestrator", {})
            debug["orchestrator"]["intent"] = state.get("intent", "general")
            debug["orchestrator"]["confidence"] = confidence
            result["debug"] = debug
            state["pipeline_result"] = result
            try:
                log_orchestrator_metrics(
                    intent=state.get("intent", "unknown"),
                    handled_by=state.get("metrics", {}).get("handled_by", "unknown"),
                    confidence=confidence,
                    source_type=result.get("source_type"),
                    allow_external=state.get("params", {}).get("allow_external"),
                    extras={"question_len": len(state.get("question", ""))},
                )
            except Exception:
                pass
            return state

        graph.add_node("detect_intent", intent_node)
        graph.add_node("handle_special", special_node)
        graph.add_node("run_rag", rag_node)
        graph.add_node("confidence_gate", gate_node)
        graph.set_entry_point("detect_intent")
        graph.add_edge("detect_intent", "handle_special")
        graph.add_edge("handle_special", "run_rag")
        graph.add_edge("run_rag", "confidence_gate")
        graph.add_edge("confidence_gate", END)
        return graph.compile()

    def answer(
        self,
        question: str,
        *,
        top_k: Optional[int] = None,
        debug: bool = False,
        history: Optional[List[Dict[str, str]]] = None,
        model: Optional[str] = None,
        min_score_override: Optional[float] = None,
        allow_external: bool = False,
    ) -> Dict[str, Any]:
        params = {
            "top_k": top_k,
            "debug": debug,
            "history": history,
            "model": model,
            "min_score_override": min_score_override,
            "allow_external": allow_external,
        }
        state: GraphState = {"question": question, "params": params}
        final_state = self.graph.invoke(state)
        return final_state["pipeline_result"]


__all__ = ["LangGraphCoordinator"]
