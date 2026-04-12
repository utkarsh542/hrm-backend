"""Interview and scorecard models."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SAEnum, Float
from app.database import Base


class InterviewType(str, enum.Enum):
    PHONE_SCREEN = "phone_screen"
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    HR = "hr"
    AI_INTERVIEW = "ai_interview"
    PANEL = "panel"
    FINAL = "final"


class InterviewStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, nullable=False)
    candidate_id = Column(Integer, nullable=False)
    job_id = Column(Integer, nullable=False)
    interview_type = Column(SAEnum(InterviewType), default=InterviewType.TECHNICAL)
    status = Column(SAEnum(InterviewStatus), default=InterviewStatus.SCHEDULED)
    scheduled_at = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=60)
    interviewer_name = Column(String, nullable=True)
    interviewer_email = Column(String, nullable=True)
    meeting_link = Column(String, nullable=True)
    location = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    # AI Interview Results
    ai_questions = Column(Text, nullable=True)  # JSON
    ai_responses = Column(Text, nullable=True)  # JSON
    ai_score = Column(Float, nullable=True)
    ai_feedback = Column(Text, nullable=True)
    # Scorecard
    technical_score = Column(Float, nullable=True)
    communication_score = Column(Float, nullable=True)
    cultural_fit_score = Column(Float, nullable=True)
    overall_score = Column(Float, nullable=True)
    recommendation = Column(String, nullable=True)  # hire, reject, next_round
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
