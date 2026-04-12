"""User model for authentication and role management."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SAEnum
from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    HR = "hr"
    MANAGER = "manager"
    EMPLOYEE = "employee"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(SAEnum(UserRole), default=UserRole.EMPLOYEE, nullable=False)
    is_active = Column(Boolean, default=True)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
