"""Employee and department models."""
import enum
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, Enum as SAEnum, Float, Boolean
from app.database import Base


class EmploymentStatus(str, enum.Enum):
    ACTIVE = "active"
    ON_NOTICE = "on_notice"
    TERMINATED = "terminated"
    RESIGNED = "resigned"
    ON_LEAVE = "on_leave"


class EmploymentType(str, enum.Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERN = "intern"


class OnboardingStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    head_employee_id = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)  # Link to User
    employee_id = Column(String, unique=True, nullable=False)  # e.g., EMP001
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String, nullable=True)
    address = Column(Text, nullable=True)
    
    # Professional
    department_id = Column(Integer, nullable=True)
    designation = Column(String, nullable=True)
    employment_type = Column(SAEnum(EmploymentType), default=EmploymentType.FULL_TIME)
    employment_status = Column(SAEnum(EmploymentStatus), default=EmploymentStatus.ACTIVE)
    joining_date = Column(Date, nullable=False, default=date.today)
    reporting_manager_id = Column(Integer, nullable=True)
    
    # Compensation
    ctc = Column(Float, default=0)  # Annual CTC
    basic_salary = Column(Float, default=0)
    hra = Column(Float, default=0)
    da = Column(Float, default=0)
    special_allowance = Column(Float, default=0)
    pf_contribution = Column(Float, default=0)
    
    # Leave balances
    casual_leave_balance = Column(Float, default=12)
    sick_leave_balance = Column(Float, default=12)
    earned_leave_balance = Column(Float, default=15)
    
    # Documents
    pan_number = Column(String, nullable=True)
    aadhar_number = Column(String, nullable=True)
    bank_account = Column(String, nullable=True)
    bank_name = Column(String, nullable=True)
    ifsc_code = Column(String, nullable=True)
    
    # Onboarding
    onboarding_status = Column(SAEnum(OnboardingStatus), default=OnboardingStatus.PENDING)
    onboarding_checklist = Column(Text, nullable=True)  # JSON
    buddy_id = Column(Integer, nullable=True)
    
    # Meta
    avatar_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
