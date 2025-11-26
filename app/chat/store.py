"""SQLite-backed chat session store."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from app.core.config import get_settings


class ChatStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.ensure_schema()

    def ensure_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                name TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES chat_sessions(id)
            )
            """
        )
        self._conn.commit()

    def create_session(self, name: Optional[str] = None) -> Dict[str, str]:
        session_id = uuid4().hex
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO chat_sessions(id, name, created_at) VALUES (?, ?, ?)",
            (session_id, name, datetime.utcnow().isoformat()),
        )
        self._conn.commit()
        return {"session_id": session_id, "name": name}

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, object]] = None,
    ) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO chat_messages(session_id, role, content, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                json.dumps(metadata or {}),
                datetime.utcnow().isoformat(),
            ),
        )
        self._conn.commit()

    def get_history(self, session_id: str, limit: int = 50) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT role, content FROM chat_messages WHERE session_id=? ORDER BY created_at ASC LIMIT ?",
            (session_id, limit),
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]

    def clear_session(self, session_id: str) -> None:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM chat_messages WHERE session_id=?", (session_id,))
        cur.execute("DELETE FROM chat_sessions WHERE id=?", (session_id,))
        self._conn.commit()

    def load_session(self, session_id: str, limit: int = 100) -> Optional[Dict[str, object]]:
        cur = self._conn.cursor()
        cur.execute("SELECT id, name, created_at FROM chat_sessions WHERE id=?", (session_id,))
        session = cur.fetchone()
        if not session:
            return None
        cur.execute(
            "SELECT role, content, metadata_json FROM chat_messages WHERE session_id=? ORDER BY created_at ASC LIMIT ?",
            (session_id, limit),
        )
        messages = []
        for row in cur.fetchall():
            metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
            messages.append({"role": row["role"], "content": row["content"], "metadata": metadata})
        return {
            "session_id": session_id,
            "name": session["name"],
            "created_at": session["created_at"],
            "messages": messages,
        }

    def session_exists(self, session_id: str) -> bool:
        cur = self._conn.cursor()
        cur.execute("SELECT 1 FROM chat_sessions WHERE id=?", (session_id,))
        return cur.fetchone() is not None


_chat_store: Optional[ChatStore] = None


def get_chat_store() -> ChatStore:
    global _chat_store
    if _chat_store is None:
        settings = get_settings()
        _chat_store = ChatStore(settings.index.sqlite_path)
    return _chat_store


__all__ = ["ChatStore", "get_chat_store"]
