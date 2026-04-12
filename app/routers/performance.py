"""Performance router — goals, reviews, ratings."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.performance import PerformanceReview, Goal, ReviewStatus, GoalStatus
from app.models.employee import Employee
from app.schemas.schemas import (
    PerformanceReviewCreate, PerformanceReviewUpdate, PerformanceReviewResponse,
    GoalCreate, GoalResponse
)

router = APIRouter(prefix="/api/performance", tags=["Performance"])


# ===== REVIEWS =====
@router.get("/reviews", response_model=list[PerformanceReviewResponse])
def list_reviews(employee_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(PerformanceReview)
    if employee_id:
        query = query.filter(PerformanceReview.employee_id == employee_id)
    
    reviews = query.order_by(PerformanceReview.created_at.desc()).all()
    result = []
    for r in reviews:
        emp = db.query(Employee).filter(Employee.id == r.employee_id).first()
        resp = PerformanceReviewResponse.model_validate(r)
        resp.employee_name = emp.full_name if emp else ""
        result.append(resp)
    return result


@router.post("/reviews", response_model=PerformanceReviewResponse)
def create_review(request: PerformanceReviewCreate, db: Session = Depends(get_db)):
    review = PerformanceReview(**request.model_dump())
    db.add(review)
    db.commit()
    db.refresh(review)
    
    emp = db.query(Employee).filter(Employee.id == review.employee_id).first()
    resp = PerformanceReviewResponse.model_validate(review)
    resp.employee_name = emp.full_name if emp else ""
    return resp


@router.put("/reviews/{review_id}", response_model=PerformanceReviewResponse)
def update_review(review_id: int, request: PerformanceReviewUpdate, db: Session = Depends(get_db)):
    review = db.query(PerformanceReview).filter(PerformanceReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "status":
            value = ReviewStatus(value)
        setattr(review, key, value)
    
    # Calculate overall rating
    ratings = [review.technical_rating, review.communication_rating, review.leadership_rating,
               review.teamwork_rating, review.innovation_rating]
    valid = [r for r in ratings if r is not None]
    if valid:
        review.overall_rating = round(sum(valid) / len(valid), 1)
    
    db.commit()
    db.refresh(review)
    
    emp = db.query(Employee).filter(Employee.id == review.employee_id).first()
    resp = PerformanceReviewResponse.model_validate(review)
    resp.employee_name = emp.full_name if emp else ""
    return resp


# ===== GOALS =====
@router.get("/goals", response_model=list[GoalResponse])
def list_goals(employee_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Goal)
    if employee_id:
        query = query.filter(Goal.employee_id == employee_id)
    return [GoalResponse.model_validate(g) for g in query.order_by(Goal.created_at.desc()).all()]


@router.post("/goals", response_model=GoalResponse)
def create_goal(request: GoalCreate, db: Session = Depends(get_db)):
    goal = Goal(**request.model_dump())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return GoalResponse.model_validate(goal)


@router.put("/goals/{goal_id}")
def update_goal(goal_id: int, status: Optional[str] = None, progress: Optional[int] = None, db: Session = Depends(get_db)):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    if status:
        goal.status = GoalStatus(status)
    if progress is not None:
        goal.progress = progress
    db.commit()
    db.refresh(goal)
    return GoalResponse.model_validate(goal)
