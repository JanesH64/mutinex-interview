import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://mc:mc@localhost:5432/mc")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(engine)


class Base(DeclarativeBase):
    pass


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
