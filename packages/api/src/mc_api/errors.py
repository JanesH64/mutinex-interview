import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from mc_shared import ForbiddenError, UserRole

logger = logging.getLogger(__name__)


class Forbidden(Exception):
    def __init__(self, role: UserRole, rule: str) -> None:
        self.role = role
        self.rule = rule


async def forbidden_handler(request: Request, exc: Forbidden) -> JSONResponse:
    logger.info(
        "forbidden: %s %s role %s: %s", request.method, request.url.path, exc.role, exc.rule
    )
    return JSONResponse(ForbiddenError(role=exc.role, rule=exc.rule).model_dump(mode="json"), 403)
