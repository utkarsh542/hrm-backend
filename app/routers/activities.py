"""Planned Activities router — events, trainings, and team building."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.activity import Activity, ActivityCategory
from app.models.user import User
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/activities", tags=["Activities"])


class ActivityCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: str
    scheduled_at: datetime
    location: Optional[str] = None


@router.get("/")
def list_activities(category: Optional[str] = None, db: Session = Depends(get_db)):
    """List all planned activities chronologically. Supports optional category filtering."""
    query = db.query(Activity)
    if category:
        try:
            cat_enum = ActivityCategory(category)
            query = query.filter(Activity.category == cat_enum)
        except ValueError:
            pass
    return query.order_by(Activity.scheduled_at.asc()).all()


@router.post("/")
def create_activity(
    data: ActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Plan a new corporate activity. Restricted to Admins, HR Managers, and Team Managers."""
    # Restrict activity planning to admins, HR, and managers
    if current_user.role.value not in ["admin", "hr", "manager"]:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Only Admins, HR, or Managers can plan activities."
        )
        
    try:
        cat_enum = ActivityCategory(data.category)
    except ValueError:
        cat_enum = ActivityCategory.event
        
    activity = Activity(
        title=data.title,
        description=data.description,
        category=cat_enum,
        scheduled_at=data.scheduled_at,
        location=data.location,
        organizer_id=current_user.id
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


@router.delete("/{activity_id}")
def delete_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancel / delete a planned corporate activity. Restricted to Admins, HR, and Managers."""
    if current_user.role.value not in ["admin", "hr", "manager"]:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Only Admins, HR, or Managers can cancel activities."
        )
        
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
        
    db.delete(activity)
    db.commit()
    return {"success": True}
