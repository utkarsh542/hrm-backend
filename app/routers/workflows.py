"""Approval workflows router."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.workflow import ApprovalRequest, ApprovalStatus

router = APIRouter(prefix="/api/workflows", tags=["Workflows"])


class ApprovalActionRequest(BaseModel):
    action: str
    comments: Optional[str] = None


@router.get("/pending")
def get_pending_approvals(approver_id: int = None, db: Session = Depends(get_db)):
    query = db.query(ApprovalRequest).filter(ApprovalRequest.status == ApprovalStatus.pending)
    if approver_id:
        query = query.filter(ApprovalRequest.approver_id == approver_id)
    approvals = query.order_by(ApprovalRequest.created_at.desc()).all()
    return [
        {"id": a.id, "entity_type": a.entity_type, "entity_id": a.entity_id,
         "title": a.title, "description": a.description, "requested_by": a.requested_by,
         "status": a.status.value if a.status else "pending",
         "created_at": a.created_at.isoformat() if a.created_at else None}
        for a in approvals
    ]


@router.get("/history")
def get_approval_history(limit: int = 50, db: Session = Depends(get_db)):
    approvals = db.query(ApprovalRequest).filter(
        ApprovalRequest.status != ApprovalStatus.pending
    ).order_by(ApprovalRequest.acted_at.desc()).limit(limit).all()
    return [
        {"id": a.id, "entity_type": a.entity_type, "entity_id": a.entity_id,
         "title": a.title, "status": a.status.value if a.status else "pending",
         "comments": a.comments,
         "acted_at": a.acted_at.isoformat() if a.acted_at else None,
         "created_at": a.created_at.isoformat() if a.created_at else None}
        for a in approvals
    ]


@router.post("/{request_id}/approve")
def approve_request(request_id: int, data: ApprovalActionRequest, db: Session = Depends(get_db)):
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")
    req.status = ApprovalStatus.approved if data.action == "approve" else ApprovalStatus.rejected
    req.comments = data.comments
    req.acted_at = datetime.utcnow()
    db.commit()
    return {"success": True, "status": req.status.value}
