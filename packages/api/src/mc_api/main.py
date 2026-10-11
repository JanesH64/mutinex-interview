import logging
import os

from fastapi import FastAPI

from mc_api.errors import Forbidden, forbidden_handler
from mc_api.routers import auth, health, users

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="Mission Control")
app.add_exception_handler(Forbidden, forbidden_handler)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
