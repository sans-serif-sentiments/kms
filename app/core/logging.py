"""Logging utilities providing structured insight into the pipeline."""
from __future__ import annotations

import logging
from typing import Optional


def configure_logging(level: str = "INFO") -> None:
    """Configure global logging format."""

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return module logger."""

    return logging.getLogger(name or "ai_kms")


__all__ = ["configure_logging", "get_logger"]
