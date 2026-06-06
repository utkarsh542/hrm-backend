from app.utils.timezone import get_ist_time
from app.logger import logger
"""Interviews router — scheduling, AI interviews, scorecards."""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from app.database import get_db
from app.models.interview import Interview, InterviewType, InterviewStatus
from app.models.candidate import Candidate, Application, ApplicationStatus
from app.models.job import Job
from app.schemas.schemas import InterviewCreate, InterviewUpdate, InterviewResponse
from app.services.ai_service import generate_interview_questions, evaluate_interview, _chat, _AI_ENABLED

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
    interview.meeting_link = f"https://meet.hrms.com/interview-{interview.id or 'new'}-{get_ist_time().strftime('%Y%m%d%H%M')}"
    
    db.add(interview)
    db.commit()
    db.refresh(interview)
    
    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    job = db.query(Job).filter(Job.id == interview.job_id).first()
    
    # Dispatch email invitation to candidate
    if candidate:
        try:
            from app.services.email_service import send_interview_invitation_email
            date_str = interview.scheduled_at.strftime("%d %b %Y, %I:%M %p") if hasattr(interview.scheduled_at, "strftime") else str(interview.scheduled_at)
            send_interview_invitation_email(
                to_email=candidate.email,
                candidate_name=candidate.full_name,
                job_title=job.title if job else "Software Position",
                round_number=interview.round_number,
                interview_type=interview.interview_type.value if hasattr(interview.interview_type, "value") else str(interview.interview_type),
                scheduled_at=date_str,
                interviewer_name=interview.interviewer_name,
                meeting_link=interview.meeting_link
            )
        except Exception as e:
            logger.error("Failed to send candidate email: %s", e)
            
    resp = InterviewResponse.model_validate(interview)
    resp.candidate_name = candidate.full_name if candidate else ""
    resp.job_title = job.title if job else ""
    return resp


@router.put("/{interview_id}", response_model=InterviewResponse)
def update_interview(interview_id: int, request: InterviewUpdate, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
        
    # Store old properties to check for rescheduling
    old_time = interview.scheduled_at
    old_interviewer = interview.interviewer_name
    old_status = interview.status
    
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
    
    # If scheduled/rescheduled date or interviewer has changed, send rescheduling email update
    if candidate and (old_time != interview.scheduled_at or old_interviewer != interview.interviewer_name or old_status != interview.status):
        if interview.status == InterviewStatus.SCHEDULED:
            try:
                from app.services.email_service import send_interview_invitation_email
                date_str = interview.scheduled_at.strftime("%d %b %Y, %I:%M %p") if hasattr(interview.scheduled_at, "strftime") else str(interview.scheduled_at)
                send_interview_invitation_email(
                    to_email=candidate.email,
                    candidate_name=candidate.full_name,
                    job_title=job.title if job else "Software Position",
                    round_number=interview.round_number,
                    interview_type=interview.interview_type.value if hasattr(interview.interview_type, "value") else str(interview.interview_type),
                    scheduled_at=date_str,
                    interviewer_name=interview.interviewer_name,
                    meeting_link=interview.meeting_link,
                    is_update=True
                )
            except Exception as e:
                logger.error("Failed to send rescheduled email: %s", e)
                
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


# ─── Live AI Interview Session ──────────────────────────────────────────────

class StartSessionRequest(BaseModel):
    interview_type: str = "technical"

class AnswerRequest(BaseModel):
    interview_id: int
    question_index: int
    question: str
    answer: str
    job_title: str = ""

class FinalEvalRequest(BaseModel):
    interview_id: int
    qa_pairs: list  # [{question, answer}, ...]
    job_title: str = ""


@router.post("/{interview_id}/start-session")
def start_live_session(interview_id: int, db: Session = Depends(get_db)):
    """Start a live AI interview session — generate questions and mark in_progress."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    job = db.query(Job).filter(Job.id == interview.job_id).first()
    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()

    job_title = job.title if job else "Software Engineer"
    skills = job.skills if job else ""

    questions = generate_interview_questions(job_title, interview.interview_type.value, skills)

    interview.ai_questions = json.dumps(questions)
    interview.status = InterviewStatus.IN_PROGRESS
    db.commit()

    return {
        "interview_id": interview_id,
        "candidate_name": candidate.full_name if candidate else "",
        "job_title": job_title,
        "interview_type": interview.interview_type.value,
        "round_number": interview.round_number,
        "questions": questions,
        "total_questions": len(questions),
    }


@router.post("/evaluate-answer")
def evaluate_single_answer(req: AnswerRequest):
    """Evaluate a single answer in real-time and return instant feedback."""
    if not req.answer.strip():
        return {"score": 2.0, "feedback": "No answer provided.", "follow_up": None}

    if _AI_ENABLED:
        result = _chat(
            f"""You are conducting a {req.job_title} interview.

Question: {req.question}
Candidate's Answer: {req.answer}

Evaluate this answer and return JSON:
{{
  "score": <1.0-5.0>,
  "feedback": "<1-2 sentence specific feedback on this answer>",
  "follow_up": "<optional follow-up question if answer needs clarification, or null>",
  "keywords_detected": ["<key concepts mentioned>"]
}}""",
            system="You are an expert technical interviewer. Be concise and specific."
        )
        if result and "score" in result:
            return {
                "score": max(1.0, min(5.0, float(result.get("score", 3.0)))),
                "feedback": result.get("feedback", ""),
                "follow_up": result.get("follow_up"),
                "keywords_detected": result.get("keywords_detected", []),
            }

    # Fallback: length-based heuristic
    words = len(req.answer.split())
    score = 4.0 if words > 50 else 3.0 if words > 20 else 2.0
    return {"score": score, "feedback": "Answer recorded.", "follow_up": None, "keywords_detected": []}


@router.post("/final-evaluation")
def final_evaluation(req: FinalEvalRequest, db: Session = Depends(get_db)):
    """Run final AI evaluation after all questions answered."""
    interview = db.query(Interview).filter(Interview.id == req.interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    questions = [p["question"] for p in req.qa_pairs]
    responses = [p["answer"] for p in req.qa_pairs]
    q_dicts = [{"question": q, "category": "mixed"} for q in questions]

    evaluation = evaluate_interview(responses, q_dicts)

    # Persist to DB
    interview.ai_responses = json.dumps(req.qa_pairs)
    interview.ai_score = evaluation["overall_score"]
    interview.ai_feedback = evaluation["feedback"]
    interview.status = InterviewStatus.COMPLETED
    interview.technical_score = evaluation["scores"].get("technical_knowledge")
    interview.communication_score = evaluation["scores"].get("communication")
    interview.cultural_fit_score = evaluation["scores"].get("cultural_fit")
    interview.overall_score = evaluation["overall_score"]
    interview.recommendation = evaluation["recommendation"]
    db.commit()

    return {
        "interview_id": req.interview_id,
        "evaluation": evaluation,
        "recommendation": evaluation["recommendation"],
        "overall_score": evaluation["overall_score"],
    }
