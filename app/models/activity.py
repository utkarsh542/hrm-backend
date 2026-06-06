"""Activity model for planned corporate events, trainings, and engagements."""
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SQLEnum
from datetime import datetime
from app.database import Base
from app.utils.timezone import get_ist_time
import enum


class ActivityCategory(enum.Enum):
    training = "training"
    event = "event"
    team_building = "team_building"
    meeting = "meeting"
    holiday = "holiday"
    other = "other"


class Activity(Base):
    __tablename__ = "activities"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(SQLEnum(ActivityCategory), default=ActivityCategory.event, index=True)
    scheduled_at = Column(DateTime, nullable=False, index=True)
    location = Column(String, nullable=True)
    organizer_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=get_ist_time)

