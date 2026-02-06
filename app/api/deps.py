from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..db.deps import get_db
from ..models.user import User


def get_current_user(db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter(User.login == settings.CHAINLIT_AUTH_USERNAME).first()
    if not user:
        user = User(
            login=settings.CHAINLIT_AUTH_USERNAME,
            password=settings.CHAINLIT_AUTH_PASSWORD,
            full_name=settings.CHAINLIT_AUTH_FULL_NAME,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return {
        "id": user.id,
        "login": user.login,
        "fullName": user.full_name,
        "isActive": user.is_active,
    }
