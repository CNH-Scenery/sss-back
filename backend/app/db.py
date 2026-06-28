import os
from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine, select

from app.models import User

DEFAULT_DATABASE_URL = "sqlite:///./cointwin.db"


def get_engine(database_url: str | None = None):
    url = database_url or DEFAULT_DATABASE_URL
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


engine = get_engine(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))


def create_db_and_tables(engine) -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def seed_anonymous_user(session: Session) -> User:
    existing = session.exec(select(User).where(User.nickname == "anonymous")).first()
    if existing:
        return existing

    user = User(nickname="anonymous")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def initialize_database() -> None:
    from app.seed import seed_static_scenarios

    create_db_and_tables(engine)
    with Session(engine) as session:
        seed_anonymous_user(session)
        seed_static_scenarios(session)
