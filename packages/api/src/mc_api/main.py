from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from mc_api.db import get_session
from mc_shared import Health

app = FastAPI(title="Mission Control")


@app.get("/health")
def health(session: Annotated[Session, Depends(get_session)]) -> Health:
    session.execute(text("SELECT 1"))
    return Health(status="ok", db="ok")
