from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


Role = Literal["user", "assistant"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


class SQLiteMemory:
    """Small async wrapper around sqlite3 for per-user dialog memory."""

    def __init__(self, database_path: Path, max_messages: int) -> None:
        self.database_path = database_path
        self.max_messages = max_messages
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    async def add_message(self, user_id: int, role: Role, content: str) -> None:
        await asyncio.to_thread(self._add_message_sync, user_id, role, content)

    async def get_context(self, user_id: int) -> list[Message]:
        return await asyncio.to_thread(self._get_context_sync, user_id)

    async def reset(self, user_id: int) -> None:
        await asyncio.to_thread(self._reset_sync, user_id)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA journal_mode=WAL;")
        connection.execute("PRAGMA foreign_keys=ON;")
        return connection

    def _initialize_sync(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_user_id_id
                ON messages(user_id, id);
                """
            )

    def _add_message_sync(self, user_id: int, role: Role, content: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO messages(user_id, role, content) VALUES (?, ?, ?);",
                (user_id, role, content),
            )
            # Keep only the most recent rows for this Telegram user.
            connection.execute(
                """
                DELETE FROM messages
                WHERE user_id = ?
                  AND id NOT IN (
                    SELECT id
                    FROM messages
                    WHERE user_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                  );
                """,
                (user_id, user_id, self.max_messages),
            )

    def _get_context_sync(self, user_id: int) -> list[Message]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content
                FROM messages
                WHERE user_id = ?
                ORDER BY id ASC;
                """,
                (user_id,),
            ).fetchall()
        return [Message(role=row[0], content=row[1]) for row in rows]

    def _reset_sync(self, user_id: int) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM messages WHERE user_id = ?;", (user_id,))
