"""Skills, training, and succession planning models."""
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, JSON, Enum as SQLEnum
from datetime import datetime
from app.database import Base
import enum


class SkillCategory(enum.Enum):
    technical = "technical"
    soft = "soft"
    domain = "domain"
    certification = "certification"
    language = "language"


class Skill(Base):
    __tablename__ = "skills"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    category = Column(SQLEnum(SkillCategory), default=SkillCategory.technical)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmployeeSkill(Base):
    __tablename__ = "employee_skills"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, nullable=False, index=True)
    skill_id = Column(Integer, nullable=False, index=True)
    proficiency = Column(Integer, default=3)
    verified = Column(Boolean, default=False)
    verified_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TrainingProgram(Base):
    __tablename__ = "training_programs"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    provider = Column(String, nullable=True)
    duration_hours = Column(Integer, default=0)
    is_mandatory = Column(Boolean, default=False)
    skills_covered = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TrainingEnrollment(Base):
    __tablename__ = "training_enrollments"
    id = Column(Integer, primary_key=True, index=True)
    program_id = Column(Integer, nullable=False, index=True)
    employee_id = Column(Integer, nullable=False, index=True)
    status = Column(String, default="enrolled")
    progress = Column(Integer, default=0)
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    certificate_url = Column(String, nullable=True)


class SuccessionPlan(Base):
    __tablename__ = "succession_plans"
    id = Column(Integer, primary_key=True, index=True)
    position = Column(String, nullable=False)
    department = Column(String, nullable=True)
    current_holder_id = Column(Integer, nullable=True)
    criticality = Column(String, default="medium")
    created_at = Column(DateTime, default=datetime.utcnow)


class SuccessionCandidate(Base):
    __tablename__ = "succession_candidates"
    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, nullable=False, index=True)
    employee_id = Column(Integer, nullable=False, index=True)
    readiness = Column(String, default="1-2_years")
    ai_score = Column(Float, nullable=True)
    gaps = Column(JSON, nullable=True)
    development_actions = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
