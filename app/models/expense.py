"""Expense management model."""
import enum
from datetime import datetime, date
from app.utils.timezone import get_ist_time, get_ist_date
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, Enum as SAEnum, Float, Boolean
from app.database import Base


class ExpenseCategory(str, enum.Enum):
    TRAVEL      = "travel"
    FOOD        = "food"
    ACCOMMODATION = "accommodation"
    EQUIPMENT   = "equipment"
    TRAINING    = "training"
    MEDICAL     = "medical"
    INTERNET    = "internet"
    MOBILE      = "mobile"
    OTHER       = "other"


class ExpenseStatus(str, enum.Enum):
    DRAFT     = "draft"
    SUBMITTED = "submitted"
    APPROVED  = "approved"
    REJECTED  = "rejected"
    PAID      = "paid"


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = {'extend_existing': True}

    id            = Column(Integer, primary_key=True, index=True)
    employee_id   = Column(Integer, nullable=False, index=True)
    title         = Column(String, nullable=False)
    description   = Column(Text, nullable=True)
    category      = Column(SAEnum(ExpenseCategory), default=ExpenseCategory.OTHER)
    amount        = Column(Float, nullable=False)
    currency      = Column(String, default="INR")
    expense_date  = Column(Date, nullable=False, default=get_ist_date)
    status        = Column(SAEnum(ExpenseStatus), default=ExpenseStatus.SUBMITTED, index=True)
    receipt_path  = Column(String, nullable=True)
    receipt_name  = Column(String, nullable=True)
    approved_by   = Column(Integer, nullable=True)
    approved_at   = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    paid_at       = Column(DateTime, nullable=True)
    notes         = Column(Text, nullable=True)
    created_at    = Column(DateTime, default=get_ist_time)
    updated_at    = Column(DateTime, default=get_ist_time, onupdate=get_ist_time)
