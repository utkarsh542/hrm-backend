"""Payroll, salary, and payslip models."""
import enum
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, Enum as SAEnum, Float
from app.database import Base


class PayrollStatus(str, enum.Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PAID = "paid"


class PayrollRun(Base):
    __tablename__ = "payroll_runs"

    id = Column(Integer, primary_key=True, index=True)
    month = Column(Integer, nullable=False)  # 1-12
    year = Column(Integer, nullable=False)
    status = Column(SAEnum(PayrollStatus), default=PayrollStatus.DRAFT)
    total_employees = Column(Integer, default=0)
    total_gross = Column(Float, default=0)
    total_deductions = Column(Float, default=0)
    total_net = Column(Float, default=0)
    processed_by = Column(Integer, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Payslip(Base):
    __tablename__ = "payslips"

    id = Column(Integer, primary_key=True, index=True)
    payroll_run_id = Column(Integer, nullable=False)
    employee_id = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    
    # Earnings
    basic_salary = Column(Float, default=0)
    hra = Column(Float, default=0)
    da = Column(Float, default=0)
    special_allowance = Column(Float, default=0)
    overtime_pay = Column(Float, default=0)
    bonus = Column(Float, default=0)
    total_earnings = Column(Float, default=0)
    
    # Deductions
    pf_employee = Column(Float, default=0)
    pf_employer = Column(Float, default=0)
    professional_tax = Column(Float, default=0)
    tds = Column(Float, default=0)
    other_deductions = Column(Float, default=0)
    total_deductions = Column(Float, default=0)
    
    # Net
    net_salary = Column(Float, default=0)
    
    # Meta
    working_days = Column(Integer, default=0)
    present_days = Column(Integer, default=0)
    leave_days = Column(Integer, default=0)
    status = Column(String, default="generated")
    pdf_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
