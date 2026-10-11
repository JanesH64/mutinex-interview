"""Slot matcher. Plain data in, plain data out: no database and no web framework."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

import numpy as np
from scipy.optimize import linear_sum_assignment

from mc_shared import SlotOut


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
    """Fill the most slots, then prefer the lowest gap, then the first username."""
    result: list[Candidate | None] = [None] * len(slots)
    if not slots or not candidates:
        return result
    rank = {n: i for i, n in enumerate(sorted(c.username for c in candidates))}
    n = len(slots)
    # Exact integer costs: a higher term outweighs the sum of all lower terms over all slots.
    weight = n * (len(candidates) - 1) + 1  # name_rank is the lowest term, gap the highest
    cost = [
        [
            (c.skills[s.skill_id] - s.min_level) * weight + rank[c.username]
            if c.skills.get(s.skill_id, 0) >= s.min_level
            else None
            for c in candidates
        ]
        for s in slots
    ]
    big = n * max((x for row in cost for x in row if x is not None), default=0) + 1
    assert big < 2**53  # float64 keeps each integer exact
    matrix = np.array([[big if x is None else x for x in row] for row in cost], dtype=np.float64)
    for i, j in zip(*linear_sum_assignment(matrix), strict=True):
        if cost[i][j] is not None:
            result[i] = candidates[j]
    return result
