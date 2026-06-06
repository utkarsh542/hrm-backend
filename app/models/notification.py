"""Notification model for real-time alerts."""
from app.utils.timezone import get_ist_time
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Enum as SQLEnum
from datetime import datetime
from app.database import Base
import enum


class NotificationType(enum.Enum):
    info = "info"
    warning = "warning"
    success = "success"
    action = "action"


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    type = Column(SQLEnum(NotificationType), default=NotificationType.info)
    link = Column(String, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=get_ist_time)
