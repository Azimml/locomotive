from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import text

from ..models.user import User


class UsersService:
    def __init__(self, db: Session):
        self.db = db

    def find_by_login(self, login: str) -> User | None:
        return self.db.query(User).filter(User.login == login).first()

    def find_by_id(self, user_id: str) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def create(self, login: str, password: str, full_name: str | None = None) -> User:
        
        self.db.execute(
            text(
                """
                INSERT INTO users (id, login, password, full_name, is_active)
                VALUES (gen_random_uuid(), :login, crypt(:password, gen_salt('bf')), :full_name, true)
                """
            ),
            {"login": login, "password": password, "full_name": full_name},
        )
        self.db.commit()
        return self.find_by_login(login)

    def validate_password(self, user: User, password: str) -> bool:
        result = self.db.execute(
            text(
                """
                SELECT 1
                FROM users
                WHERE id = :user_id
                  AND password = crypt(:password, password)
                """
            ),
            {"user_id": user.id, "password": password},
        ).first()
        return result is not None

    def exists(self, login: str) -> bool:
        return self.db.query(User).filter(User.login == login).count() > 0
