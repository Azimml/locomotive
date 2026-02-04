from __future__ import annotations

import uuid
from sqlalchemy import Boolean, Column, DateTime, String, func, Index
from sqlalchemy.orm import relationship

from ..db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    login = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    chat_sessions = relationship("ChatSession", back_populates="user")


Index("ix_users_login", User.login)
