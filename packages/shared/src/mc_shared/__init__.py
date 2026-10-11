from datetime import date, datetime
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


class UnavailabilityReason(StrEnum):
    HOLIDAY = "HOLIDAY"
    SICK = "SICK"
    MEETING = "MEETING"


class AssignmentStatus(StrEnum):
    INVITED = "INVITED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
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
    crew_username: str | None = None
    assignment_status: AssignmentStatus | None = None


class InviteCreate(BaseModel):
    position: int
    username: str = Field(min_length=1)


class SlotCreate(BaseModel):
    skill_id: UUID
    min_level: int = Field(ge=1, le=5)


class MissionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None


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
    approved_by_username: str | None = None
    approved_at: datetime | None = None
    slots: list[SlotOut]


class MissionSummary(BaseModel):
    id: UUID
    title: str
    status: MissionStatus
    start_date: date
    end_date: date
    lead_username: str
    requires_additional_director: bool


class ProfileOut(BaseModel):
    username: str
    display_name: str
    org_name: str


class SkillLevel(BaseModel):
    level: int = Field(ge=1, le=5)


class CrewSkillOut(BaseModel):
    skill_id: UUID
    skill_name: str
    level: int


class UnavailabilityCreate(BaseModel):
    start_date: date
    end_date: date
    reason: UnavailabilityReason

    @model_validator(mode="after")
    def check_dates(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class UnavailabilityOut(BaseModel):
    id: UUID
    start_date: date
    end_date: date
    reason: UnavailabilityReason


class CrewSuggestion(BaseModel):
    user_id: UUID
    username: str
    display_name: str
    level: int
    workload_days: int


class SlotMatch(BaseModel):
    slot: SlotOut
    suggestion: CrewSuggestion | None


class MatchPreview(BaseModel):
    mission_id: UUID
    slots: list[SlotMatch]
