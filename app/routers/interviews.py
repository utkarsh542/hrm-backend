"""Interviews router — scheduling, AI interviews, scorecards."""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.interview import Interview, InterviewType, InterviewStatus
from app.models.candidate import Candidate, Application, ApplicationStatus
from app.models.job import Job
from app.schemas.schemas import InterviewCreate, InterviewUpdate, InterviewResponse
from app.services.ai_service import generate_interview_questions, evaluate_interview

router = APIRouter(prefix="/api/interviews", tags=["Interviews"])


@router.get("/", response_model=list[InterviewResponse])
def list_interviews(
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Interview)
    if status:
        query = query.filter(Interview.status == InterviewStatus(status))
    
    interviews = query.order_by(Interview.scheduled_at.desc()).all()
    result = []
    for i in interviews:
        candidate = db.query(Candidate).filter(Candidate.id == i.candidate_id).first()
        job = db.query(Job).filter(Job.id == i.job_id).first()
        resp = InterviewResponse.model_validate(i)
        resp.candidate_name = candidate.full_name if candidate else ""
        resp.job_title = job.title if job else ""
        result.append(resp)
    return result


@router.post("/", response_model=InterviewResponse)
def schedule_interview(request: InterviewCreate, db: Session = Depends(get_db)):
    # Update application status
    application = db.query(Application).filter(Application.id == request.application_id).first()
    if application:
        application.status = ApplicationStatus.INTERVIEW
    
    interview = Interview(**request.model_dump())
    
    # Generate meeting link
    interview.meeting_link = f"https://meet.hrms.com/interview-{interview.id or 'new'}-{datetime.utcnow().strftime('%Y%m%d%H%M')}"
    
    db.add(interview)
    db.commit()
    db.refresh(interview)
    
    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    job = db.query(Job).filter(Job.id == interview.job_id).first()
    resp = InterviewResponse.model_validate(interview)
    resp.candidate_name = candidate.full_name if candidate else ""
    resp.job_title = job.title if job else ""
    return resp


@router.put("/{interview_id}", response_model=InterviewResponse)
def update_interview(interview_id: int, request: InterviewUpdate, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "status":
            value = InterviewStatus(value)
        setattr(interview, key, value)
    
    # Calculate overall score if individual scores provided
    scores = [interview.technical_score, interview.communication_score, interview.cultural_fit_score]
    valid_scores = [s for s in scores if s is not None]
    if valid_scores:
        interview.overall_score = round(sum(valid_scores) / len(valid_scores), 1)
    
    db.commit()
    db.refresh(interview)
    
    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    job = db.query(Job).filter(Job.id == interview.job_id).first()
    resp = InterviewResponse.model_validate(interview)
    resp.candidate_name = candidate.full_name if candidate else ""
    resp.job_title = job.title if job else ""
    return resp


@router.post("/{interview_id}/ai-interview")
def run_ai_interview(interview_id: int, db: Session = Depends(get_db)):
    """Run an AI-powered mock interview and get evaluation."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    job = db.query(Job).filter(Job.id == interview.job_id).first()
    job_title = job.title if job else "Software Engineer"
    skills = job.skills if job else ""
    
    # Generate questions
    questions = generate_interview_questions(job_title, interview.interview_type.value, skills)
    interview.ai_questions = json.dumps(questions)
    
    # Simulate responses and evaluate
    mock_responses = [f"Sample response for question {i+1}" for i in range(len(questions))]
    evaluation = evaluate_interview(mock_responses, questions)
    
    interview.ai_responses = json.dumps(mock_responses)
    interview.ai_score = evaluation["overall_score"]
    interview.ai_feedback = evaluation["feedback"]
    interview.status = InterviewStatus.COMPLETED
    
    # Map AI scores to scorecard
    interview.technical_score = evaluation["scores"].get("technical_knowledge")
    interview.communication_score = evaluation["scores"].get("communication")
    interview.cultural_fit_score = evaluation["scores"].get("cultural_fit")
    interview.overall_score = evaluation["overall_score"]
    interview.recommendation = evaluation["recommendation"]
    
    db.commit()
    db.refresh(interview)
    
    return {
        "interview_id": interview.id,
        "questions": questions,
        "evaluation": evaluation,
        "status": "completed",
    }


@router.get("/{interview_id}/questions")
def get_interview_questions(interview_id: int, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    job = db.query(Job).filter(Job.id == interview.job_id).first()
    questions = generate_interview_questions(
        job.title if job else "Software Engineer",
        interview.interview_type.value,
        job.skills if job else ""
    )
    return {"questions": questions}
