"""Onboarding models for new employee onboarding automation."""
from app.utils.timezone import get_ist_time
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Enum as SQLEnum
from datetime import datetime
from app.database import Base
import enum


class OnboardingTaskCategory(enum.Enum):
    documentation = "documentation"
    training = "training"
    access = "access"
    introduction = "introduction"
    equipment = "equipment"


class OnboardingTaskStatus(enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    skipped = "skipped"


class OnboardingPlan(Base):
    __tablename__ = "onboarding_plans"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, nullable=False, index=True)
    plan_name = Column(String, nullable=False)
    department = Column(String, nullable=True)
    role = Column(String, nullable=True)
    status = Column(String, default="active")
    ai_generated = Column(Boolean, default=False)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=get_ist_time)
    completed_at = Column(DateTime, nullable=True)


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"
    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(SQLEnum(OnboardingTaskCategory), default=OnboardingTaskCategory.training)
    assigned_to = Column(Integer, nullable=True)
    due_day = Column(Integer, default=1)
    status = Column(SQLEnum(OnboardingTaskStatus), default=OnboardingTaskStatus.pending)
    priority = Column(String, default="medium")
    order = Column(Integer, default=0)
    completed_at = Column(DateTime, nullable=True)
    completed_by = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
