"""End-to-end RAG pipeline orchestrating retrieval and LLM generation."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from app.core.config import get_settings
from app.kb.indexing import get_state_store
from app.kb.models import RetrievalChunk
from app.kb.retrieval import HybridRetriever
from app.rag.intent import IntentType, analyse_intent
from app.rag.llm_client import LLMClient
from app.rag import prompts

LOGGER = logging.getLogger(__name__)


class RAGPipeline:
    PROBE_KEYWORDS = (
        "leave",
        "vacation",
        "time off",
        "pto",
        "absence",
    )
    def __init__(
        self,
        retriever: Optional[HybridRetriever] = None,
        llm_client: Optional[LLMClient] = None,
        default_model: Optional[str] = None,
    ):
        settings = get_settings()
        self.settings = settings
        self.retriever = retriever or HybridRetriever()
        model = default_model or settings.llm.default_model
        base_url = settings.llm.base_url
        self.allowed_models = settings.llm.allowed_models
        self.default_model = model
        self.llm = llm_client or LLMClient(model=model, base_url=base_url)
        general_model = settings.llm.general_model or model
        if general_model == model:
            self.world_llm = self.llm
        else:
            self.world_llm = LLMClient(model=general_model, base_url=base_url)
        self.max_context_chars = settings.retrieval.max_context_chars

    def _format_chunks(self, chunks) -> List[Dict[str, str]]:
        formatted = []
        repo_url = self.settings.repo.repo_url
        branch = self.settings.repo.branch
        for chunk in chunks:
            metadata = chunk.chunk.metadata
            source_path = metadata.get("source_path", chunk.chunk.source_path)
            web_url = self._build_web_url(source_path, repo_url, branch)
            formatted.append(
                {
                    "chunk_id": chunk.chunk.chunk_id,
                    "source_path": source_path,
                    "section": metadata.get("section", chunk.chunk.section_name),
                    "confidence": metadata.get("confidence", "unknown"),
                    "text": chunk.chunk.text,
                    "title": metadata.get("title", ""),
                    "knowledge_unit_id": metadata.get("knowledge_unit_id", chunk.chunk.knowledge_unit_id),
                    "version": metadata.get("version", ""),
                    "updated_at": metadata.get("updated_at", ""),
                    "web_url": web_url,
                }
            )
        return formatted

    def answer_question(
        self,
        question: str,
        top_k: Optional[int] = None,
        debug: bool = False,
        history: Optional[List[Dict[str, str]]] = None,
        model: Optional[str] = None,
        min_score_override: Optional[float] = None,
        allow_external: bool = False,
    ) -> Dict[str, object]:
        model_name = model or self.default_model
        intent = analyse_intent(question)
        if intent in (IntentType.SMALL_TALK, IntentType.GRATITUDE):
            answer = self._generate_small_talk(question)
            response = {
                "answer": answer,
                "sources": [],
                "model": model_name,
                "confidence": "medium",
                "source_type": "conversation",
            }
            if debug:
                response["debug"] = {"notice": "small_talk"}
            return response
        if intent == IntentType.CLARIFICATION:
            result = self._clarification_prompt(question)
            result["model"] = model_name
            result.setdefault("source_type", "conversation")
            if debug:
                result["debug"] = {"notice": "clarification"}
            return result
        if intent == IntentType.WELLNESS:
            result = self._wellness_prompt(question, model_name)
            result["model"] = model_name
            return result
        if intent == IntentType.WORLD:
            if allow_external:
                result = self._world_prompt(question, model_name)
            else:
                result = self._external_blocked_answer()
            result["model"] = model_name
            return result
        score_override = min_score_override
        allowed_prefixes: Optional[List[str]] = None
        if intent == IntentType.LANGGRAPH and score_override is None:
            score_override = min(self.settings.retrieval.min_score_threshold, 0.1)
            allowed_prefixes = ["LG-"]
        elif intent == IntentType.WELLNESS or intent == IntentType.HR:
            if score_override is None:
                score_override = min(self.settings.retrieval.min_score_threshold, 0.02)
            allowed_prefixes = ["HR-", "EN-", "CO-", "PR-"]
        elif intent == IntentType.FINANCE:
            allowed_prefixes = ["FIN-", "SALES-", "CP-"]
        elif intent == IntentType.SALES:
            allowed_prefixes = ["SALES-", "PT-", "PR-", "CO-"]
        elif intent == IntentType.IT:
            allowed_prefixes = ["IT-", "OPS-", "PR-"]
        elif intent == IntentType.PRODUCT:
            allowed_prefixes = ["PD-", "PR-", "PT-"]
        retrieval = self.retriever.retrieve(question, score_override, allowed_prefixes)
        selected = retrieval.selected_chunks
        if not selected:
            if intent in (IntentType.SMALL_TALK, IntentType.GRATITUDE):
                answer = self._generate_small_talk(question)
                response = {"answer": answer, "sources": [], "model": model_name, "confidence": "medium"}
                if debug:
                    response["debug"] = {"notice": "small_talk"}
                return response
            if allow_external:
                result = self._world_prompt(question, model_name)
                result["model"] = model_name
                return result
            fallback = self._fallback_answer([], question, allowed_prefixes, intent)
            return {
                "answer": fallback,
                "sources": [],
                "debug": retrieval.debug if debug else None,
                "model": model_name,
                "confidence": "low",
                "source_type": "internal",
            }
        if top_k:
            selected = selected[:top_k]
        selected = self._apply_context_budget(selected)
        formatted_chunks = self._format_chunks(selected)
        low_confidence = all(chunk["confidence"] == "low" for chunk in formatted_chunks)
        user_prompt = prompts.build_user_prompt(question, formatted_chunks, history)
        normalized_question = question.lower()
        if any(keyword in normalized_question for keyword in self.PROBE_KEYWORDS):
            user_prompt += "\n\nReminder: The user might be discussing leave/time-off. Confirm dates or urgency if not provided."
        if low_confidence:
            user_prompt += "\n\nContext confidence is low; prefer stating this explicitly."
        try:
            answer = self.llm.generate_answer(prompts.SYSTEM_PROMPT, user_prompt, model_override=model_name)
        except Exception as exc:  # pragma: no cover - network failure
            LOGGER.error("LLM generation failed: %s", exc)
            answer = self._fallback_answer(formatted_chunks, question, allowed_prefixes, intent)
        sources = [
            {
                "knowledge_unit_id": chunk["knowledge_unit_id"],
                "title": chunk["title"],
                "source_path": chunk["source_path"],
                "section": chunk["section"],
                "version": chunk["version"],
                "updated_at": chunk["updated_at"],
                "web_url": chunk.get("web_url"),
            }
            for chunk in formatted_chunks
        ]
        confidence = self._score_confidence(formatted_chunks)
        result = {"answer": answer, "sources": sources, "confidence": confidence, "source_type": "internal"}
        if debug:
            result["debug"] = {
                "retrieval": retrieval.debug,
                "selected": formatted_chunks,
            }
        result["model"] = model_name
        return result

    def refresh_indexes(self) -> None:
        """Force the retriever to rebuild lexical and graph indexes."""

        self.retriever.refresh_sources()

    def _fallback_answer(
        self,
        chunks: List[Dict[str, str]],
        question: str,
        allowed_prefixes: Optional[List[str]] = None,
        intent: Optional[IntentType] = None,
    ) -> str:
        if not chunks:
            catalog_hint = self._suggest_units(allowed_prefixes)
            if catalog_hint:
                return (
                    f"I don't have a precise answer for \"{question}\" yet. Here are related KB entries you can open:\n"
                    + catalog_hint
                    + "\nIf you meant something else, share the KB ID or policy name."
                )
            return (
                f"I don't have vetted knowledge about \"{question}\" in the current KB. "
                "The catalog mainly covers HR, Finance, Security, and operational policies. "
                "If this topic should live here, please share the KB ID or policy name so I can look it up."
            )
        bullet_lines = [
            f"- ({chunk['knowledge_unit_id']} · {chunk['section']}) {chunk['text'][:280]}..."
            for chunk in chunks
        ]
        return (
            "I could not verify the full answer with high confidence, but here are the most relevant snippets. "
            "Please double-check the cited docs:\n"
            + "\n".join(bullet_lines)
            + "\n\nPlease review the cited documents for precise details."
        )

    def generate_greeting(self, name: Optional[str] = None) -> Dict[str, str]:
        target = name or "there"
        message = (
            f"Hi {target}! I'm your AI-KMS knowledge assistant with access to our GitHub-sourced policies, processes, "
            "and enablement docs. Ask me anything and I'll cite the relevant sources or let you know when we need to add a KB entry."
        )
        return {"message": message}

    def _suggest_units(self, allowed_prefixes: Optional[List[str]]) -> str:
        if not allowed_prefixes:
            return ""
        try:
            store = get_state_store()
            units = store.list_all_units()
        except Exception:
            return ""
        matches = [
            (u["id"], u.get("title", ""))
            for u in units
            if any(u.get("id", "").startswith(prefix) for prefix in allowed_prefixes)
        ]
        if not matches:
            return ""
        matches = sorted(matches)[:6]
        return "\n".join(f"- {uid}: {title}" for uid, title in matches)

    def _is_small_talk(self, question: str) -> bool:
        intent = analyse_intent(question)
        return intent in (IntentType.SMALL_TALK, IntentType.GRATITUDE)

    def _generate_small_talk(self, question: str) -> str:
        prompt = prompts.build_smalltalk_prompt(question)
        try:
            return self.llm.generate_answer(prompts.SYSTEM_PROMPT, prompt, model_override=self.default_model)
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("Small talk generation failed: %s", exc)
            return (
                "Hi there! I'm your AI-KMS assistant with access to our GitHub knowledge base. "
                "Ask me about policies, processes, or enablement docs and I'll cite my sources."
            )

    def _apply_context_budget(self, chunks: List[RetrievalChunk]) -> List[RetrievalChunk]:
        """Trim or drop chunks so prompts stay within the configured budget."""

        if self.max_context_chars <= 0:
            return chunks
        budget = self.max_context_chars
        trimmed: List[RetrievalChunk] = []
        for chunk in chunks:
            if budget <= 0:
                break
            text = chunk.chunk.text
            if len(text) > budget:
                chunk.chunk.text = text[:budget]
                budget = 0
            else:
                budget -= len(text)
            trimmed.append(chunk)
        return trimmed

    def _clarification_prompt(self, question: str) -> Dict[str, object]:
        message = (
            "I want to help, but I need a bit more detail. "
            "Could you share the specific topic, policy ID, or workflow you're asking about?"
        )
        return {"answer": message, "sources": [], "confidence": "low", "source_type": "conversation"}

    def _wellness_prompt(self, question: str, model_name: str) -> Dict[str, object]:
        fallback = (
            "I'm not a clinician, but I can connect you to our HR wellness resources. "
            "You can reach the HR wellness alias or EAP hotline (see HR-003) for confidential support."
        )
        try:
            prompt = (
                "The user is asking about wellness or mental health. "
                "Respond with empathy, cite HR-003, and list HR/EAP contacts. "
                f"User message: {question}"
            )
            answer = self.llm.generate_answer(
                prompts.SYSTEM_PROMPT, prompt, model_override=model_name
            )
        except Exception:
            answer = fallback
        sources = [
            {
                "knowledge_unit_id": "HR-003",
                "title": "Employee Mental Health & Support Policy",
                "source_path": "kb/policies/HR-003-mental-health-support.md",
                "section": "Summary",
                "version": "1.0.0",
                "updated_at": "2025-02-21",
            }
        ]
        return {"answer": answer, "sources": sources, "confidence": "medium", "source_type": "internal"}

    def _world_prompt(self, question: str, model_name: str) -> Dict[str, object]:
        prompt = (
            "The user is asking about a general or world topic. "
            "Give a concise, factual answer. Do NOT mention, speculate about, or invite org-specific follow-ups "
            "unless the user explicitly asks for org context. "
            "Keep it short and focused solely on the question. "
            f"Question: {question}"
        )
        try:
            answer = self.world_llm.generate_answer(
                prompts.SYSTEM_PROMPT, prompt, model_override=self.world_llm.model
            )
        except Exception:
            answer = (
                "I can share a general perspective, but I don't store public news in my KB. "
                "Tell me if you want an org-specific angle."
            )
        return {"answer": answer, "sources": [], "confidence": "medium", "source_type": "external"}

    def _external_blocked_answer(self) -> Dict[str, object]:
        message = (
            "This sounds like a world or general-knowledge question. External responses are disabled for this session. "
            "Toggle “Allow general knowledge answers” to let me use the general model, or point me to a KB ID to stay grounded."
        )
        return {"answer": message, "sources": [], "confidence": "low", "source_type": "conversation"}

    def _build_web_url(self, source_path: str, repo_url: Optional[str], branch: str) -> Optional[str]:
        if not repo_url or not source_path:
            return None
        base = repo_url.rstrip("/")
        return f"{base}/blob/{branch}/{source_path}"

    def _score_confidence(self, chunks: List[Dict[str, str]]) -> str:
        if not chunks:
            return "low"
        if len(chunks) >= 3:
            return "high"
        return "medium"


__all__ = ["RAGPipeline"]
