from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    login: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)


class AuthUser(BaseModel):
    id: str
    login: str
    fullName: str | None


class AuthResponse(BaseModel):
    accessToken: str
    user: AuthUser
