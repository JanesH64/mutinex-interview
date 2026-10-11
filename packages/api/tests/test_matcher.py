import time
from uuid import UUID, uuid4

from mc_shared import SlotOut

EVA = UUID(int=1)
ROBOTICS = UUID(int=2)
PILOTING = UUID(int=3)
GEOLOGY = UUID(int=4)
NAMES = {EVA: "EVA", ROBOTICS: "Robotics", PILOTING: "Piloting", GEOLOGY: "Geology"}


def slot(skill, level, position=1):
    return SlotOut(
        id=uuid4(), position=position, skill_id=skill, skill_name=NAMES[skill], min_level=level
    )


def crew(name, skills, workload_days=0):
    from mc_api.matcher import Candidate

    return Candidate(uuid4(), name, {k: v for k, v in skills.items()}, workload_days)


def holders_of(candidates):
    out = {}
    for c in candidates:
        for skill in c.skills:
            out[skill] = out.get(skill, 0) + 1
    return out


def run(slots, candidates):
    from mc_api.matcher import assign

    return assign(slots, candidates, holders_of(candidates))


def names(result):
    return [c.username if c else None for c in result]


def test_assign_prefers_the_lowest_gap_ac11_dev_over_cara():
    got = run([slot(EVA, 3)], [crew("dev", {EVA: 3}), crew("cara", {EVA: 4})])
    assert names(got) == ["dev"]


def test_assign_closest_fit_wins_ac12():
    got = run(
        [slot(PILOTING, 3)],
        [crew("ava", {PILOTING: 5}), crew("ivan", {PILOTING: 4}), crew("ben", {PILOTING: 3})],
    )
    assert names(got) == ["ben"]


def test_assign_below_minimum_or_other_skill_gives_none_ac7():
    got = run([slot(EVA, 3)], [crew("dev", {EVA: 2}), crew("jo", {GEOLOGY: 4})])
    assert got == [None]


def test_assign_greedy_trap_ac11():
    got = run(
        [slot(EVA, 3, 1), slot(ROBOTICS, 3, 2)],
        [crew("cara", {EVA: 3, ROBOTICS: 3}), crew("dev", {EVA: 4})],
    )
    assert names(got) == ["dev", "cara"]


def test_assign_fills_the_maximum_number_of_slots_ac11():
    got = run(
        [slot(EVA, 3, 1), slot(EVA, 3, 2), slot(EVA, 3, 3)],
        [crew("abe", {EVA: 3}), crew("bob", {EVA: 3})],
    )
    assert sorted(n for n in names(got) if n) == ["abe", "bob"]
    assert names(got).count(None) == 1


def test_assign_uses_each_member_one_time():
    got = run([slot(EVA, 3, 1), slot(EVA, 3, 2)], [crew("abe", {EVA: 3}), crew("bob", {EVA: 3})])
    assert sorted(names(got)) == ["abe", "bob"]


def test_assign_full_tie_goes_to_the_first_username_ac16():
    eli, abe = crew("eli", {EVA: 3}), crew("abe", {EVA: 3})
    from mc_api.matcher import assign

    for order in ([eli, abe], [abe, eli]):
        assert names(assign([slot(EVA, 3)], order, holders_of(order))) == ["abe"]


def test_assign_handles_empty_inputs():
    assert run([], [crew("abe", {EVA: 3})]) == []
    assert run([slot(EVA, 3)], []) == [None]


def test_assign_scales_to_20_slots_and_200_candidates():
    slots = [slot(EVA, 1, p) for p in range(1, 21)]
    candidates = [
        crew(f"u{i:03}", {EVA: i % 5 + 1}, workload_days=(i * 7) % 301) for i in range(200)
    ]
    start = time.monotonic()
    got = run(slots, candidates)
    assert time.monotonic() - start < 2
    assert len({c.user_id for c in got}) == 20
