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
    
    # ─── Entity Syncing ───
    if req.entity_type == "leave":
        from app.models.attendance import LeaveRequest, LeaveStatus, LeaveType
        from app.models.employee import Employee
        
        leave = db.query(LeaveRequest).filter(LeaveRequest.id == req.entity_id).first()
        if leave:
            status_str = "approved" if data.action == "approve" else "rejected"
            remarks = data.comments if status_str == "rejected" else "Leave request approved."
            
            if status_str == "approved":
                leave.status = LeaveStatus.APPROVED
                leave.approved_at = datetime.utcnow()
                
                # Deduct leave balance
                emp = db.query(Employee).filter(Employee.id == leave.employee_id).first()
                if emp:
                    if leave.leave_type == LeaveType.CASUAL:
                        emp.casual_leave_balance = max(0, emp.casual_leave_balance - leave.days)
                    elif leave.leave_type == LeaveType.SICK:
                        emp.sick_leave_balance = max(0, emp.sick_leave_balance - leave.days)
                    elif leave.leave_type == LeaveType.EARNED:
                        emp.earned_leave_balance = max(0, emp.earned_leave_balance - leave.days)
            else:
                leave.status = LeaveStatus.REJECTED
                leave.rejection_reason = data.comments

            db.commit()
            
            # Trigger notifications and email alerts
            try:
                from app.routers.notifications import create_notification
                from app.services.email_service import send_leave_status_update
                
                emp = db.query(Employee).filter(Employee.id == leave.employee_id).first()
                if emp:
                    # In-app notification
                    if emp.user_id:
                        create_notification(
                            db=db,
                            user_id=emp.user_id,
                            title=f"Leave Request {status_str.title()}",
                            message=f"Your {leave.leave_type.value} leave request for {leave.days} day(s) has been {status_str}. Remarks: \"{remarks}\"",
                            type="success" if status_str == "approved" else "warning",
                            link="/attendance/leaves"
                        )
                    # Email alert
                    send_leave_status_update(
                        to_email=emp.email,
                        employee_name=emp.full_name,
                        leave_type=leave.leave_type.value,
                        status=status_str,
                        comments=remarks
                    )
            except Exception as e:
                import logging
                logger = logging.getLogger("uvicorn")
                logger.error(f"Error in leave approval sync alerts: {e}")
                
    elif req.entity_type == "resignation":
        from app.models.offboarding import Resignation, ResignationStatus
        resignation = db.query(Resignation).filter(Resignation.id == req.entity_id).first()
        if resignation:
            resignation.status = ResignationStatus.APPROVED if data.action == "approve" else ResignationStatus.REJECTED
            db.commit()
            
    return {"success": True, "status": req.status.value}
