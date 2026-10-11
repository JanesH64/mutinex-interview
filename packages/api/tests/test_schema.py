import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from mc_api.models import (
    AppUser,
    Assignment,
    AssignmentStatus,
    CrewSkill,
    Mission,
    MissionRequirement,
    MissionStatus,
    Organization,
    Skill,
    Unavailability,
    UnavailabilityReason,
    UserRole,
)

D = date(2026, 11, 10)
D2 = date(2026, 11, 12)


def org(s):
    o = Organization(id=uuid.uuid4(), name="Org")
    s.add(o)
    s.flush()
    return o


def user(s, o, role=UserRole.CREW, username=None):
    u = AppUser(
        id=uuid.uuid4(),
        org_id=o.id,
        username=username or f"u-{uuid.uuid4()}",
        display_name="U",
        role=role,
    )
    s.add(u)
    s.flush()
    return u


def skill(s, o, name=None):
    k = Skill(id=uuid.uuid4(), org_id=o.id, name=name or f"s-{uuid.uuid4()}")
    s.add(k)
    s.flush()
    return k


def mission(s, o, lead, **kw):
    m = Mission(
        id=uuid.uuid4(), org_id=o.id, title="M", lead_id=lead.id,
        status=MissionStatus.DRAFT, start_date=D, end_date=D2, **kw,
    )  # fmt: skip
    s.add(m)
    s.flush()
    return m


def slot(s, o, m, k, position=1, min_level=3, **kw):
    r = MissionRequirement(
        id=uuid.uuid4(), org_id=o.id, mission_id=m.id, position=position,
        skill_id=k.id, min_level=min_level, **kw,
    )  # fmt: skip
    s.add(r)
    s.flush()
    return r


def assign(s, o, m, r, u, status=AssignmentStatus.INVITED):
    a = Assignment(
        id=uuid.uuid4(), org_id=o.id, mission_id=m.id, requirement_id=r.id,
        user_id=u.id, status=status,
    )  # fmt: skip
    s.add(a)
    s.flush()
    return a


def rejects(s, fn):
    with pytest.raises(IntegrityError), s.begin_nested():
        fn()


def world(s):
    """Two orgs with a lead, crew, skill, mission and slot each."""
    out = []
    for _ in range(2):
        o = org(s)
        lead = user(s, o, UserRole.LEAD)
        crew = user(s, o)
        k = skill(s, o)
        m = mission(s, o, lead)
        r = slot(s, o, m, k)
        out.append((o, lead, crew, k, m, r))
    return out


def test_same_org_links_succeed(session):
    (o, lead, crew, k, m, r), _ = world(session)
    session.add(CrewSkill(org_id=o.id, user_id=crew.id, skill_id=k.id, level=3))
    session.add(
        Unavailability(
            id=uuid.uuid4(), org_id=o.id, user_id=crew.id, start_date=D, end_date=D,
            reason=UnavailabilityReason.SICK,
        )
    )  # fmt: skip
    m.approved_by = lead.id
    assign(session, o, m, r, crew)
    session.flush()


def test_cross_org_links_fail(session):
    (a, a_lead, a_crew, a_k, a_m, a_r), (_b, b_lead, b_crew, b_k, b_m, b_r) = world(session)

    def add(obj):
        return lambda: (session.add(obj), session.flush())

    def unavail():
        return Unavailability(
            id=uuid.uuid4(), org_id=a.id, user_id=b_crew.id, start_date=D, end_date=D,
            reason=UnavailabilityReason.SICK,
        )  # fmt: skip

    def req(**kw):
        base = {"id": uuid.uuid4(), "org_id": a.id, "mission_id": a_m.id, "position": 2,
                    "skill_id": a_k.id, "min_level": 1}  # fmt: skip
        return MissionRequirement(**{**base, **kw})

    def asg(**kw):
        base = {"id": uuid.uuid4(), "org_id": a.id, "mission_id": a_m.id, "requirement_id": a_r.id,
                    "user_id": a_crew.id, "status": AssignmentStatus.INVITED}  # fmt: skip
        return Assignment(**{**base, **kw})

    def mis(**kw):
        base = {"id": uuid.uuid4(), "org_id": a.id, "title": "X", "lead_id": a_lead.id,
                    "status": MissionStatus.DRAFT, "start_date": D, "end_date": D2}  # fmt: skip
        return Mission(**{**base, **kw})

    cases = [
        asg(mission_id=b_m.id, requirement_id=b_r.id),  # assignment -> mission
        asg(user_id=b_crew.id),  # assignment -> app_user
        asg(requirement_id=b_r.id),  # assignment -> mission_requirement
        req(mission_id=b_m.id),  # requirement -> mission
        req(skill_id=b_k.id),  # requirement -> skill
        CrewSkill(org_id=a.id, user_id=b_crew.id, skill_id=a_k.id, level=1),  # -> app_user
        CrewSkill(org_id=a.id, user_id=a_crew.id, skill_id=b_k.id, level=1),  # -> skill
        unavail(),  # unavailability -> app_user
        mis(lead_id=b_lead.id),  # mission.lead_id
        mis(approved_by=b_lead.id),  # mission.approved_by
    ]
    assert len(cases) == 10
    for obj in cases:
        rejects(session, add(obj))


def test_assignment_slot_of_other_mission_same_org(session):
    (o, lead, crew, k, m, _r), _ = world(session)
    m2 = mission(session, o, lead)
    r2 = slot(session, o, m2, k)
    rejects(session, lambda: assign(session, o, m, r2, crew))


@pytest.mark.parametrize("table", ["app_user", "skill", "crew_skill", "unavailability",
                                   "mission", "mission_requirement", "assignment"])  # fmt: skip
def test_org_id_not_null(session, table):
    from sqlalchemy import text

    cols = session.execute(
        text(
            "SELECT is_nullable FROM information_schema.columns"
            " WHERE table_name = :t AND column_name = 'org_id'"
        ),
        {"t": table},
    ).scalar()
    assert cols == "NO"


@pytest.mark.parametrize("level,ok", [(0, False), (6, False), (1, True), (5, True)])
def test_level_ranges(session, level, ok):
    (o, _lead, crew, _k, m, _r), _ = world(session)
    k2 = skill(session, o)

    def crew_skill():
        session.add(CrewSkill(org_id=o.id, user_id=crew.id, skill_id=k2.id, level=level))
        session.flush()

    def requirement():
        slot(session, o, m, k2, position=2, min_level=level)

    for fn in (crew_skill, requirement):
        if ok:
            with session.begin_nested():
                fn()
        else:
            rejects(session, fn)


@pytest.mark.parametrize("end,ok", [(date(2026, 11, 9), False), (D, True)])
def test_date_order(session, end, ok):
    (o, lead, crew, *_), _ = world(session)

    def unavail():
        session.add(
            Unavailability(
                id=uuid.uuid4(), org_id=o.id, user_id=crew.id, start_date=D, end_date=end,
                reason=UnavailabilityReason.HOLIDAY,
            )
        )  # fmt: skip
        session.flush()

    def mis():
        m = Mission(
            id=uuid.uuid4(), org_id=o.id, title="M", lead_id=lead.id,
            status=MissionStatus.DRAFT, start_date=D, end_date=end,
        )  # fmt: skip
        session.add(m)
        session.flush()

    for fn in (unavail, mis):
        if ok:
            with session.begin_nested():
                fn()
        else:
            rejects(session, fn)


def test_unique_username_and_skill_name(session):
    a, b = org(session), org(session)
    name = f"ava-{uuid.uuid4()}"
    user(session, a, username=name)
    rejects(session, lambda: user(session, b, username=name))
    sk = f"EVA-{uuid.uuid4()}"
    skill(session, a, sk)
    rejects(session, lambda: skill(session, a, sk))
    skill(session, b, sk)


def test_active_slot_position_unique(session):
    (o, _lead, _crew, k, m, r), _ = world(session)
    rejects(session, lambda: slot(session, o, m, k, position=1))
    r.archived_at = datetime(2026, 10, 1, tzinfo=UTC)
    session.flush()
    slot(session, o, m, k, position=1)


@pytest.mark.parametrize("done", [AssignmentStatus.DECLINED, AssignmentStatus.CANCELLED])
def test_active_assignment_unique(session, done):
    (o, _lead, crew, k, m, r), _ = world(session)
    other = user(session, o)
    r2 = slot(session, o, m, k, position=2)
    first = assign(session, o, m, r, crew)
    rejects(session, lambda: assign(session, o, m, r2, crew))  # same mission and user
    rejects(session, lambda: assign(session, o, m, r, other))  # same slot
    first.status = done
    session.flush()
    assign(session, o, m, r, crew)


def test_timestamps(session):
    (_o, _lead, _crew, _k, m, _r), _ = world(session)
    session.refresh(m)
    created, updated = m.created_at, m.updated_at
    assert created and updated
    m.title = "Changed"
    session.flush()
    session.refresh(m)
    assert m.created_at == created
    assert m.updated_at > updated


def test_deletes_with_children_rejected(session):
    (o, _lead, crew, k, m, r), _ = world(session)
    session.add(CrewSkill(org_id=o.id, user_id=crew.id, skill_id=k.id, level=2))
    assign(session, o, m, r, crew)
    session.flush()
    session.expunge_all()
    rejects(session, lambda: (session.delete(session.get(AppUser, crew.id)), session.flush()))
    session.expunge_all()
    rejects(session, lambda: (session.delete(session.get(Mission, m.id)), session.flush()))


def test_user_delete_blocked_by_assignment_alone(session):
    (o, _lead, crew, _k, m, r), _ = world(session)
    assign(session, o, m, r, crew)
    session.expunge_all()
    rejects(session, lambda: (session.delete(session.get(AppUser, crew.id)), session.flush()))
