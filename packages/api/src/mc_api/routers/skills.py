from typing import Annotated

from fastapi import APIRouter, Depends

from mc_api.dependencies import get_scope
from mc_api.models import Skill
from mc_api.scope import OrgScope
from mc_shared import SkillOut

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("")
def list_skills(scope: Annotated[OrgScope, Depends(get_scope)]) -> list[SkillOut]:
    skills = scope.session.scalars(scope.select(Skill).order_by(Skill.name))
    return [SkillOut(id=s.id, name=s.name, description=s.description) for s in skills]
