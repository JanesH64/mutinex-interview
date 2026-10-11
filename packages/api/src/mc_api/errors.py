from fastapi import Request
from fastapi.responses import JSONResponse

from mc_shared import ForbiddenError, UserRole


class Forbidden(Exception):
    def __init__(self, role: UserRole, rule: str) -> None:
        self.role = role
        self.rule = rule


async def forbidden_handler(request: Request, exc: Forbidden) -> JSONResponse:
    return JSONResponse(ForbiddenError(role=exc.role, rule=exc.rule).model_dump(mode="json"), 403)
