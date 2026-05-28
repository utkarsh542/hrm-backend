"""Attendance and leave management models."""
import enum
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, Enum as SAEnum, Float
from app.database import Base


class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    HALF_DAY = "half_day"
    WORK_FROM_HOME = "work_from_home"
    ON_LEAVE = "on_leave"
    HOLIDAY = "holiday"
    WEEKEND = "weekend"


class LeaveType(str, enum.Enum):
    CASUAL = "casual"
    SICK = "sick"
    EARNED = "earned"
    MATERNITY = "maternity"
    PATERNITY = "paternity"
    UNPAID = "unpaid"
    COMPENSATORY = "compensatory"


class LeaveStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, nullable=False, index=True)
    date = Column(Date, nullable=False, default=date.today, index=True)
    status = Column(SAEnum(AttendanceStatus), default=AttendanceStatus.PRESENT)
    check_in = Column(DateTime, nullable=True)
    check_out = Column(DateTime, nullable=True)
    work_hours = Column(Float, default=0)
    overtime_hours = Column(Float, default=0)
    notes = Column(Text, nullable=True)
    ip_address = Column(String, nullable=True)
    
    # Geofence & Reverse Geocoding logs
    check_in_lat = Column(Float, nullable=True)
    check_in_lon = Column(Float, nullable=True)
    check_out_lat = Column(Float, nullable=True)
    check_out_lon = Column(Float, nullable=True)
    check_in_address = Column(String, nullable=True)
    check_out_address = Column(String, nullable=True)
    check_in_district = Column(String, nullable=True)
    check_in_state = Column(String, nullable=True)
    check_out_district = Column(String, nullable=True)
    check_out_state = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, nullable=False, index=True)
    leave_type = Column(SAEnum(LeaveType), default=LeaveType.CASUAL)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    days = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(SAEnum(LeaveStatus), default=LeaveStatus.PENDING, index=True)
    approved_by = Column(Integer, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Holiday(Base):
    __tablename__ = "holidays"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    type = Column(String, default="national")  # national, regional, optional
    created_at = Column(DateTime, default=datetime.utcnow)


class GeofenceSetting(Base):
    __tablename__ = "geofence_settings"

    id = Column(Integer, primary_key=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius = Column(Float, default=100.0)

