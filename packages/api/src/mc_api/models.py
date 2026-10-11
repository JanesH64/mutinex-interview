import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from mc_api.db import Base
from mc_shared import MissionStatus, UnavailabilityReason, UserRole


class AssignmentStatus(enum.StrEnum):
    INVITED = "INVITED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # clock_timestamp(): now() is fixed inside a transaction, so it would hide a later update.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.clock_timestamp()
    )


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def _org_id() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, ForeignKey("organization.id"))


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name)


class Organization(Timestamps, Base):
    __tablename__ = "organization"

    id: Mapped[uuid.UUID] = _id()
    name: Mapped[str] = mapped_column(Text)


class AppUser(Timestamps, Base):
    __tablename__ = "app_user"
    __table_args__ = (UniqueConstraint("username"), UniqueConstraint("org_id", "id"))

    id: Mapped[uuid.UUID] = _id()
    org_id: Mapped[uuid.UUID] = _org_id()
    username: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    role: Mapped[UserRole] = mapped_column(_enum(UserRole, "user_role"))


class Skill(Timestamps, Base):
    __tablename__ = "skill"
    __table_args__ = (UniqueConstraint("org_id", "name"), UniqueConstraint("org_id", "id"))

    id: Mapped[uuid.UUID] = _id()
    org_id: Mapped[uuid.UUID] = _org_id()
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)


class CrewSkill(Timestamps, Base):
    __tablename__ = "crew_skill"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "user_id"], ["app_user.org_id", "app_user.id"]),
        ForeignKeyConstraint(["org_id", "skill_id"], ["skill.org_id", "skill.id"]),
        CheckConstraint("level BETWEEN 1 AND 5", name="level_range"),
    )

    org_id: Mapped[uuid.UUID] = _org_id()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    level: Mapped[int] = mapped_column(SmallInteger)


class Unavailability(Timestamps, Base):
    __tablename__ = "unavailability"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "user_id"], ["app_user.org_id", "app_user.id"]),
        CheckConstraint("end_date >= start_date", name="dates"),
    )

    id: Mapped[uuid.UUID] = _id()
    org_id: Mapped[uuid.UUID] = _org_id()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[UnavailabilityReason] = mapped_column(
        _enum(UnavailabilityReason, "unavailability_reason")
    )


class Mission(Timestamps, Base):
    __tablename__ = "mission"
    __table_args__ = (
        UniqueConstraint("org_id", "id"),
        ForeignKeyConstraint(["org_id", "lead_id"], ["app_user.org_id", "app_user.id"]),
        ForeignKeyConstraint(["org_id", "approved_by"], ["app_user.org_id", "app_user.id"]),
        CheckConstraint("end_date >= start_date", name="dates"),
    )

    id: Mapped[uuid.UUID] = _id()
    org_id: Mapped[uuid.UUID] = _org_id()
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    lead_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    status: Mapped[MissionStatus] = mapped_column(_enum(MissionStatus, "mission_status"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MissionRequirement(Timestamps, Base):
    __tablename__ = "mission_requirement"
    __table_args__ = (
        UniqueConstraint("org_id", "mission_id", "id"),
        ForeignKeyConstraint(["org_id", "mission_id"], ["mission.org_id", "mission.id"]),
        ForeignKeyConstraint(["org_id", "skill_id"], ["skill.org_id", "skill.id"]),
        CheckConstraint("min_level BETWEEN 1 AND 5", name="min_level_range"),
        Index(
            "uq_mission_requirement_active_position",
            "mission_id",
            "position",
            unique=True,
            postgresql_where="archived_at IS NULL",
        ),
    )

    id: Mapped[uuid.UUID] = _id()
    org_id: Mapped[uuid.UUID] = _org_id()
    mission_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    position: Mapped[int] = mapped_column(SmallInteger)
    skill_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    min_level: Mapped[int] = mapped_column(SmallInteger)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Assignment(Timestamps, Base):
    __tablename__ = "assignment"
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "mission_id"], ["mission.org_id", "mission.id"]),
        ForeignKeyConstraint(
            ["org_id", "mission_id", "requirement_id"],
            [
                "mission_requirement.org_id",
                "mission_requirement.mission_id",
                "mission_requirement.id",
            ],
        ),
        ForeignKeyConstraint(["org_id", "user_id"], ["app_user.org_id", "app_user.id"]),
        Index(
            "uq_assignment_active_user",
            "mission_id",
            "user_id",
            unique=True,
            postgresql_where="status IN ('INVITED','ACCEPTED')",
        ),
        Index(
            "uq_assignment_active_slot",
            "requirement_id",
            unique=True,
            postgresql_where="status IN ('INVITED','ACCEPTED')",
        ),
    )

    id: Mapped[uuid.UUID] = _id()
    org_id: Mapped[uuid.UUID] = _org_id()
    mission_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    requirement_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    status: Mapped[AssignmentStatus] = mapped_column(_enum(AssignmentStatus, "assignment_status"))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
