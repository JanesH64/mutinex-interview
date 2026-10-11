"""Slot matcher. Plain data in, plain data out: no database and no web framework."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from fractions import Fraction
from uuid import UUID

import numpy as np
from scipy.optimize import linear_sum_assignment

from mc_shared import SlotOut

WORKLOAD_WINDOW_DAYS = 90


def workload_days(start: date, end: date, booked: Iterable[tuple[date, date]]) -> int:
    """Days of the booked ranges inside the window around the mission. Both ends count."""
    lo = start - timedelta(days=WORKLOAD_WINDOW_DAYS)
    hi = end + timedelta(days=WORKLOAD_WINDOW_DAYS)
    return sum(max(0, (min(e, hi) - max(s, lo)).days + 1) for s, e in booked)


@dataclass(frozen=True)
class Candidate:
    user_id: UUID
    username: str
    skills: Mapping[UUID, int]  # skill_id -> level, all skills of the member
    workload_days: int = 0


def assign(
    slots: Sequence[SlotOut],
    candidates: Sequence[Candidate],
    holders: Mapping[UUID, int],
) -> list[Candidate | None]:
    """Fill the most slots, then the lowest gap, scarcity, workload and the first username."""
    result: list[Candidate | None] = [None] * len(slots)
    if not slots or not candidates:
        return result
    rank = {n: i for i, n in enumerate(sorted(c.username for c in candidates))}
    n = len(slots)

    def scarcity(c: Candidate, s: SlotOut) -> Fraction:
        return max(
            (Fraction(1, holders[k]) for k in c.skills if k != s.skill_id), default=Fraction(0)
        )

    eligible = {
        (i, j)
        for i, s in enumerate(slots)
        for j, c in enumerate(candidates)
        if c.skills.get(s.skill_id, 0) >= s.min_level
    }
    scar = {cell: scarcity(candidates[cell[1]], slots[cell[0]]) for cell in eligible}
    scar_rank = {v: r for r, v in enumerate(sorted(set(scar.values())))}
    # Terms from the lowest to the highest. A higher term outweighs the sum of all lower terms.
    terms = [
        lambda i, j: rank[candidates[j].username],
        lambda i, j: candidates[j].workload_days,
        lambda i, j: scar_rank[scar[i, j]],
        lambda i, j: candidates[j].skills[slots[i].skill_id] - slots[i].min_level,
    ]
    cost = {cell: terms[0](*cell) for cell in eligible}
    for term in terms[1:]:
        weight = n * max(cost.values(), default=0) + 1
        cost = {cell: term(*cell) * weight + x for cell, x in cost.items()}
    cost_rows = [[cost.get((i, j)) for j in range(len(candidates))] for i in range(n)]
    big = n * max(cost.values(), default=0) + 1
    assert big < 2**53  # float64 keeps each integer exact
    matrix = np.array(
        [[big if x is None else x for x in row] for row in cost_rows], dtype=np.float64
    )
    for i, j in zip(*linear_sum_assignment(matrix), strict=True):
        if (i, j) in cost:
            result[i] = candidates[j]
    return result
