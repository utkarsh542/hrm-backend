"""Pydantic schemas for all modules."""
import datetime as dt
from typing import Optional, List
from pydantic import BaseModel


# ============== AUTH ==============
class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    avatar_url: Optional[str] = None
    
    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str = "employee"


# ============== JOBS ==============
class JobCreate(BaseModel):
    title: str
    department: str
    location: str
    job_type: str = "full_time"
    experience_min: int = 0
    experience_max: int = 0
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    description: str
    requirements: Optional[str] = None
    skills: Optional[str] = None
    openings: int = 1
    closing_date: Optional[dt.datetime] = None

class JobUpdate(BaseModel):
    title: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = None
    experience_min: Optional[int] = None
    experience_max: Optional[int] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    skills: Optional[str] = None
    status: Optional[str] = None
    openings: Optional[int] = None

class JobResponse(BaseModel):
    id: int
    title: str
    department: str
    location: str
    job_type: str
    experience_min: int
    experience_max: int
    salary_min: Optional[float]
    salary_max: Optional[float]
    description: str
    requirements: Optional[str]
    skills: Optional[str]
    status: str
    openings: int
    created_at: dt.datetime
    applications_count: int = 0
    
    class Config:
        from_attributes = True


# ============== CANDIDATES ==============
class CandidateCreate(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    current_company: Optional[str] = None
    current_designation: Optional[str] = None
    experience_years: float = 0
    skills: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[str] = None
    expected_salary: Optional[float] = None
    notice_period_days: int = 0

class CandidateResponse(BaseModel):
    id: int
    full_name: str
    email: str
    phone: Optional[str]
    current_company: Optional[str]
    current_designation: Optional[str]
    experience_years: float
    skills: Optional[str]
    resume_url: Optional[str]
    linkedin_url: Optional[str]
    location: Optional[str]
    expected_salary: Optional[float]
    notice_period_days: int
    created_at: dt.datetime
    
    class Config:
        from_attributes = True


# ============== APPLICATIONS ==============
class ApplicationCreate(BaseModel):
    candidate_id: int
    job_id: int
    source: str = "website"
    notes: Optional[str] = None

class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None

class ApplicationResponse(BaseModel):
    id: int
    candidate_id: int
    job_id: int
    status: str
    source: str
    ai_score: Optional[float]
    ai_summary: Optional[str]
    notes: Optional[str]
    applied_at: dt.datetime
    candidate_name: str = ""
    candidate_email: str = ""
    job_title: str = ""
    
    class Config:
        from_attributes = True


# ============== INTERVIEWS ==============
class InterviewCreate(BaseModel):
    application_id: int
    candidate_id: int
    job_id: int
    interview_type: str = "technical"
    scheduled_at: dt.datetime
    duration_minutes: int = 60
    interviewer_name: Optional[str] = None
    interviewer_email: Optional[str] = None
    meeting_link: Optional[str] = None
    location: Optional[str] = None
    round_number: int = 1

class InterviewUpdate(BaseModel):
    status: Optional[str] = None
    technical_score: Optional[float] = None
    communication_score: Optional[float] = None
    cultural_fit_score: Optional[float] = None
    overall_score: Optional[float] = None
    recommendation: Optional[str] = None
    feedback: Optional[str] = None

class InterviewResponse(BaseModel):
    id: int
    application_id: int
    candidate_id: int
    job_id: int
    interview_type: str
    status: str
    scheduled_at: dt.datetime
    duration_minutes: int
    interviewer_name: Optional[str]
    meeting_link: Optional[str]
    ai_score: Optional[float]
    ai_feedback: Optional[str]
    overall_score: Optional[float]
    recommendation: Optional[str]
    feedback: Optional[str]
    round_number: int = 1
    candidate_name: str = ""
    job_title: str = ""
    
    class Config:
        from_attributes = True


# ============== EMPLOYEES ==============
class EmployeeCreate(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    date_of_birth: Optional[dt.date] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    official_address: Optional[str] = None
    corresponding_address: Optional[str] = None
    department_id: Optional[int] = None
    designation: Optional[str] = None
    employment_type: str = "full_time"
    joining_date: dt.date = dt.date.today()
    ctc: float = 0
    comp_off_balance: float = 0.0
    pan_number: Optional[str] = None
    aadhar_number: Optional[str] = None
    bank_account: Optional[str] = None
    bank_name: Optional[str] = None
    ifsc_code: Optional[str] = None

class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    official_address: Optional[str] = None
    corresponding_address: Optional[str] = None
    department_id: Optional[int] = None
    designation: Optional[str] = None
    employment_type: Optional[str] = None
    employment_status: Optional[str] = None
    ctc: Optional[float] = None
    comp_off_balance: Optional[float] = None
    reporting_manager_id: Optional[int] = None

class EmployeeResponse(BaseModel):
    id: int
    employee_id: str
    full_name: str
    email: str
    phone: Optional[str]
    date_of_birth: Optional[dt.date]
    gender: Optional[str]
    address: Optional[str] = None
    official_address: Optional[str] = None
    corresponding_address: Optional[str] = None
    department_id: Optional[int]
    department_name: str = ""
    designation: Optional[str]
    employment_type: str
    employment_status: str
    joining_date: dt.date
    ctc: float
    casual_leave_balance: float
    sick_leave_balance: float
    earned_leave_balance: float
    comp_off_balance: float = 0.0
    onboarding_status: str
    reporting_manager_id: Optional[int] = None
    avatar_url: Optional[str]
    is_active: bool
    created_at: dt.datetime
    
    class Config:
        from_attributes = True


# ============== ATTENDANCE ==============
class AttendanceCreate(BaseModel):
    employee_id: int
    attendance_date: dt.date = dt.date.today()
    status: str = "present"
    notes: Optional[str] = None

class AttendanceCheckIn(BaseModel):
    employee_id: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    image_base64: Optional[str] = None

class AttendanceResponse(BaseModel):
    id: int
    employee_id: int
    date: dt.date
    status: str
    check_in: Optional[dt.datetime]
    check_out: Optional[dt.datetime]
    work_hours: float
    employee_name: str = ""
    
    # Geolocation & Reverse Geocoded address fields
    check_in_lat: Optional[float] = None
    check_in_lon: Optional[float] = None
    check_out_lat: Optional[float] = None
    check_out_lon: Optional[float] = None
    check_in_address: Optional[str] = None
    check_out_address: Optional[str] = None
    check_in_district: Optional[str] = None
    check_in_state: Optional[str] = None
    check_out_district: Optional[str] = None
    check_out_state: Optional[str] = None
    
    class Config:
        from_attributes = True


# ============== LEAVES ==============
class LeaveRequestCreate(BaseModel):
    employee_id: int
    leave_type: str = "casual"
    start_date: dt.date
    end_date: dt.date
    reason: Optional[str] = None

class LeaveRequestUpdate(BaseModel):
    status: Optional[str] = None
    rejection_reason: Optional[str] = None
    start_date: Optional[dt.date] = None
    end_date: Optional[dt.date] = None
    reason: Optional[str] = None
    leave_type: Optional[str] = None

class LeaveRequestResponse(BaseModel):
    id: int
    employee_id: int
    leave_type: str
    start_date: dt.date
    end_date: dt.date
    days: float
    reason: Optional[str]
    status: str
    approved_by: Optional[int]
    employee_name: str = ""
    created_at: dt.datetime
    
    class Config:
        from_attributes = True


# ============== PAYROLL ==============
class PayrollRunCreate(BaseModel):
    month: int
    year: int

class PayslipResponse(BaseModel):
    id: int
    payroll_run_id: int
    employee_id: int
    month: int
    year: int
    basic_salary: float
    hra: float
    da: float
    special_allowance: float
    total_earnings: float
    pf_employee: float
    professional_tax: float
    tds: float
    total_deductions: float
    net_salary: float
    working_days: int
    present_days: int
    status: str
    employee_name: str = ""
    employee_code: str = ""
    department: str = ""
    designation: str = ""
    
    class Config:
        from_attributes = True

class PayrollRunResponse(BaseModel):
    id: int
    month: int
    year: int
    status: str
    total_employees: int
    total_gross: float
    total_deductions: float
    total_net: float
    processed_at: Optional[dt.datetime]
    payslips: List[PayslipResponse] = []
    
    class Config:
        from_attributes = True


# ============== PERFORMANCE ==============
class PerformanceReviewCreate(BaseModel):
    employee_id: int
    cycle: str = "annual"
    period: Optional[str] = None

class PerformanceReviewUpdate(BaseModel):
    technical_rating: Optional[float] = None
    communication_rating: Optional[float] = None
    leadership_rating: Optional[float] = None
    teamwork_rating: Optional[float] = None
    innovation_rating: Optional[float] = None
    overall_rating: Optional[float] = None
    self_review: Optional[str] = None
    manager_review: Optional[str] = None
    strengths: Optional[str] = None
    improvements: Optional[str] = None
    recommendation: Optional[str] = None
    status: Optional[str] = None

class PerformanceReviewResponse(BaseModel):
    id: int
    employee_id: int
    cycle: str
    period: Optional[str]
    status: str
    technical_rating: Optional[float]
    communication_rating: Optional[float]
    leadership_rating: Optional[float]
    teamwork_rating: Optional[float]
    innovation_rating: Optional[float]
    overall_rating: Optional[float]
    self_review: Optional[str]
    manager_review: Optional[str]
    recommendation: Optional[str]
    employee_name: str = ""
    created_at: dt.datetime
    
    class Config:
        from_attributes = True

class GoalCreate(BaseModel):
    employee_id: int
    title: str
    description: Optional[str] = None
    target_date: Optional[dt.datetime] = None
    priority: str = "medium"

class GoalResponse(BaseModel):
    id: int
    employee_id: int
    title: str
    description: Optional[str]
    target_date: Optional[dt.datetime]
    status: str
    progress: int
    priority: str
    
    class Config:
        from_attributes = True


# ============== OFFBOARDING ==============
class ResignationCreate(BaseModel):
    employee_id: int
    reason: Optional[str] = None
    notice_period_days: int = 30

class ResignationUpdate(BaseModel):
    status: Optional[str] = None
    manager_remarks: Optional[str] = None
    hr_remarks: Optional[str] = None
    last_working_day: Optional[dt.date] = None
    exit_feedback: Optional[str] = None
    exit_rating: Optional[int] = None
    would_recommend: Optional[bool] = None
    reason_for_leaving: Optional[str] = None
    assets_returned: Optional[bool] = None

class ResignationResponse(BaseModel):
    id: int
    employee_id: int
    reason: Optional[str]
    resignation_date: dt.date
    last_working_day: Optional[dt.date]
    notice_period_days: int
    status: str
    exit_interview_done: bool
    assets_returned: bool
    experience_letter_generated: bool
    relieving_letter_generated: bool
    fnf_generated: bool
    total_settlement: float
    employee_name: str = ""
    employee_code: str = ""
    department: str = ""
    designation: str = ""
    created_at: dt.datetime
    
    class Config:
        from_attributes = True


# ============== DASHBOARD ==============
class DashboardStats(BaseModel):
    total_employees: int = 0
    active_employees: int = 0
    open_positions: int = 0
    total_applications: int = 0
    interviews_today: int = 0
    pending_leaves: int = 0
    pending_resignations: int = 0
    this_month_payroll: float = 0
    new_hires_this_month: int = 0
    attrition_rate: float = 0
    casual_leave_balance: float = 0
    sick_leave_balance: float = 0
    earned_leave_balance: float = 0
    work_hours_this_month: float = 0
    present_days_this_month: int = 0
    active_goals_count: int = 0

class DepartmentStats(BaseModel):
    name: str
    count: int

class HiringFunnelData(BaseModel):
    stage: str
    count: int

class RecentActivity(BaseModel):
    id: int
    type: str
    message: str
    timestamp: dt.datetime


# ============== COMP-OFF ==============
class CompOffRuleResponse(BaseModel):
    id: int
    standard_working_hours: float
    min_overtime_hours: float
    is_active: int
    
    class Config:
        from_attributes = True

class CompOffRuleUpdate(BaseModel):
    standard_working_hours: Optional[float] = None
    min_overtime_hours: Optional[float] = None

class CompOffRequestCreate(BaseModel):
    attendance_date: dt.date
    reason: Optional[str] = None

class CompOffRequestResponse(BaseModel):
    id: int
    employee_id: int
    attendance_date: dt.date
    working_hours: float
    overtime_hours: float
    reason: Optional[str]
    manager_status: str
    manager_id: Optional[int]
    manager_action_at: Optional[dt.datetime]
    hr_status: str
    hr_id: Optional[int]
    hr_action_at: Optional[dt.datetime]
    status: str
    created_at: dt.datetime
    employee_name: str = ""
    
    class Config:
        from_attributes = True

class CompOffRequestAction(BaseModel):
    action: str  # approve, reject

