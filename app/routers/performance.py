"""Performance router — goals, reviews, ratings."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.performance import PerformanceReview, Goal, ReviewStatus, GoalStatus
from app.models.employee import Employee
from app.models.user import User, UserRole
from app.schemas.schemas import (
    PerformanceReviewCreate, PerformanceReviewUpdate, PerformanceReviewResponse,
    GoalCreate, GoalResponse
)
from app.services.auth_service import get_current_user, get_current_employee, require_roles

router = APIRouter(prefix="/api/performance", tags=["Performance"])


# ===== REVIEWS =====
@router.get("/reviews", response_model=list[PerformanceReviewResponse])
def list_reviews(
    employee_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    # Enforce data isolation
    if current_user.role.value in ["employee", "manager"]:
        employee_id = current_employee.id

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
def create_review(
    request: PerformanceReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "hr")) # Secure review creation
):
    review = PerformanceReview(**request.model_dump())
    db.add(review)
    db.commit()
    db.refresh(review)
    
    emp = db.query(Employee).filter(Employee.id == review.employee_id).first()
    resp = PerformanceReviewResponse.model_validate(review)
    resp.employee_name = emp.full_name if emp else ""
    return resp


@router.put("/reviews/{review_id}", response_model=PerformanceReviewResponse)
def update_review(
    review_id: int,
    request: PerformanceReviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    review = db.query(PerformanceReview).filter(PerformanceReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
        
    # Enforce data isolation: standard employees/managers cannot update others' reviews
    if current_user.role.value in ["employee", "manager"]:
        if review.employee_id != current_employee.id:
            raise HTTPException(status_code=403, detail="Forbidden: You cannot update other employees' reviews")
    
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "status":
            value = ReviewStatus(value)
        setattr(review, key, value)
    
    # Calculate overall rating
    ratings = [review.technical_rating, review.communication_rating, review.relationship_rating if hasattr(review, 'relationship_rating') else review.leadership_rating,
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
def list_goals(
    employee_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    # Enforce data isolation
    if current_user.role.value in ["employee", "manager"]:
        employee_id = current_employee.id

    query = db.query(Goal)
    if employee_id:
        query = query.filter(Goal.employee_id == employee_id)
    return [GoalResponse.model_validate(g) for g in query.order_by(Goal.created_at.desc()).all()]


@router.post("/goals", response_model=GoalResponse)
def create_goal(
    request: GoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    target_emp_id = request.employee_id
    # Enforce data isolation
    if current_user.role.value in ["employee", "manager"]:
        target_emp_id = current_employee.id
        
    goal_data = request.model_dump()
    goal_data["employee_id"] = target_emp_id

    goal = Goal(**goal_data)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return GoalResponse.model_validate(goal)


@router.put("/goals/{goal_id}")
def update_goal(
    goal_id: int,
    status: Optional[str] = None,
    progress: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
        
    # Enforce data isolation
    if current_user.role.value in ["employee", "manager"]:
        if goal.employee_id != current_employee.id:
            raise HTTPException(status_code=403, detail="Forbidden: You cannot modify other employees' goals")

    if status:
        goal.status = GoalStatus(status)
    if progress is not None:
        goal.progress = progress
    db.commit()
    db.refresh(goal)
    return GoalResponse.model_validate(goal)


# ===== 360° FEEDBACK =====
from pydantic import BaseModel as PydanticBase
import json

class PeerFeedbackRequest(PydanticBase):
    review_id: int
    reviewer_name: str
    feedback: str
    rating: float  # 1-5

class SelfReviewRequest(PydanticBase):
    review_id: int
    self_review: str


@router.post("/reviews/{review_id}/peer-feedback")
def submit_peer_feedback(
    review_id: int,
    request: PeerFeedbackRequest,
    db: Session = Depends(get_db)
):
    """Submit peer feedback for a 360° review."""
    review = db.query(PerformanceReview).filter(PerformanceReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    existing = json.loads(review.peer_feedback or "[]")
    existing.append({
        "reviewer": request.reviewer_name,
        "feedback": request.feedback,
        "rating": request.rating,
    })
    review.peer_feedback = json.dumps(existing)
    review.peer_rating = round(sum(p["rating"] for p in existing) / len(existing), 1)
    db.commit()
    return {"message": "Peer feedback submitted", "peer_rating": review.peer_rating, "total_peers": len(existing)}


@router.post("/reviews/{review_id}/self-review")
def submit_self_review(
    review_id: int,
    request: SelfReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    """Employee submits their self-assessment."""
    review = db.query(PerformanceReview).filter(PerformanceReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
        
    # Enforce data isolation
    if current_user.role.value in ["employee", "manager"]:
        if review.employee_id != current_employee.id:
            raise HTTPException(status_code=403, detail="Forbidden: You cannot submit self-reviews for other employees")

    review.self_review = request.self_review
    review.status = ReviewStatus.MANAGER_REVIEW
    db.commit()
    return {"message": "Self review submitted", "status": review.status.value}


@router.get("/reviews/{review_id}/360-summary")
def get_360_summary(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    """Get full 360° feedback summary for a review."""
    review = db.query(PerformanceReview).filter(PerformanceReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Enforce data isolation: standard users can only view their own 360 summaries
    if current_user.role.value in ["employee", "manager"]:
        if review.employee_id != current_employee.id:
            raise HTTPException(status_code=403, detail="Forbidden: You cannot view other employees' 360 summaries")

    emp = db.query(Employee).filter(Employee.id == review.employee_id).first()
    peer_list = json.loads(review.peer_feedback or "[]")

    return {
        "review_id": review_id,
        "employee_name": emp.full_name if emp else "",
        "self_review": review.self_review,
        "manager_review": review.manager_review,
        "peer_feedback": peer_list,
        "peer_rating": review.peer_rating,
        "overall_rating": review.overall_rating,
        "ratings": {
            "technical": review.technical_rating,
            "communication": review.communication_rating,
            "leadership": review.leadership_rating,
            "teamwork": review.teamwork_rating,
            "innovation": review.innovation_rating,
            "peer_avg": review.peer_rating,
        },
        "recommendation": review.recommendation,
        "status": review.status.value,
    }
