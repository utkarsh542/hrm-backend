"""Employee engagement models — surveys, mood tracking, wellness."""
from app.utils.timezone import get_ist_time, get_ist_date
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, Date, JSON, Enum as SQLEnum
from datetime import datetime, date
from app.database import Base
import enum


class SurveyStatus(enum.Enum):
    draft = "draft"
    active = "active"
    closed = "closed"


class PulseSurvey(Base):
    __tablename__ = "pulse_surveys"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    questions = Column(JSON, nullable=False)
    status = Column(SQLEnum(SurveyStatus), default=SurveyStatus.draft)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=get_ist_time)
    closes_at = Column(DateTime, nullable=True)


class SurveyResponse(Base):
    __tablename__ = "survey_responses"
    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, nullable=False, index=True)
    employee_id = Column(Integer, nullable=True)
    answers = Column(JSON, nullable=False)
    sentiment_score = Column(Float, nullable=True)
    submitted_at = Column(DateTime, default=get_ist_time)


class MoodEntry(Base):
    __tablename__ = "mood_entries"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, nullable=False, index=True)
    mood = Column(Integer, nullable=False)
    note = Column(Text, nullable=True)
    date = Column(Date, default=get_ist_date)
    created_at = Column(DateTime, default=get_ist_time)
