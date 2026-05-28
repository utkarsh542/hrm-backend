"""Resume parsing and smart candidate creation."""
import os
import time
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.models.candidate import Candidate, Application, ApplicationStatus, ApplicationSource
from app.models.job import Job
from app.services.ai_service import parse_resume_text, screen_resume

router = APIRouter(prefix="/api/resume", tags=["Resume Intelligence"])


def extract_text_from_file(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        try:
            import fitz
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text.strip()
        except Exception as e:
            print(f"PDF extraction error: {e}")
            return ""
    elif ext == ".docx":
        try:
            from docx import Document
            doc = Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs]).strip()
        except Exception as e:
            print(f"DOCX extraction error: {e}")
            return ""
    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    return ""


@router.post("/parse")
async def parse_resume(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".docx", ".txt"]:
        raise HTTPException(status_code=400, detail="Unsupported format. Use PDF, DOCX, or TXT.")
    upload_dir = os.path.join(settings.UPLOAD_DIR, "resumes")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{int(time.time())}_{file.filename}"
    file_path = os.path.join(upload_dir, filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    text = extract_text_from_file(file_path)
    if not text:
        raise HTTPException(status_code=400, detail="Could not extract text from file.")
    parsed = parse_resume_text(text)
    parsed["resume_url"] = f"/uploads/resumes/{filename}"
    return parsed


@router.post("/parse-and-create")
async def parse_and_create_candidate(file: UploadFile = File(...), job_id: int = None, db: Session = Depends(get_db)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".docx", ".txt"]:
        raise HTTPException(status_code=400, detail="Unsupported format.")
    upload_dir = os.path.join(settings.UPLOAD_DIR, "resumes")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{int(time.time())}_{file.filename}"
    file_path = os.path.join(upload_dir, filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    text = extract_text_from_file(file_path)
    if not text:
        raise HTTPException(status_code=400, detail="Could not extract text from file.")
    parsed = parse_resume_text(text)
    email = parsed.get("email", "").strip()
    existing = db.query(Candidate).filter(Candidate.email == email).first() if email else None
    if existing:
        candidate = existing
    else:
        candidate = Candidate(
            full_name=parsed.get("full_name", "Unknown"),
            email=email or f"unknown_{int(time.time())}@parsed.com",
            phone=parsed.get("phone"), current_company=parsed.get("current_company"),
            current_designation=parsed.get("current_designation"),
            experience_years=parsed.get("experience_years", 0),
            skills=parsed.get("skills", ""), location=parsed.get("location"),
            expected_salary=parsed.get("expected_salary"),
            resume_url=f"/uploads/resumes/{filename}",
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
    application = None
    if job_id:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(
                status_code=400,
                detail=f"Job ID {job_id} does not exist. The candidate was successfully saved to your database, but the job application could not be created."
            )
        screening = screen_resume(candidate.skills or "", job.skills or "", candidate.experience_years or 0)
        application = Application(
            candidate_id=candidate.id, job_id=job_id, status=ApplicationStatus.APPLIED,
            source=ApplicationSource.WEBSITE, ai_score=screening["score"], ai_summary=screening["summary"],
        )
        db.add(application)
        db.commit()
        db.refresh(application)
    return {"candidate_id": candidate.id, "candidate_name": candidate.full_name,
            "parsed_data": parsed, "application_id": application.id if application else None,
            "is_existing": existing is not None}
