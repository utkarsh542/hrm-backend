"""Dashboard router — KPIs, stats, hiring funnel, recent activity."""
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.employee import Employee, EmploymentStatus
from app.models.job import Job, JobStatus
from app.models.candidate import Application, ApplicationStatus
from app.models.interview import Interview, InterviewStatus
from app.models.attendance import LeaveRequest, LeaveStatus
from app.models.offboarding import Resignation, ResignationStatus
from app.models.payroll import PayrollRun
from app.schemas.schemas import DashboardStats, DepartmentStats, HiringFunnelData, RecentActivity

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_employees = db.query(Employee).count()
    active_employees = db.query(Employee).filter(Employee.employment_status == EmploymentStatus.ACTIVE).count()
    open_positions = db.query(Job).filter(Job.status == JobStatus.OPEN).count()
    total_applications = db.query(Application).count()
    
    today = date.today()
    interviews_today = db.query(Interview).filter(
        func.date(Interview.scheduled_at) == today,
        Interview.status == InterviewStatus.SCHEDULED
    ).count()
    
    pending_leaves = db.query(LeaveRequest).filter(LeaveRequest.status == LeaveStatus.PENDING).count()
    pending_resignations = db.query(Resignation).filter(
        Resignation.status.in_([ResignationStatus.SUBMITTED, ResignationStatus.MANAGER_APPROVED])
    ).count()
    
    # New hires this month
    first_of_month = today.replace(day=1)
    new_hires = db.query(Employee).filter(Employee.joining_date >= first_of_month).count()
    
    return DashboardStats(
        total_employees=total_employees,
        active_employees=active_employees,
        open_positions=open_positions,
        total_applications=total_applications,
        interviews_today=interviews_today,
        pending_leaves=pending_leaves,
        pending_resignations=pending_resignations,
        new_hires_this_month=new_hires,
        attrition_rate=round((pending_resignations / max(total_employees, 1)) * 100, 1),
    )


@router.get("/department-stats", response_model=list[DepartmentStats])
def get_department_stats(db: Session = Depends(get_db)):
    from app.models.employee import Department
    departments = db.query(Department).all()
    
    # Calculate all counts in a single query using group_by
    counts = db.query(Employee.department_id, func.count(Employee.id))\
        .filter(Employee.is_active == True)\
        .group_by(Employee.department_id).all()
    count_map = {dept_id: count for dept_id, count in counts}
    
    result = []
    for dept in departments:
        count = count_map.get(dept.id, 0)
        result.append(DepartmentStats(name=dept.name, count=count))
    return result


@router.get("/hiring-funnel", response_model=list[HiringFunnelData])
def get_hiring_funnel(db: Session = Depends(get_db)):
    stages = [
        ("Applied", ApplicationStatus.APPLIED),
        ("Screening", ApplicationStatus.SCREENING),
        ("Shortlisted", ApplicationStatus.SHORTLISTED),
        ("Interview", ApplicationStatus.INTERVIEW),
        ("Offered", ApplicationStatus.OFFERED),
        ("Hired", ApplicationStatus.HIRED),
    ]
    result = []
    for label, status in stages:
        count = db.query(Application).filter(Application.status == status).count()
        result.append(HiringFunnelData(stage=label, count=count))
    return result


@router.get("/recent-activity", response_model=list[RecentActivity])
def get_recent_activity(db: Session = Depends(get_db)):
    activities = []
    
    # Recent applications
    recent_apps = db.query(Application).order_by(Application.applied_at.desc()).limit(5).all()
    from app.models.candidate import Candidate
    
    if recent_apps:
        cand_ids = [app.candidate_id for app in recent_apps]
        job_ids = [app.job_id for app in recent_apps]
        candidates = {c.id: c for c in db.query(Candidate).filter(Candidate.id.in_(cand_ids)).all()}
        jobs = {j.id: j for j in db.query(Job).filter(Job.id.in_(job_ids)).all()}
        
        for app in recent_apps:
            candidate = candidates.get(app.candidate_id)
            job = jobs.get(app.job_id)
            if candidate and job:
                activities.append(RecentActivity(
                    id=app.id,
                    type="application",
                    message=f"{candidate.full_name} applied for {job.title}",
                    timestamp=app.applied_at,
                ))
    
    # Recent interviews
    recent_interviews = db.query(Interview).order_by(Interview.created_at.desc()).limit(3).all()
    if recent_interviews:
        cand_ids = [interview.candidate_id for interview in recent_interviews]
        candidates = {c.id: c for c in db.query(Candidate).filter(Candidate.id.in_(cand_ids)).all()}
        
        for interview in recent_interviews:
            candidate = candidates.get(interview.candidate_id)
            if candidate:
                activities.append(RecentActivity(
                    id=interview.id,
                    type="interview",
                    message=f"Interview scheduled with {candidate.full_name}",
                    timestamp=interview.created_at,
                ))
    
    # Recent leaves
    recent_leaves = db.query(LeaveRequest).order_by(LeaveRequest.created_at.desc()).limit(3).all()
    if recent_leaves:
        emp_ids = [leave.employee_id for leave in recent_leaves]
        employees = {e.id: e for e in db.query(Employee).filter(Employee.id.in_(emp_ids)).all()}
        
        for leave in recent_leaves:
            emp = employees.get(leave.employee_id)
            if emp:
                activities.append(RecentActivity(
                    id=leave.id,
                    type="leave",
                    message=f"{emp.full_name} requested {leave.leave_type.value} leave",
                    timestamp=leave.created_at,
                ))
    
    activities.sort(key=lambda x: x.timestamp, reverse=True)
    return activities[:10]
