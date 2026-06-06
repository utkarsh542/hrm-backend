"""Face attendance model — stores face-verified check-in records."""
from datetime import datetime, date
from app.utils.timezone import get_ist_time, get_ist_date
from sqlalchemy import Column, Integer, String, DateTime, Date, Float, Boolean, Text
from app.database import Base


class FaceAttendance(Base):
    __tablename__ = "face_attendance"
    __table_args__ = {'extend_existing': True}

    id            = Column(Integer, primary_key=True, index=True)
    employee_id   = Column(Integer, nullable=False, index=True)
    date          = Column(Date, nullable=False, default=get_ist_date, index=True)
    check_in      = Column(DateTime, nullable=True)
    check_out     = Column(DateTime, nullable=True)
    work_hours    = Column(Float, default=0)
    confidence    = Column(Float, default=0)      # face match confidence 0-1
    verified      = Column(Boolean, default=False)
    location      = Column(String, nullable=True)  # office / remote
    ip_address    = Column(String, nullable=True)
    device_info   = Column(String, nullable=True)
    notes         = Column(Text, nullable=True)
    created_at    = Column(DateTime, default=get_ist_time)
