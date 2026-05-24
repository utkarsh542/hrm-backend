"""HRMS Backend — FastAPI Application Entry Point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import create_tables
from app.routers import (
    auth, dashboard, jobs, candidates, interviews, employees,
    attendance, payroll, performance, offboarding, ai_copilot,
    documents, expenses, face_attendance, benchmarking,
    notifications, search, onboarding, engagement, workflows,
    skills, analytics, resume,
)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-Powered HR Automation Platform — Next-Gen HRMS",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for uploads and generated docs
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
app.mount("/generated", StaticFiles(directory=settings.GENERATED_DIR), name="generated")

# Include all routers — Core
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(jobs.router)
app.include_router(candidates.router)
app.include_router(interviews.router)
app.include_router(employees.router)
app.include_router(attendance.router)
app.include_router(payroll.router)
app.include_router(performance.router)
app.include_router(offboarding.router)
app.include_router(ai_copilot.router)
app.include_router(documents.router)
app.include_router(expenses.router)
app.include_router(face_attendance.router)
app.include_router(benchmarking.router)
# Include all routers — New AI-Powered Features
app.include_router(notifications.router)
app.include_router(search.router)
app.include_router(onboarding.router)
app.include_router(engagement.router)
app.include_router(workflows.router)
app.include_router(skills.router)
app.include_router(analytics.router)
app.include_router(resume.router)


@app.on_event("startup")
def startup():
    # Import all models so SQLAlchemy registers them before create_tables
    from app.models import user, employee, job, candidate, interview, attendance, payroll, performance, offboarding, document, expense, face_attendance  # noqa
    create_tables()
    seed_demo_data()
    fix_manager_relationships()


@app.get("/api/health")
def health():
    return {"status": "healthy", "app": settings.APP_NAME, "version": settings.APP_VERSION}


def seed_demo_data():
    """Seed the database with demo data for immediate use."""
    from app.database import SessionLocal
    from app.models.expense import Expense
    from app.models.face_attendance import FaceAttendance
    from app.models.user import User, UserRole
    from app.models.employee import Employee, Department
    from app.models.job import Job, JobStatus, JobType
    from app.models.candidate import Candidate, Application, ApplicationStatus, ApplicationSource
    from app.models.interview import Interview, InterviewType, InterviewStatus
    from app.models.attendance import Holiday, LeaveRequest, LeaveType, LeaveStatus, Attendance, AttendanceStatus
    from app.models.payroll import PayrollRun, Payslip
    from app.models.performance import PerformanceReview, Goal, ReviewCycle, GoalStatus
    from app.models.offboarding import Resignation, ResignationStatus
    from app.services.auth_service import hash_password
    from app.services.payroll_service import calculate_salary_breakup
    from app.services.ai_service import screen_resume
    from datetime import datetime, date, timedelta
    import random
    
    db = SessionLocal()
    
    # Only seed if DB is empty
    if db.query(User).first():
        db.close()
        return
    
    try:
        # ===== USERS =====
        users = [
            User(email="admin@techcorp.com", hashed_password=hash_password("admin123"), full_name="Rajesh Kumar", role=UserRole.ADMIN, avatar_url=""),
            User(email="hr@techcorp.com", hashed_password=hash_password("hr123"), full_name="Priya Sharma", role=UserRole.HR, avatar_url=""),
            User(email="manager@techcorp.com", hashed_password=hash_password("manager123"), full_name="Amit Patel", role=UserRole.MANAGER, avatar_url=""),
            User(email="employee@techcorp.com", hashed_password=hash_password("employee123"), full_name="Sneha Reddy", role=UserRole.EMPLOYEE, avatar_url=""),
        ]
        db.add_all(users)
        db.commit()
        
        # ===== DEPARTMENTS =====
        departments = [
            Department(name="Engineering", description="Software development and architecture"),
            Department(name="Human Resources", description="People operations and talent management"),
            Department(name="Marketing", description="Brand, content, and digital marketing"),
            Department(name="Sales", description="Business development and client relations"),
            Department(name="Finance", description="Accounting, payroll, and financial planning"),
            Department(name="Product", description="Product management and strategy"),
            Department(name="Design", description="UI/UX and visual design"),
            Department(name="Operations", description="Infrastructure and IT operations"),
        ]
        db.add_all(departments)
        db.commit()
        
        # ===== EMPLOYEES =====
        emp_data = [
            ("Rajesh Kumar", "rajesh@techcorp.com", "M", 1, "VP Engineering", 2800000, "2020-01-15"),
            ("Priya Sharma", "priya@techcorp.com", "F", 2, "HR Director", 2200000, "2019-06-01"),
            ("Amit Patel", "amit@techcorp.com", "M", 1, "Tech Lead", 2400000, "2021-03-10"),
            ("Sneha Reddy", "sneha@techcorp.com", "F", 1, "Senior Developer", 1800000, "2022-07-20"),
            ("Vikram Singh", "vikram@techcorp.com", "M", 4, "Sales Manager", 1600000, "2021-09-01"),
            ("Ananya Iyer", "ananya@techcorp.com", "F", 3, "Marketing Lead", 1500000, "2022-01-10"),
            ("Rahul Verma", "rahul@techcorp.com", "M", 1, "Full Stack Developer", 1200000, "2023-02-15"),
            ("Deepika Nair", "deepika@techcorp.com", "F", 5, "Finance Manager", 2000000, "2020-08-20"),
            ("Arjun Mehta", "arjun@techcorp.com", "M", 6, "Product Manager", 2100000, "2021-11-05"),
            ("Kavya Joshi", "kavya@techcorp.com", "F", 7, "UI/UX Designer", 1400000, "2022-04-15"),
            ("Sanjay Gupta", "sanjay@techcorp.com", "M", 8, "DevOps Engineer", 1700000, "2022-06-01"),
            ("Meera Krishnan", "meera@techcorp.com", "F", 1, "QA Engineer", 1100000, "2023-05-20"),
            ("Rohan Desai", "rohan@techcorp.com", "M", 1, "Junior Developer", 800000, "2024-01-10"),
            ("Pooja Aggarwal", "pooja@techcorp.com", "F", 2, "HR Executive", 900000, "2023-08-15"),
            ("Karthik Raman", "karthik@techcorp.com", "M", 4, "Sales Executive", 700000, "2024-03-01"),
        ]
        
        # Map user email/role to user ID by full name
        user_map = {u.full_name: u for u in users}
        
        employees = []
        for i, (name, email, gender, dept_id, desig, ctc, join_date) in enumerate(emp_data):
            breakup = calculate_salary_breakup(ctc)
            matched_user = user_map.get(name)
            user_id = matched_user.id if matched_user else None
            emp_email = matched_user.email if matched_user else email
            
            emp = Employee(
                user_id=user_id,
                employee_id=f"EMP{i+1:04d}",
                full_name=name,
                email=emp_email,
                phone=f"+91-98{random.randint(10000000, 99999999)}",
                gender=gender,
                date_of_birth=date(1985 + random.randint(0, 15), random.randint(1, 12), random.randint(1, 28)),
                department_id=dept_id,
                designation=desig,
                joining_date=date.fromisoformat(join_date),
                ctc=ctc,
                basic_salary=breakup["basic"],
                hra=breakup["hra"],
                da=breakup["da"],
                special_allowance=breakup["special_allowance"],
                pf_contribution=breakup["pf_employee"],
                onboarding_status="completed",
                casual_leave_balance=random.randint(5, 12),
                sick_leave_balance=random.randint(6, 12),
                earned_leave_balance=random.randint(5, 15),
                address=f"{random.randint(1, 500)}, Sector {random.randint(1, 50)}, Bangalore, Karnataka",
                pan_number=f"ABCDE{random.randint(1000, 9999)}F",
                bank_account=f"{random.randint(10000000000, 99999999999)}",
                bank_name="HDFC Bank",
                ifsc_code="HDFC0001234",
            )
            employees.append(emp)
        
        db.add_all(employees)
        db.commit()
        
        # ===== JOBS =====
        jobs = [
            Job(title="Senior Full Stack Developer", department="Engineering", location="Bangalore", 
                job_type=JobType.FULL_TIME, experience_min=4, experience_max=8, salary_min=1500000, salary_max=2500000,
                description="We're looking for an experienced Full Stack Developer proficient in React, Node.js, and Python to join our engineering team.",
                requirements="Strong experience with React/Next.js, Python/FastAPI, PostgreSQL, Docker, CI/CD",
                skills="React,Node.js,Python,PostgreSQL,Docker,AWS,TypeScript", openings=2, status=JobStatus.OPEN),
            Job(title="Product Designer", department="Design", location="Bangalore",
                job_type=JobType.FULL_TIME, experience_min=3, experience_max=6, salary_min=1200000, salary_max=2000000,
                description="Join our design team to create beautiful and intuitive user experiences.",
                requirements="Figma, Design Systems, User Research, Prototyping",
                skills="Figma,UI/UX,Design Systems,Prototyping,User Research", openings=1, status=JobStatus.OPEN),
            Job(title="DevOps Engineer", department="Engineering", location="Bangalore (Remote)",
                job_type=JobType.FULL_TIME, experience_min=3, experience_max=7, salary_min=1400000, salary_max=2200000,
                description="Looking for a DevOps engineer to manage our cloud infrastructure and CI/CD pipelines.",
                requirements="AWS/GCP, Kubernetes, Docker, Terraform, CI/CD",
                skills="AWS,Kubernetes,Docker,Terraform,Jenkins,Linux,Python", openings=1, status=JobStatus.OPEN),
            Job(title="Marketing Intern", department="Marketing", location="Bangalore",
                job_type=JobType.INTERNSHIP, experience_min=0, experience_max=1, salary_min=15000, salary_max=25000,
                description="Exciting internship opportunity for marketing enthusiasts.",
                skills="Social Media,Content Writing,SEO,Google Analytics", openings=2, status=JobStatus.OPEN),
            Job(title="Data Analyst", department="Product", location="Bangalore",
                job_type=JobType.FULL_TIME, experience_min=2, experience_max=5, salary_min=1000000, salary_max=1800000,
                description="Analyze data to drive product decisions.", skills="Python,SQL,Tableau,Statistics",
                openings=1, status=JobStatus.CLOSED),
        ]
        db.add_all(jobs)
        db.commit()
        
        # ===== CANDIDATES =====
        candidate_data = [
            ("Arun Saxena", "arun.saxena@gmail.com", "Google", "SDE-3", 6.5, "React,Python,Node.js,PostgreSQL,Docker,AWS", 2000000),
            ("Neha Kapoor", "neha.k@gmail.com", "Microsoft", "SDE-2", 4.0, "React,TypeScript,Next.js,MongoDB", 1600000),
            ("Suresh Babu", "suresh.b@gmail.com", "Flipkart", "Senior Engineer", 5.0, "Python,FastAPI,Django,PostgreSQL,Redis", 1800000),
            ("Divya Menon", "divya.m@gmail.com", "Swiggy", "Frontend Developer", 3.5, "React,CSS,JavaScript,Figma", 1200000),
            ("Manish Tiwari", "manish.t@gmail.com", "Infosys", "System Engineer", 2.0, "Java,Python,SQL,Linux", 900000),
            ("Ritu Jain", "ritu.j@gmail.com", "Adobe", "Product Designer", 4.0, "Figma,Sketch,UI/UX,Prototyping,Design Systems", 1500000),
            ("Gaurav Sharma", "gaurav.s@gmail.com", "TCS", "DevOps Engineer", 3.5, "AWS,Docker,Kubernetes,Jenkins,Terraform", 1300000),
            ("Pallavi Das", "pallavi.d@gmail.com", "Freshworks", "QA Lead", 5.5, "Selenium,Python,API Testing,JIRA", 1400000),
        ]
        
        candidates = []
        for name, email, company, desig, exp, skills, expected in candidate_data:
            c = Candidate(
                full_name=name, email=email, phone=f"+91-97{random.randint(10000000, 99999999)}",
                current_company=company, current_designation=desig,
                experience_years=exp, skills=skills, expected_salary=expected,
                location="Bangalore", notice_period_days=random.choice([15, 30, 60, 90]),
            )
            candidates.append(c)
        db.add_all(candidates)
        db.commit()
        
        # ===== APPLICATIONS =====
        applications = []
        job_list = db.query(Job).all()
        candidate_list = db.query(Candidate).all()
        
        app_mappings = [
            (1, 1, "applied"), (2, 1, "screening"), (3, 1, "shortlisted"),
            (4, 1, "interview"), (5, 1, "rejected"),
            (6, 2, "applied"), (7, 3, "shortlisted"), (8, 1, "offered"),
        ]
        
        for cand_idx, job_idx, status in app_mappings:
            if cand_idx <= len(candidate_list) and job_idx <= len(job_list):
                cand = candidate_list[cand_idx - 1]
                job = job_list[job_idx - 1]
                screening = screen_resume(cand.skills or "", job.skills or "", cand.experience_years)
                app = Application(
                    candidate_id=cand.id, job_id=job.id,
                    status=ApplicationStatus(status),
                    source=random.choice(list(ApplicationSource)),
                    ai_score=screening["score"],
                    ai_summary=screening["summary"],
                    applied_at=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                )
                applications.append(app)
        db.add_all(applications)
        db.commit()
        
        # ===== INTERVIEWS =====
        interviews = []
        app_list = db.query(Application).filter(Application.status.in_([
            ApplicationStatus.INTERVIEW, ApplicationStatus.SHORTLISTED
        ])).all()
        
        for app in app_list:
            interview = Interview(
                application_id=app.id, candidate_id=app.candidate_id, job_id=app.job_id,
                interview_type=random.choice([InterviewType.TECHNICAL, InterviewType.HR, InterviewType.BEHAVIORAL]),
                status=InterviewStatus.SCHEDULED,
                scheduled_at=datetime.utcnow() + timedelta(days=random.randint(1, 7), hours=random.randint(9, 17)),
                duration_minutes=60,
                interviewer_name="Amit Patel",
                meeting_link=f"https://meet.hrms.com/interview-{app.id}",
            )
            interviews.append(interview)
        db.add_all(interviews)
        db.commit()
        
        # ===== LEAVE REQUESTS =====
        leave_requests = [
            LeaveRequest(employee_id=4, leave_type=LeaveType.CASUAL, start_date=date.today() + timedelta(days=5),
                        end_date=date.today() + timedelta(days=6), days=2, reason="Personal work", status=LeaveStatus.PENDING),
            LeaveRequest(employee_id=7, leave_type=LeaveType.SICK, start_date=date.today() - timedelta(days=2),
                        end_date=date.today() - timedelta(days=1), days=2, reason="Fever", status=LeaveStatus.APPROVED, approved_by=1),
            LeaveRequest(employee_id=10, leave_type=LeaveType.EARNED, start_date=date.today() + timedelta(days=10),
                        end_date=date.today() + timedelta(days=14), days=5, reason="Family vacation", status=LeaveStatus.PENDING),
        ]
        db.add_all(leave_requests)
        db.commit()
        
        # ===== HOLIDAYS =====
        holidays = [
            Holiday(name="Republic Day", date=date(2026, 1, 26), type="national"),
            Holiday(name="Holi", date=date(2026, 3, 14), type="national"),
            Holiday(name="Good Friday", date=date(2026, 4, 3), type="national"),
            Holiday(name="May Day", date=date(2026, 5, 1), type="national"),
            Holiday(name="Independence Day", date=date(2026, 8, 15), type="national"),
            Holiday(name="Gandhi Jayanti", date=date(2026, 10, 2), type="national"),
            Holiday(name="Dussehra", date=date(2026, 10, 22), type="national"),
            Holiday(name="Diwali", date=date(2026, 11, 12), type="national"),
            Holiday(name="Christmas", date=date(2026, 12, 25), type="national"),
        ]
        db.add_all(holidays)
        db.commit()
        
        # ===== PERFORMANCE REVIEWS =====
        reviews = [
            PerformanceReview(employee_id=3, cycle=ReviewCycle.ANNUAL, period="2025", status="completed",
                            technical_rating=4.5, communication_rating=4.0, leadership_rating=4.2,
                            teamwork_rating=4.3, innovation_rating=4.1, overall_rating=4.2,
                            manager_review="Amit has shown exceptional technical leadership.", recommendation="promote"),
            PerformanceReview(employee_id=4, cycle=ReviewCycle.ANNUAL, period="2025", status="completed",
                            technical_rating=4.0, communication_rating=4.5, leadership_rating=3.5,
                            teamwork_rating=4.2, innovation_rating=3.8, overall_rating=4.0,
                            manager_review="Sneha consistently delivers high-quality work.", recommendation="increment"),
            PerformanceReview(employee_id=7, cycle=ReviewCycle.ANNUAL, period="2025", status="pending"),
        ]
        db.add_all(reviews)
        db.commit()
        
        # ===== GOALS =====
        goals = [
            Goal(employee_id=3, title="Lead microservices migration", description="Migrate monolith to microservices",
                 status=GoalStatus.IN_PROGRESS, progress=60, priority="high"),
            Goal(employee_id=4, title="Complete AWS certification", progress=30, priority="medium"),
            Goal(employee_id=7, title="Build 3 feature modules", progress=40, priority="high"),
        ]
        db.add_all(goals)
        db.commit()
        
        # ===== RESIGNATION (sample) =====
        resignation = Resignation(
            employee_id=11, reason="Pursuing higher studies",
            resignation_date=date.today() - timedelta(days=10),
            last_working_day=date.today() + timedelta(days=20),
            notice_period_days=30, status=ResignationStatus.HR_PROCESSING,
        )
        db.add(resignation)
        
        # Update employee status
        emp11 = db.query(Employee).filter(Employee.id == 11).first()
        if emp11:
            emp11.employment_status = "on_notice"
        
        db.commit()
        
        print("[OK] Demo data seeded successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"[WARN] Seed error (may already exist): {e}")
    finally:
        db.close()


def fix_manager_relationships():
    """Fix manager relationships for existing seeded employees in-place on startup."""
    from app.database import SessionLocal
    from app.models.employee import Employee
    
    db = SessionLocal()
    try:
        employees = db.query(Employee).all()
        # If any employee already has a reporting manager, we assume they are configured
        if any(emp.reporting_manager_id is not None for emp in employees):
            db.close()
            return
            
        emp_map = {e.full_name: e for e in employees}
        
        # Engineering Hierarchy
        vp = emp_map.get("Rajesh Kumar")
        tl = emp_map.get("Amit Patel")
        
        if tl and vp:
            tl.reporting_manager_id = vp.id
            
        eng_staff = ["Sneha Reddy", "Rahul Verma", "Meera Krishnan", "Rohan Desai"]
        for name in eng_staff:
            e = emp_map.get(name)
            if e and tl:
                e.reporting_manager_id = tl.id
                
        # HR Hierarchy
        hr_dir = emp_map.get("Priya Sharma")
        hr_exec = emp_map.get("Pooja Aggarwal")
        if hr_dir and vp:
            hr_dir.reporting_manager_id = vp.id
        if hr_exec and hr_dir:
            hr_exec.reporting_manager_id = hr_dir.id
            
        # Sales Hierarchy
        sales_mgr = emp_map.get("Vikram Singh")
        sales_exec = emp_map.get("Karthik Raman")
        if sales_mgr and vp:
            sales_mgr.reporting_manager_id = vp.id
        if sales_exec and sales_mgr:
            sales_exec.reporting_manager_id = sales_mgr.id
            
        db.commit()
        print("[OK] Manager relationships configured successfully in existing database!")
    except Exception as e:
        print(f"Error fixing manager relationships: {e}")
    finally:
        db.close()
