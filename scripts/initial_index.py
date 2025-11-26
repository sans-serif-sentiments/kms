"""CLI helper to sync and index the knowledge base."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.kb.ingestion import ingest_kb


def main():  # pragma: no cover
    result = ingest_kb(force=True)
    print(result)


if __name__ == "__main__":
    main()
