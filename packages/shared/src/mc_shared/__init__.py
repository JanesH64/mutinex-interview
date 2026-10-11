from datetime import date
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class UserRole(StrEnum):
    DIRECTOR = "DIRECTOR"
    LEAD = "LEAD"
    CREW = "CREW"


class MissionStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


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


class UserOut(BaseModel):
    id: UUID
    username: str
    display_name: str
    role: UserRole


class ForbiddenError(BaseModel):
    role: UserRole
    rule: str


class SkillOut(BaseModel):
    id: UUID
    name: str
    description: str | None


class MissionCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def check_dates(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class SlotOut(BaseModel):
    id: UUID
    position: int
    skill_id: UUID
    skill_name: str
    min_level: int


class MissionOut(BaseModel):
    id: UUID
    title: str
    description: str | None
    status: MissionStatus
    start_date: date
    end_date: date
    lead_id: UUID
    lead_username: str
    requires_additional_director: bool
    slots: list[SlotOut]


class MissionSummary(BaseModel):
    id: UUID
    title: str
    status: MissionStatus
    start_date: date
    end_date: date
    lead_username: str
    requires_additional_director: bool
