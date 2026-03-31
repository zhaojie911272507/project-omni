"""Memory / Persistence Layer for Project Omni.

SQLite-based conversation history, session management, and user preferences.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

import aiosqlite
from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Database path
DB_PATH = os.getenv("DB_PATH", "./data/omni.db")

# Ensure data directory exists
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

# SQLAlchemy setup
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ─────────────────────────────────────────────────────────────────────────────
# Database Models
# ─────────────────────────────────────────────────────────────────────────────


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), index=True, nullable=False)
    platform = Column(String(50), nullable=False)  # cli, wecom, feishu, telegram, etc.
    user_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    title = Column(String(500), nullable=True)
    metadata = Column(JSON, default=dict)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, nullable=False)
    role = Column(String(20), nullable=False)  # system, user, assistant, tool
    content = Column(Text, nullable=True)
    tool_calls = Column(JSON, nullable=True)
    tool_call_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), index=True, nullable=False)
    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# Database Init
# ─────────────────────────────────────────────────────────────────────────────


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


# ─────────────────────────────────────────────────────────────────────────────
# Conversation Management
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ConversationInfo:
    id: int
    session_id: str
    platform: str
    user_id: str | None
    created_at: datetime
    updated_at: datetime
    title: str | None
    message_count: int = 0


class MemoryStore:
    """Main memory store for conversations and preferences."""

    def __init__(self):
        init_db()

    def _get_session(self) -> Session:
        return SessionLocal()

    # ── Conversation CRUD ──────────────────────────────────────────────────

    async def create_conversation(
        self,
        session_id: str,
        platform: str,
        user_id: str | None = None,
        title: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        """Create a new conversation, return its ID."""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """INSERT INTO conversations (session_id, platform, user_id, title, metadata)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_id, platform, user_id, title, json.dumps(metadata or {})),
            )
            await db.commit()
            return cursor.lastrowid

    async def get_conversation(self, conversation_id: int) -> ConversationInfo | None:
        """Get a conversation by ID."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT c.*, COUNT(m.id) as message_count
                   FROM conversations c
                   LEFT JOIN messages m ON c.id = m.conversation_id
                   WHERE c.id = ?
                   GROUP BY c.id""",
                (conversation_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return ConversationInfo(
                id=row["id"],
                session_id=row["session_id"],
                platform=row["platform"],
                user_id=row["user_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                title=row["title"],
                message_count=row["message_count"],
            )

    async def get_conversation_by_session(
        self, session_id: str, platform: str, user_id: str | None = None
    ) -> ConversationInfo | None:
        """Get the most recent conversation for a session."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT c.*, COUNT(m.id) as message_count
                   FROM conversations c
                   LEFT JOIN messages m ON c.id = m.conversation_id
                   WHERE c.session_id = ? AND c.platform = ?
                   GROUP BY c.id
                   ORDER BY c.updated_at DESC
                   LIMIT 1""",
                (session_id, platform),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return ConversationInfo(
                id=row["id"],
                session_id=row["session_id"],
                platform=row["platform"],
                user_id=row["user_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                title=row["title"],
                message_count=row["message_count"],
            )

    async def list_conversations(
        self,
        platform: str | None = None,
        user_id: str | None = None,
        limit: int = 50,
    ) -> list[ConversationInfo]:
        """List conversations with optional filters."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            query = """SELECT c.*, COUNT(m.id) as message_count
                       FROM conversations c
                       LEFT JOIN messages m ON c.id = m.conversation_id"""
            params = []
            where = []
            if platform:
                where.append("c.platform = ?")
                params.append(platform)
            if user_id:
                where.append("c.user_id = ?")
                params.append(user_id)
            if where:
                query += " WHERE " + " AND ".join(where)
            query += " GROUP BY c.id ORDER BY c.updated_at DESC LIMIT ?"
            params.append(limit)

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [
                ConversationInfo(
                    id=row["id"],
                    session_id=row["session_id"],
                    platform=row["platform"],
                    user_id=row["user_id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    title=row["title"],
                    message_count=row["message_count"],
                )
                for row in rows
            ]

    async def update_conversation_title(
        self, conversation_id: int, title: str
    ) -> None:
        """Update conversation title."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, datetime.utcnow().isoformat(), conversation_id),
            )
            await db.commit()

    async def delete_conversation(self, conversation_id: int) -> None:
        """Delete a conversation and its messages."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            await db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            await db.commit()

    # ── Message CRUD ───────────────────────────────────────────────────────

    async def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str | None = None,
        tool_calls: list[dict] | None = None,
        tool_call_id: str | None = None,
    ) -> int:
        """Add a message to a conversation."""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """INSERT INTO messages (conversation_id, role, content, tool_calls, tool_call_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    conversation_id,
                    role,
                    content,
                    json.dumps(tool_calls) if tool_calls else None,
                    tool_call_id,
                ),
            )
            await db.commit()
            # Update conversation timestamp
            await db.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), conversation_id),
            )
            await db.commit()
            return cursor.lastrowid

    async def get_messages(
        self, conversation_id: int, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Get all messages for a conversation."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC"
            if limit:
                query += f" LIMIT {limit}"
            cursor = await db.execute(query, (conversation_id,))
            rows = await cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "role": row["role"],
                    "content": row["content"],
                    "tool_calls": json.loads(row["tool_calls"]) if row["tool_calls"] else None,
                    "tool_call_id": row["tool_call_id"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

    # ── User Preferences ───────────────────────────────────────────────────

    async def set_preference(
        self, user_id: str, key: str, value: str | dict | list
    ) -> None:
        """Set a user preference."""
        value_str = json.dumps(value) if isinstance(value, (dict, list)) else value
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT OR REPLACE INTO user_preferences (user_id, key, value, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (user_id, key, value_str, datetime.utcnow().isoformat()),
            )
            await db.commit()

    async def get_preference(
        self, user_id: str, key: str, default: Any = None
    ) -> Any:
        """Get a user preference."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT value FROM user_preferences WHERE user_id = ? AND key = ?",
                (user_id, key),
            )
            row = await cursor.fetchone()
            if row is None:
                return default
            try:
                return json.loads(row["value"])
            except (json.JSONDecodeError, TypeError):
                return row["value"]

    async def get_all_preferences(self, user_id: str) -> dict[str, Any]:
        """Get all preferences for a user."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT key, value FROM user_preferences WHERE user_id = ?",
                (user_id,),
            )
            rows = await cursor.fetchall()
            result = {}
            for row in rows:
                try:
                    result[row["key"]] = json.loads(row["value"])
                except (json.JSONDecodeError, TypeError):
                    result[row["key"]] = row["value"]
            return result


# Global memory store instance
_memory_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    """Get the global memory store instance."""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store