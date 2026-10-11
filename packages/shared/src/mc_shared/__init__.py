from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class UserRole(StrEnum):
    DIRECTOR = "DIRECTOR"
    LEAD = "LEAD"
    CREW = "CREW"


class Health(BaseModel):
    status: str
    db: str


class LoginRequest(BaseModel):
    username: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class Me(BaseModel):
    id: UUID
    username: str
    display_name: str
    role: UserRole
    org_id: UUID
    org_name: str
