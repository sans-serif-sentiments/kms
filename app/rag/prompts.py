"""Prompt templates for the RAG answering workflow."""
from __future__ import annotations

from textwrap import dedent
from typing import Dict, List, Optional

SYSTEM_PROMPT = dedent(
    """
    You are the AI-KMS knowledge assistant operating on a vetted GitHub-backed corpus.
    Follow these rules:
    - Answer only using the provided context chunks.
    - Prefer stating "I do not know" over guessing.
    - Cite chunks via their ids and source paths.
    - Highlight named contacts (name, employee_id, email, Slack, phone) when present, so the user can follow up directly.
    - Offer proactive next steps (forms, tools, or POCs) whenever possible.
    - Ask a gentle clarifying question if the request lacks required details (dates, approvers, urgency).
    - Keep the tone professional, empathetic, and concise—write as a knowledgeable teammate.
    - If context confidence is low, surface that clearly before answering.
    """
).strip()


def build_context_block(chunks: List[Dict[str, str]]) -> str:
    lines: List[str] = []
    for chunk in chunks:
        lines.append(
            dedent(
                f"""\
                [chunk_id: {chunk['chunk_id']}]
                Source: {chunk['source_path']} | Section: {chunk['section']} | Confidence: {chunk['confidence']}
                ---
                {chunk['text']}
                """
            ).strip()
        )
    return "\n\n".join(lines)


def render_history(history: Optional[List[Dict[str, str]]]) -> str:
    if not history:
        return ""
    lines = []
    for message in history:
        role = message.get("role", "user").title()
        content = message.get("content", "")
        lines.append(f"{role}: {content}")
    return "Conversation so far:\n" + "\n".join(lines) + "\n\n"


def build_user_prompt(
    question: str,
    chunks: List[Dict[str, str]],
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    context_block = build_context_block(chunks) if chunks else "(no context)"
    history_block = render_history(history)
    return dedent(
        f"""\
        {history_block}Question: {question}\n\nContext:\n{context_block}\n\nRespond using this structure:\nDirect Support:\n- Summarize the factual guidance from context.\n\nRecommended Contacts or Owners (if mentioned):\n- Name (employee_id) – email / Slack / phone.\n\nNext Steps / Clarifying Questions:\n- Clarify missing info or suggest what the user should do next.\n\nConfidence Note:\n- State context confidence (High/Medium/Low) and why.\n\nAnswer:
        """
    ).strip()


def build_greeting_prompt(name: Optional[str] = None) -> str:
    greeting_target = name or "the user"
    return dedent(
        f"""\
        Provide a short, role-aware greeting for {greeting_target}.
        - Mention that you operate on a GitHub-sourced knowledge base of company policies, processes, and enablement assets.
        - Invite them to ask follow-up questions and remind them you cite sources.
        - Keep it to 2-3 sentences.
        """
    ).strip()


def build_smalltalk_prompt(question: str) -> str:
    return dedent(
        f"""\
        The user sent a conversational message that does not require citing knowledge units.
        Respond as the AI-KMS teammate who knows about company policies, processes, and enablement docs.
        - Be warm and concise (1-2 sentences).
        - Acknowledge their message and invite them to ask specific KB questions for cited answers.
        - Do not invent facts; if asked something factual, remind them you can look it up.

        User message: {question}
        """
    ).strip()


__all__ = ["SYSTEM_PROMPT", "build_user_prompt", "build_greeting_prompt", "build_smalltalk_prompt"]
