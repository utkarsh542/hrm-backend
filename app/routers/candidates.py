"""Candidates & Applications router."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.candidate import Candidate, Application, ApplicationStatus
from app.models.job import Job
from app.schemas.schemas import (
    CandidateCreate, CandidateResponse,
    ApplicationCreate, ApplicationUpdate, ApplicationResponse
)
from app.services.ai_service import screen_resume

router = APIRouter(prefix="/api/candidates", tags=["Candidates"])


# ===== CANDIDATES =====
@router.get("/", response_model=list[CandidateResponse])
def list_candidates(search: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Candidate)
    if search:
        query = query.filter(
            (Candidate.full_name.ilike(f"%{search}%")) |
            (Candidate.email.ilike(f"%{search}%")) |
            (Candidate.skills.ilike(f"%{search}%"))
        )
    return [CandidateResponse.model_validate(c) for c in query.order_by(Candidate.created_at.desc()).all()]


@router.post("/", response_model=CandidateResponse)
def create_candidate(request: CandidateCreate, db: Session = Depends(get_db)):
    existing = db.query(Candidate).filter(Candidate.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Candidate with this email already exists")
    
    candidate = Candidate(**request.model_dump())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return CandidateResponse.model_validate(candidate)


@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return CandidateResponse.model_validate(candidate)


# ===== APPLICATIONS =====
@router.get("/applications/all", response_model=list[ApplicationResponse])
def list_applications(
    status: Optional[str] = None,
    job_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Application)
    if status:
        query = query.filter(Application.status == ApplicationStatus(status))
    if job_id:
        query = query.filter(Application.job_id == job_id)
    
    applications = query.order_by(Application.applied_at.desc()).all()
    result = []
    for app in applications:
        candidate = db.query(Candidate).filter(Candidate.id == app.candidate_id).first()
        job = db.query(Job).filter(Job.id == app.job_id).first()
        resp = ApplicationResponse.model_validate(app)
        resp.candidate_name = candidate.full_name if candidate else ""
        resp.candidate_email = candidate.email if candidate else ""
        resp.job_title = job.title if job else ""
        result.append(resp)
    return result


@router.post("/applications/", response_model=ApplicationResponse)
def create_application(request: ApplicationCreate, db: Session = Depends(get_db)):
    # Verify candidate and job exist
    candidate = db.query(Candidate).filter(Candidate.id == request.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    job = db.query(Job).filter(Job.id == request.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check if already applied
    existing = db.query(Application).filter(
        Application.candidate_id == request.candidate_id,
        Application.job_id == request.job_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Candidate has already applied for this job")
    
    application = Application(**request.model_dump())
    
    # Run AI screening
    screening = screen_resume(
        candidate_skills=candidate.skills or "",
        job_requirements=job.skills or job.requirements or "",
        experience_years=candidate.experience_years
    )
    application.ai_score = screening["score"]
    application.ai_summary = screening["summary"]
    
    db.add(application)
    db.commit()
    db.refresh(application)
    
    resp = ApplicationResponse.model_validate(application)
    resp.candidate_name = candidate.full_name
    resp.candidate_email = candidate.email
    resp.job_title = job.title
    return resp


@router.put("/applications/{app_id}", response_model=ApplicationResponse)
def update_application(app_id: int, request: ApplicationUpdate, db: Session = Depends(get_db)):
    application = db.query(Application).filter(Application.id == app_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
        
    old_status = application.status
    
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "status":
            value = ApplicationStatus(value)
        setattr(application, key, value)
    
    db.commit()
    db.refresh(application)
    
    candidate = db.query(Candidate).filter(Candidate.id == application.candidate_id).first()
    job = db.query(Job).filter(Job.id == application.job_id).first()
    
    # ── Hook: Candidate officially JOINED (Promote to Active Employee) ──
    if application.status == ApplicationStatus.JOINED and old_status != ApplicationStatus.JOINED:
        from app.models.employee import Employee, EmploymentStatus, EmploymentType, OnboardingStatus
        existing_emp = db.query(Employee).filter(Employee.email == candidate.email).first()
        if not existing_emp:
            # Generate next EMPxxx ID
            emp_count = db.query(Employee).count()
            next_emp_id = f"EMP{emp_count + 1:03d}"
            
            # Extract offer parameters from notes if present
            import re
            ctc_val = 0.0
            basic_val = 0.0
            hra_val = 0.0
            special_val = 0.0
            
            if application.notes:
                ctc_match = re.search(r"OFFER_CTC:\s*([\d\.]+)", application.notes)
                if ctc_match:
                    ctc_val = float(ctc_match.group(1))
                    basic_val = ctc_val * 0.5 / 12.0
                    hra_val = ctc_val * 0.2 / 12.0
                    special_val = ctc_val * 0.3 / 12.0
            
            new_emp = Employee(
                employee_id=next_emp_id,
                full_name=candidate.full_name,
                email=candidate.email,
                phone=candidate.phone,
                designation=job.title if job else "Employee",
                ctc=ctc_val,
                basic_salary=basic_val,
                hra=hra_val,
                special_allowance=special_val,
                employment_type=EmploymentType.FULL_TIME,
                employment_status=EmploymentStatus.ACTIVE,
                onboarding_status=OnboardingStatus.PENDING,
                is_active=True
            )
            db.add(new_emp)
            db.commit()
            
            # Create a User account for login
            from app.models.user import User, UserRole
            from app.services.auth_service import hash_password
            import random
            import string
            
            existing_user = db.query(User).filter(User.email == candidate.email).first()
            if not existing_user:
                temp_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
                hashed_pass = hash_password(temp_pass)
                
                new_user = User(
                    email=candidate.email,
                    full_name=candidate.full_name,
                    hashed_password=hashed_pass,
                    role=UserRole.EMPLOYEE,
                    is_active=True
                )
                db.add(new_user)
                db.commit()
                db.refresh(new_user)
                
                new_emp.user_id = new_user.id
                db.commit()
                
                try:
                    from app.services.email_service import send_welcome_email
                    send_welcome_email(candidate.email, candidate.full_name, temp_pass)
                except Exception as e:
                    print("Failed to send welcome email:", e)
                    


    resp = ApplicationResponse.model_validate(application)
    resp.candidate_name = candidate.full_name if candidate else ""
    resp.candidate_email = candidate.email if candidate else ""
    resp.job_title = job.title if job else ""
    return resp


@router.get("/applications/pipeline")
def get_pipeline(db: Session = Depends(get_db)):
    """Get all applications grouped by status for Kanban view."""
    statuses = [s.value for s in ApplicationStatus]
    pipeline = {}
    for status in statuses:
        apps = db.query(Application).filter(Application.status == ApplicationStatus(status)).all()
        items = []
        for app in apps:
            candidate = db.query(Candidate).filter(Candidate.id == app.candidate_id).first()
            job = db.query(Job).filter(Job.id == app.job_id).first()
            items.append({
                "id": app.id,
                "candidate_id": app.candidate_id,
                "candidate_name": candidate.full_name if candidate else "",
                "candidate_email": candidate.email if candidate else "",
                "job_id": app.job_id,
                "job_title": job.title if job else "",
                "ai_score": app.ai_score,
                "source": app.source.value if app.source else "website",
                "applied_at": app.applied_at.isoformat() if app.applied_at else "",
            })
        pipeline[status] = items
    return pipeline


from pydantic import BaseModel

class OfferLetterRequest(BaseModel):
    ctc: float
    joining_date: str
    probation_months: int = 6
    valid_until: str

@router.post("/applications/{app_id}/send-offer")
def send_offer_letter(app_id: int, req: OfferLetterRequest, db: Session = Depends(get_db)):
    application = db.query(Application).filter(Application.id == app_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
        
    candidate = db.query(Candidate).filter(Candidate.id == application.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    job = db.query(Job).filter(Job.id == application.job_id).first()
    job_title = job.title if job else "Software Engineer"
    
    # Calculate Annexure breakdown
    monthly_ctc = req.ctc / 12.0
    basic = monthly_ctc * 0.5
    hra = monthly_ctc * 0.2
    special = monthly_ctc * 0.3
    
    # Format dates beautifully
    from datetime import datetime
    try:
        join_fmt = datetime.strptime(req.joining_date, "%Y-%m-%d").strftime("%d %b %Y")
    except:
        join_fmt = req.joining_date
        
    try:
        valid_fmt = datetime.strptime(req.valid_until, "%Y-%m-%d").strftime("%d %b %Y")
    except:
        valid_fmt = req.valid_until

    # Save to notes for candidate promotion hook
    application.notes = (
        f"OFFER_CTC: {req.ctc}\n"
        f"JOIN_DATE: {req.joining_date}\n"
        f"PROBATION: {req.probation_months}\n"
        f"VALID_UNTIL: {req.valid_until}\n"
        f"OFFER_SENT_AT: {datetime.utcnow().isoformat()}\n"
    )
    application.status = ApplicationStatus.OFFERED
    db.commit()
    
    # Send detailed email with Annexure table attached as PDF
    try:
        from app.services.email_service import send_email_with_attachment
        from app.services.pdf_service import generate_offer_letter_pdf
        
        # Generate the PDF content bytes
        pdf_bytes = generate_offer_letter_pdf(
            candidate_name=candidate.full_name,
            job_title=job_title,
            ctc=req.ctc,
            joining_date=join_fmt,
            probation_months=req.probation_months,
            valid_until=valid_fmt
        )
        
        subject = f"Official Job Offer: {job_title} — TechCorp Solutions"
        
        text_content = (
            f"Dear {candidate.full_name},\n\n"
            f"We are pleased to extend you a formal offer of employment at TechCorp Solutions Pvt. Ltd. for the position of {job_title}.\n\n"
            f"Your formal Offer Letter, Salary Annexure, and Company Terms & Policies have been generated and are attached as a PDF file to this email.\n\n"
            f"Please review the attached PDF document carefully. To accept the offer, please sign the letter and respond back to our talent acquisition team before the offer validity expires on {valid_fmt}.\n\n"
            f"We look forward to having you join our team and make a massive impact together!\n\n"
            f"Best regards,\n"
            f"TechCorp Recruitment Team"
        )
        
        html_content = (
            f"<div style='font-family: sans-serif; max-width: 550px; margin: auto; padding: 28px; border: 1px solid #ddd; border-radius: 16px; background-color: #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.05);'>"
            f"  <div style='text-align: center; border-bottom: 2px solid #6c63ff; padding-bottom: 16px; margin-bottom: 24px;'>"
            f"    <h2 style='color: #6c63ff; margin: 0; font-size: 24px;'>TechCorp Solutions Pvt. Ltd.</h2>"
            f"    <p style='color: #888; margin: 4px 0 0 0; font-size: 12px;'>123 Tech Park, Bangalore, KA 560001</p>"
            f"  </div>"
            f"  <p>Dear <strong>{candidate.full_name}</strong>,</p>"
            f"  <p>We are delighted to extend to you this formal offer of employment for the position of <strong>{job_title}</strong> at TechCorp Solutions.</p>"
            f"  <p>Your official **Offer Letter**, **Salary Annexure Table**, and complete **Company Terms & Policies** are attached directly to this email as a PDF document.</p>"
            f"  <div style='background-color: #f1f0ff; border-left: 4px solid #6c63ff; padding: 16px; margin: 24px 0; border-radius: 8px; font-size: 14px;'>"
            f"    <p style='margin: 0 0 6px;'><strong>Proposed Position:</strong> {job_title}</p>"
            f"    <p style='margin: 0 0 6px;'><strong>Total Annual Compensation:</strong> ₹{req.ctc:,.2f} per annum</p>"
            f"    <p style='margin: 0;'><strong>Attachment:</strong> Offer_Letter_{candidate.full_name.replace(' ', '_')}.pdf</p>"
            f"  </div>"
            f"  <p>Please download and review the attached PDF carefully. To formally accept the offer, kindly sign the document and reply back before the validity date (<strong>{valid_fmt}</strong>) to lock in your onboarding slot.</p>"
            f"  <p>We look forward to welcoming you to the TechCorp family!</p>"
            f"  <hr style='border: none; border-top: 1px solid #eee; margin: 24px 0;' />"
            f"  <p style='font-size: 12px; color: #888; text-align: center;'>TechCorp Global Talent Acquisition Operations Team</p>"
            f"</div>"
        )
        
        pdf_name = f"Offer_Letter_{candidate.full_name.replace(' ', '_')}.pdf"
        send_email_with_attachment(candidate.email, subject, html_content, text_content, pdf_bytes, pdf_name)
    except Exception as e:
        print("Failed to generate and dispatch offer letter PDF email:", e)
        
    return {"success": True, "message": "Offer letter, Annexure and Policies PDF successfully sent to candidate"}


@router.delete("/applications/{app_id}")
def delete_application(app_id: int, db: Session = Depends(get_db)):
    from app.models.candidate import Application
    application = db.query(Application).filter(Application.id == app_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    db.delete(application)
    db.commit()
    return {"success": True, "message": "Application successfully removed from pipeline"}
    

