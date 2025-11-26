"""Lightweight intent heuristics used to route chat requests."""
from __future__ import annotations

from enum import Enum
import re
from typing import Set


class IntentType(str, Enum):
    """Simple intent labels so the pipeline can branch."""

    SMALL_TALK = "small_talk"
    GRATITUDE = "gratitude"
    LANGGRAPH = "langgraph"
    CLARIFICATION = "clarification"
    WELLNESS = "wellness"
    HR = "hr"
    FINANCE = "finance"
    SALES = "sales"
    IT = "it"
    PRODUCT = "product"
    WORLD = "world"
    GENERAL = "general"


SMALL_TALK_TERMS: Set[str] = {
    "hi",
    "hello",
    "hey",
    "hola",
    "ola",
    "yo",
    "good morning",
    "good evening",
    "sup",
}
GRATITUDE_TERMS: Set[str] = {"thanks", "thank you", "thx", "tysm"}
LANGGRAPH_TERMS: Set[str] = {"langgraph", "lang graph", "lg-"}
WELLNESS_TERMS: Set[str] = {"mental health", "burnout", "therapy", "stress", "eap", "wellness"}
WORLD_TERMS: Set[str] = {
    "economy",
    "world",
    "global problem",
    "news",
    "what happened",
    "explain",
    "define",
    "definition",
    "what is",
    "what's",
    "who is",
    "who was",
    "on the internet",
}
HR_TERMS: Set[str] = {
    "pto",
    "leave",
    "benefit",
    "benefits",
    "wellbeing",
    "wellness",
    "vacation",
    "hr",
    "hr-",
    "policy",
    "policies",
    "onboarding",
    "new hire",
    "employee handbook",
}
FINANCE_TERMS: Set[str] = {"budget", "forecast", "finance", "fin-", "revops", "revenue"}
SALES_TERMS: Set[str] = {"sales", "pipeline", "escalation", "customer", "cs", "gtd", "deal", "quota"}
IT_TERMS: Set[str] = {"access", "device", "it-", "okta", "sso", "jamf", "ticket", "incident"}
PRODUCT_TERMS: Set[str] = {"product", "roadmap", "pd-", "feature", "langgraph", "control tower", "initiative"}


def _contains_term(normalized: str, term: str) -> bool:
    pattern = rf"\b{re.escape(term)}\b"
    return bool(re.search(pattern, normalized))


def analyse_intent(question: str) -> IntentType:
    """Return the coarse intent for an incoming question."""

    normalized = re.sub(r"[^a-z0-9\s]", " ", question.strip().lower())
    normalized = re.sub(r"\s+", " ", normalized)
    if not normalized:
        return IntentType.SMALL_TALK
    for term in SMALL_TALK_TERMS:
        if _contains_term(normalized, term):
            return IntentType.SMALL_TALK
    for term in GRATITUDE_TERMS:
        if _contains_term(normalized, term):
            return IntentType.GRATITUDE
    for term in LANGGRAPH_TERMS:
        if _contains_term(normalized, term):
            return IntentType.LANGGRAPH
    for term in WELLNESS_TERMS:
        if _contains_term(normalized, term):
            return IntentType.WELLNESS
    if any(_contains_term(normalized, term) for term in WORLD_TERMS):
        return IntentType.WORLD
    if any(_contains_term(normalized, term) for term in HR_TERMS):
        return IntentType.HR
    if any(_contains_term(normalized, term) for term in FINANCE_TERMS):
        return IntentType.FINANCE
    if any(_contains_term(normalized, term) for term in SALES_TERMS):
        return IntentType.SALES
    if any(_contains_term(normalized, term) for term in IT_TERMS):
        return IntentType.IT
    if any(_contains_term(normalized, term) for term in PRODUCT_TERMS):
        return IntentType.PRODUCT
    tokens = [token for token in normalized.replace("?", "").split() if token]
    if len(tokens) <= 3 and "?" not in normalized:
        return IntentType.CLARIFICATION
    return IntentType.GENERAL


__all__ = ["IntentType", "analyse_intent"]
