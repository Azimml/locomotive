from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..core.security import create_access_token
from ..services.users import UsersService


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UsersService(db)

    def login(self, login: str, password: str) -> dict:
        user = self.users.find_by_login(login)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Login yoki parol noto'g'ri",
            )

        if not self.users.validate_password(user, password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Login yoki parol noto'g'ri",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Foydalanuvchi faol emas",
            )

        access_token = create_access_token(subject=user.id, login=user.login)
        return {
            "accessToken": access_token,
            "user": {
                "id": str(user.id),
                "login": user.login,
                "fullName": user.full_name,
            },
        }

    def validate_user(self, user_id: str) -> dict | None:
        user = self.users.find_by_id(user_id)
        if not user:
            return None
        return {
            "id": user.id,
            "login": user.login,
            "fullName": user.full_name,
            "isActive": user.is_active,
        }
