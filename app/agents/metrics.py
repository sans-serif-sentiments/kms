"""Lightweight metrics logger for orchestrator events."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

METRICS_PATH = Path("storage/metrics/orchestrator_metrics.csv")


def log_orchestrator_metrics(
    *,
    intent: str,
    handled_by: str,
    confidence: str,
    source_type: Optional[str] = None,
    allow_external: Optional[bool] = None,
    extras: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a single orchestrator event to a CSV for inspection or export to dashboards."""

    try:
        METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": datetime.utcnow().isoformat(),
            "intent": intent,
            "handled_by": handled_by,
            "confidence": confidence,
            "source_type": source_type or "",
            "allow_external": allow_external if allow_external is not None else "",
        }
        if extras:
            for k, v in extras.items():
                row[k] = v
        write_header = not METRICS_PATH.exists()
        with METRICS_PATH.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            if write_header:
                writer.writeheader()
            writer.writerow(row)
    except Exception:
        # Metrics must not break the request path.
        return


__all__ = ["log_orchestrator_metrics", "METRICS_PATH"]
