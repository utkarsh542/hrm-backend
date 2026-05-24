"""Database engine and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite specific
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def get_db():
    """Dependency injection for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables."""
    # Import all models so SQLAlchemy registers them before create_all
    from app.models import (  # noqa
        user, employee, job, candidate, interview,
        attendance, payroll, performance, offboarding,
        document, expense, face_attendance,
        notification, onboarding, engagement, workflow, skills,
    )
    Base.metadata.create_all(bind=engine)
