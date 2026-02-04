from __future__ import annotations

import uuid
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Index, func, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from ..db.base import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role = Column(
        Enum("user", "assistant", "system", "tool", name="messages_role_enum"),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    metadata_json = Column("metadata", JSONB, nullable=True)
    tool_calls = Column("toolCalls", JSONB, nullable=True)
    tool_call_id = Column("toolCallId", String, nullable=True)
    created_at = Column("createdAt", DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")


Index("ix_messages_session_created", Message.session_id, Message.created_at)
Index("ix_messages_session", Message.session_id)
