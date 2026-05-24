"""Employee engagement router — surveys, mood tracking, burnout detection."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.engagement import PulseSurvey, SurveyResponse, MoodEntry, SurveyStatus
from app.models.employee import Employee
from app.services.ai_service import analyze_survey_sentiment, detect_burnout_risk

router = APIRouter(prefix="/api/engagement", tags=["Engagement"])


class SurveyCreate(BaseModel):
    title: str
    description: Optional[str] = None
    questions: list

class SurveyResponseCreate(BaseModel):
    survey_id: int
    employee_id: Optional[int] = None
    answers: dict

class MoodCreate(BaseModel):
    employee_id: int
    mood: int
    note: Optional[str] = None


@router.get("/surveys")
def list_surveys(status: str = None, db: Session = Depends(get_db)):
    query = db.query(PulseSurvey)
    if status:
        try:
            query = query.filter(PulseSurvey.status == SurveyStatus(status))
        except ValueError:
            pass
    surveys = query.order_by(PulseSurvey.created_at.desc()).all()
    return [
        {"id": s.id, "title": s.title, "description": s.description,
         "questions": s.questions or [], "status": s.status.value if s.status else "draft",
         "response_count": db.query(SurveyResponse).filter(SurveyResponse.survey_id == s.id).count(),
         "created_at": s.created_at.isoformat() if s.created_at else None}
        for s in surveys
    ]


@router.post("/surveys")
def create_survey(data: SurveyCreate, db: Session = Depends(get_db)):
    survey = PulseSurvey(title=data.title, description=data.description, questions=data.questions, status=SurveyStatus.active)
    db.add(survey)
    db.commit()
    db.refresh(survey)
    return {"id": survey.id, "message": "Survey created"}


@router.post("/surveys/{survey_id}/respond")
def submit_response(survey_id: int, data: SurveyResponseCreate, db: Session = Depends(get_db)):
    survey = db.query(PulseSurvey).filter(PulseSurvey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    text_answers = [str(v) for v in data.answers.values() if isinstance(v, str) and len(v) > 10]
    sentiment_score = None
    if text_answers:
        sentiment = analyze_survey_sentiment(text_answers)
        sentiment_score = sentiment.get("sentiment_score")
    response = SurveyResponse(survey_id=survey_id, employee_id=data.employee_id, answers=data.answers, sentiment_score=sentiment_score)
    db.add(response)
    db.commit()
    return {"success": True}


@router.get("/surveys/{survey_id}/results")
def get_survey_results(survey_id: int, db: Session = Depends(get_db)):
    survey = db.query(PulseSurvey).filter(PulseSurvey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    responses = db.query(SurveyResponse).filter(SurveyResponse.survey_id == survey_id).all()
    questions = survey.questions or []
    question_results = []
    for q in questions:
        qid = str(q.get("id", ""))
        answers = [r.answers.get(qid) for r in responses if r.answers and qid in r.answers]
        if q.get("type") == "rating":
            numeric = [a for a in answers if isinstance(a, (int, float))]
            avg = sum(numeric) / len(numeric) if numeric else 0
            question_results.append({"question": q.get("text", ""), "type": "rating", "avg_score": round(avg, 1), "response_count": len(numeric)})
        else:
            question_results.append({"question": q.get("text", ""), "type": q.get("type", "text"), "responses": [str(a) for a in answers[:20]], "response_count": len(answers)})
    sentiments = [r.sentiment_score for r in responses if r.sentiment_score is not None]
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.5
    return {"survey": {"id": survey.id, "title": survey.title}, "total_responses": len(responses), "avg_sentiment": round(avg_sentiment, 2), "question_results": question_results}


@router.post("/mood")
def submit_mood(data: MoodCreate, db: Session = Depends(get_db)):
    existing = db.query(MoodEntry).filter(MoodEntry.employee_id == data.employee_id, MoodEntry.date == date.today()).first()
    if existing:
        existing.mood = max(1, min(5, data.mood))
        existing.note = data.note
    else:
        entry = MoodEntry(employee_id=data.employee_id, mood=max(1, min(5, data.mood)), note=data.note)
        db.add(entry)
    db.commit()
    return {"success": True}


@router.get("/mood/trends")
def get_mood_trends(employee_id: int = None, days: int = 30, db: Session = Depends(get_db)):
    since = date.today() - timedelta(days=days)
    query = db.query(MoodEntry).filter(MoodEntry.date >= since)
    if employee_id:
        query = query.filter(MoodEntry.employee_id == employee_id)
    entries = query.order_by(MoodEntry.date).all()
    by_date = {}
    for e in entries:
        d = e.date.isoformat() if e.date else ""
        by_date.setdefault(d, []).append(e.mood)
    trends = [{"date": d, "avg_mood": round(sum(m) / len(m), 1), "count": len(m)} for d, m in by_date.items()]
    overall_avg = round(sum(e.mood for e in entries) / len(entries), 1) if entries else 3.0
    return {"trends": trends, "overall_avg": overall_avg, "total_entries": len(entries)}


@router.get("/burnout-risk")
def get_burnout_risk(db: Session = Depends(get_db)):
    from app.models.attendance import Attendance, LeaveRequest
    employees = db.query(Employee).filter(Employee.is_active == True).all()
    risks = []
    month_start = date.today().replace(day=1)
    for emp in employees:
        attendance = db.query(Attendance).filter(Attendance.employee_id == emp.id, Attendance.date >= month_start).all()
        overtime = sum(a.overtime_hours or 0 for a in attendance)
        leaves = db.query(LeaveRequest).filter(LeaveRequest.employee_id == emp.id, LeaveRequest.start_date >= month_start).count()
        moods = db.query(MoodEntry).filter(MoodEntry.employee_id == emp.id, MoodEntry.date >= month_start).all()
        mood_scores = [m.mood for m in moods]
        risk = detect_burnout_risk(emp.full_name, overtime, leaves, mood_scores)
        if risk["risk_score"] > 0:
            risks.append({"employee_id": emp.id, "employee_name": emp.full_name, "designation": emp.designation, **risk})
    risks.sort(key=lambda x: x["risk_score"], reverse=True)
    return risks


@router.get("/dashboard")
def engagement_dashboard(db: Session = Depends(get_db)):
    total_surveys = db.query(PulseSurvey).count()
    active_surveys = db.query(PulseSurvey).filter(PulseSurvey.status == SurveyStatus.active).count()
    total_responses = db.query(SurveyResponse).count()
    today_moods = db.query(MoodEntry).filter(MoodEntry.date == date.today()).all()
    avg_mood = round(sum(m.mood for m in today_moods) / len(today_moods), 1) if today_moods else 0
    return {"total_surveys": total_surveys, "active_surveys": active_surveys, "total_responses": total_responses, "today_mood_avg": avg_mood, "today_mood_count": len(today_moods)}
