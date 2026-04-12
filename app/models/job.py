"""Job posting model."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SAEnum, Float
from app.database import Base


class JobStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    ON_HOLD = "on_hold"


class JobType(str, enum.Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    department = Column(String, nullable=False)
    location = Column(String, nullable=False)
    job_type = Column(SAEnum(JobType), default=JobType.FULL_TIME)
    experience_min = Column(Integer, default=0)
    experience_max = Column(Integer, default=0)
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    description = Column(Text, nullable=False)
    requirements = Column(Text, nullable=True)
    skills = Column(String, nullable=True)  # Comma-separated
    status = Column(SAEnum(JobStatus), default=JobStatus.OPEN)
    openings = Column(Integer, default=1)
    posted_by = Column(Integer, nullable=True)  # User ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closing_date = Column(DateTime, nullable=True)
