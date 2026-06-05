"""Offboarding, resignation, and exit models."""
import enum
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, Enum as SAEnum, Float, Boolean
from app.database import Base


class ResignationStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    MANAGER_APPROVED = "manager_approved"
    HR_PROCESSING = "hr_processing"
    EXIT_INTERVIEW = "exit_interview"
    FINAL_SETTLEMENT = "final_settlement"
    COMPLETED = "completed"
    WITHDRAWN = "withdrawn"


class Resignation(Base):
    __tablename__ = "resignations"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    resignation_date = Column(Date, nullable=False, default=date.today)
    last_working_day = Column(Date, nullable=True)
    notice_period_days = Column(Integer, default=30)
    status = Column(SAEnum(ResignationStatus), default=ResignationStatus.SUBMITTED)
    
    # Manager & HR
    manager_remarks = Column(Text, nullable=True)
    hr_remarks = Column(Text, nullable=True)
    
    # Exit Interview
    exit_interview_done = Column(Boolean, default=False)
    exit_feedback = Column(Text, nullable=True)
    exit_rating = Column(Integer, nullable=True)  # 1-5 overall experience
    would_recommend = Column(Boolean, nullable=True)
    reason_for_leaving = Column(String, nullable=True)
    
    # Asset Return
    assets_returned = Column(Boolean, default=False)
    asset_checklist = Column(Text, nullable=True)  # JSON
    
    # Documents
    experience_letter_generated = Column(Boolean, default=False)
    relieving_letter_generated = Column(Boolean, default=False)
    fnf_generated = Column(Boolean, default=False)
    
    # Final Settlement
    pending_salary = Column(Float, default=0)
    leave_encashment = Column(Float, default=0)
    gratuity = Column(Float, default=0)
    deductions = Column(Float, default=0)
    total_settlement = Column(Float, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OffboardingDocument(Base):
    __tablename__ = "offboarding_documents"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, nullable=True)
    candidate_id = Column(Integer, nullable=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # resume, offer_letter, payslip, experience_letter, etc.
    file_url = Column(String, nullable=True)
    generated_content = Column(Text, nullable=True)  # For generated docs
    created_at = Column(DateTime, default=datetime.utcnow)
