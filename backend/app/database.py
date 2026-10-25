from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.app.config import settings

is_sqlite = settings.database_url.startswith("sqlite")

connect_args = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    import backend.app.models.entities  # noqa: F401
    Base.metadata.create_all(bind=engine)


def reset_db(force: bool = False) -> None:
    if settings.app_env.lower() == "production" and not force:
        raise PermissionError(
            "Database reset is blocked in production environments to prevent accidental data loss."
        )
    if not settings.allow_db_reset and not force:
        raise PermissionError(
            "Database reset is disabled by configuration (ALLOW_DB_RESET=false)."
        )
    import backend.app.models.entities  # noqa: F401
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

