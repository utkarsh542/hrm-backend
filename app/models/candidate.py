"""Candidate and application models."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SAEnum, Float
from app.database import Base


class ApplicationStatus(str, enum.Enum):
    APPLIED = "applied"
    SCREENING = "screening"
    SHORTLISTED = "shortlisted"
    INTERVIEW = "interview"
    OFFERED = "offered"
    HIRED = "hired"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ApplicationSource(str, enum.Enum):
    LINKEDIN = "linkedin"
    NAUKRI = "naukri"
    INDEED = "indeed"
    EMAIL = "email"
    REFERRAL = "referral"
    WEBSITE = "website"
    OTHER = "other"


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)
    current_company = Column(String, nullable=True)
    current_designation = Column(String, nullable=True)
    experience_years = Column(Float, default=0)
    skills = Column(Text, nullable=True)  # Comma-separated
    resume_url = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    location = Column(String, nullable=True)
    expected_salary = Column(Float, nullable=True)
    notice_period_days = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, nullable=False)
    job_id = Column(Integer, nullable=False)
    status = Column(SAEnum(ApplicationStatus), default=ApplicationStatus.APPLIED)
    source = Column(SAEnum(ApplicationSource), default=ApplicationSource.WEBSITE)
    ai_score = Column(Float, nullable=True)  # AI screening score (0-100)
    ai_summary = Column(Text, nullable=True)  # AI screening summary
    notes = Column(Text, nullable=True)
    applied_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
