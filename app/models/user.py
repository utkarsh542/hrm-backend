"""User model for authentication and role management."""
import enum
from datetime import datetime
from app.utils.timezone import get_ist_time
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SAEnum
from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    HR = "hr"
    MANAGER = "manager"
    EMPLOYEE = "employee"

    def __str__(self):
        return self.value


from sqlalchemy.ext.hybrid import hybrid_property


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    _role = Column("role", SAEnum(UserRole), default=UserRole.EMPLOYEE, nullable=False)
    is_active = Column(Boolean, default=True)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=get_ist_time)
    updated_at = Column(DateTime, default=get_ist_time, onupdate=get_ist_time)

    @hybrid_property
    def role(self):
        val = self._role
        if isinstance(val, UserRole):
            return val
        if isinstance(val, str):
            try:
                return UserRole(val.lower())
            except ValueError:
                try:
                    return UserRole[val.upper()]
                except KeyError:
                    return UserRole.EMPLOYEE
        return UserRole.EMPLOYEE

    @role.setter
    def role(self, value):
        self._role = value

    @role.expression
    def role(cls):
        return cls._role
