from sqlmodel import Session, SQLModel, create_engine, select

from app.models import User

DEFAULT_DATABASE_URL = "sqlite:///./cointwin.db"


def get_engine(database_url: str | None = None):
    return create_engine(database_url or DEFAULT_DATABASE_URL)


def create_db_and_tables(engine) -> None:
    SQLModel.metadata.create_all(engine)


def seed_anonymous_user(session: Session) -> User:
    existing = session.exec(select(User).where(User.nickname == "anonymous")).first()
    if existing:
        return existing

    user = User(nickname="anonymous")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
