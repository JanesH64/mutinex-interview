import random
import time
from datetime import date
from uuid import UUID, uuid4

from mc_shared import SlotOut

EVA = UUID(int=1)
ROBOTICS = UUID(int=2)
PILOTING = UUID(int=3)
GEOLOGY = UUID(int=4)
WELDING = UUID(int=5)
NAMES = {
    EVA: "EVA",
    ROBOTICS: "Robotics",
    PILOTING: "Piloting",
    GEOLOGY: "Geology",
    WELDING: "Welding",
}


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


def run_with(slots, candidates, holders):
    from mc_api.matcher import assign

    return assign(slots, candidates, holders)


def test_scarcity_no_other_skill_beats_a_rare_other_skill_ac13():
    got = run_with(
        [slot(EVA, 3)], [crew("eli", {EVA: 3, GEOLOGY: 3}), crew("dev", {EVA: 3})], {GEOLOGY: 3}
    )
    assert names(got) == ["dev"]


def test_scarcity_lower_max_wins_ac13_eli_over_cara():
    got = run_with(
        [slot(EVA, 3)],
        [crew("cara", {EVA: 3, ROBOTICS: 3}), crew("eli", {EVA: 3, GEOLOGY: 3})],
        {GEOLOGY: 3, ROBOTICS: 2},
    )
    assert names(got) == ["eli"]


def test_scarcity_wins_over_workload_ac13():
    got = run_with(
        [slot(EVA, 3)],
        [crew("dev", {EVA: 3}, workload_days=30), crew("eli", {EVA: 3, GEOLOGY: 3})],
        {GEOLOGY: 3},
    )
    assert names(got) == ["dev"]


def test_scarcity_only_the_max_counts_ac13():
    got = run_with(
        [slot(EVA, 3)],
        [crew("bob", {EVA: 3, ROBOTICS: 1}), crew("abe", {EVA: 3, GEOLOGY: 1, PILOTING: 1})],
        {GEOLOGY: 3, PILOTING: 3, ROBOTICS: 2},
    )
    assert names(got) == ["abe"]


def test_scarcity_ignores_the_slot_skill_ac13():
    got = run_with(
        [slot(WELDING, 1)],
        [crew("bob", {WELDING: 1, GEOLOGY: 2}), crew("abe", {WELDING: 1}, workload_days=10)],
        {WELDING: 2, GEOLOGY: 3},
    )
    assert names(got) == ["abe"]


def test_gap_wins_over_scarcity_and_workload_ac12():
    got = run_with(
        [slot(PILOTING, 3)],
        [crew("ivan", {PILOTING: 4}), crew("ben", {PILOTING: 3, ROBOTICS: 1}, workload_days=60)],
        {ROBOTICS: 1},
    )
    assert names(got) == ["ben"]


def test_lower_workload_wins_at_equal_gap_and_scarcity_ac14():
    got = run([slot(EVA, 3)], [crew("dev", {EVA: 3}, workload_days=12), crew("kai", {EVA: 3})])
    assert names(got) == ["kai"]


def test_workload_days_clips_to_the_window_ac15():
    from mc_api.matcher import workload_days

    booked = [
        (date(2026, 11, 25), date(2026, 12, 5)),
        (date(2027, 6, 1), date(2027, 6, 20)),
        (date(2026, 11, 20), date(2026, 11, 30)),
    ]
    assert workload_days(date(2027, 3, 1), date(2027, 3, 10), booked) == 13
    assert workload_days(date(2027, 3, 1), date(2027, 3, 10), []) == 0


def test_assign_scales_with_random_holders():
    rng = random.Random(7)
    slots = [slot(EVA, 1, p) for p in range(1, 21)]
    skills = [ROBOTICS, PILOTING, GEOLOGY]
    candidates = [
        crew(
            f"u{i:03}",
            {EVA: i % 5 + 1, **{k: 1 for k in skills if rng.random() < 0.5}},
            workload_days=(i * 7) % 301,
        )
        for i in range(200)
    ]
    holders = {k: rng.randint(1, 200) for k in [EVA, *skills]}
    start = time.monotonic()
    got = run_with(slots, candidates, holders)
    assert time.monotonic() - start < 2
    assert len({c.user_id for c in got}) == 20
