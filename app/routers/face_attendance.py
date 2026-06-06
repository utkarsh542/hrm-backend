"""Face Attendance router — browser webcam based face check-in."""
import base64
import random
from app.utils.timezone import get_ist_time, get_ist_date
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.face_attendance import FaceAttendance
from app.models.attendance import Attendance, AttendanceStatus
from app.models.employee import Employee

router = APIRouter(prefix="/api/face-attendance", tags=["Face Attendance"])


class FaceCheckInRequest(BaseModel):
    employee_id: int
    image_base64: str        # webcam snapshot base64
    location: Optional[str] = "office"
    device_info: Optional[str] = None


class FaceCheckOutRequest(BaseModel):
    employee_id: int
    image_base64: str


def _verify_face(image_base64: str, employee_id: int) -> dict:
    """
    Simulated face verification.
    In production: integrate DeepFace / AWS Rekognition / Azure Face API.
    Returns confidence score and match result.
    """
    if not image_base64 or len(image_base64) < 100:
        return {"verified": False, "confidence": 0.0, "reason": "Invalid image"}
    # Simulate: 90% success rate with high confidence
    confidence = round(random.uniform(0.82, 0.99), 3)
    verified = confidence >= 0.80
    return {
        "verified": verified,
        "confidence": confidence,
        "reason": "Face matched successfully" if verified else "Face confidence too low",
    }


def _fmt_record(rec: FaceAttendance, db: Session) -> dict:
    emp = db.query(Employee).filter(Employee.id == rec.employee_id).first()
    return {
        "id": rec.id,
        "employee_id": rec.employee_id,
        "employee_name": emp.full_name if emp else "",
        "employee_code": emp.employee_id if emp else "",
        "date": str(rec.date),
        "check_in": rec.check_in.isoformat() if rec.check_in else None,
        "check_out": rec.check_out.isoformat() if rec.check_out else None,
        "work_hours": rec.work_hours,
        "confidence": rec.confidence,
        "verified": rec.verified,
        "location": rec.location,
    }


@router.post("/check-in")
def face_check_in(req: FaceCheckInRequest, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == req.employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    today = get_ist_date()
    existing = db.query(FaceAttendance).filter(
        FaceAttendance.employee_id == req.employee_id,
        FaceAttendance.date == today,
    ).first()
    if existing and existing.check_in:
        raise HTTPException(status_code=400, detail="Already checked in today")

    result = _verify_face(req.image_base64, req.employee_id)
    if not result["verified"]:
        raise HTTPException(status_code=403, detail=f"Face verification failed: {result['reason']}")

    now = get_ist_time()
    if existing:
        existing.check_in = now
        existing.confidence = result["confidence"]
        existing.verified = True
        existing.location = req.location
        rec = existing
    else:
        rec = FaceAttendance(
            employee_id=req.employee_id, date=today,
            check_in=now, confidence=result["confidence"],
            verified=True, location=req.location,
            device_info=req.device_info,
        )
        db.add(rec)

    # Also update main attendance table
    att = db.query(Attendance).filter(
        Attendance.employee_id == req.employee_id,
        Attendance.date == today,
    ).first()
    if not att:
        att = Attendance(employee_id=req.employee_id, date=today, check_in=now, status=AttendanceStatus.PRESENT)
        db.add(att)
    else:
        att.check_in = now
        att.status = AttendanceStatus.PRESENT

    db.commit()
    db.refresh(rec)
    return {
        "message": f"✅ Face verified! Welcome, {emp.full_name}",
        "confidence": result["confidence"],
        "check_in_time": now.strftime("%H:%M:%S"),
        "record": _fmt_record(rec, db),
    }


@router.post("/check-out")
def face_check_out(req: FaceCheckOutRequest, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == req.employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    today = get_ist_date()
    rec = db.query(FaceAttendance).filter(
        FaceAttendance.employee_id == req.employee_id,
        FaceAttendance.date == today,
    ).first()
    if not rec or not rec.check_in:
        raise HTTPException(status_code=400, detail="Not checked in today")

    result = _verify_face(req.image_base64, req.employee_id)
    if not result["verified"]:
        raise HTTPException(status_code=403, detail=f"Face verification failed: {result['reason']}")

    now = get_ist_time()
    rec.check_out = now
    diff = now - rec.check_in
    rec.work_hours = round(diff.total_seconds() / 3600, 2)

    # Update main attendance
    att = db.query(Attendance).filter(
        Attendance.employee_id == req.employee_id,
        Attendance.date == today,
    ).first()
    if att:
        att.check_out = now
        att.work_hours = rec.work_hours

    db.commit()
    db.refresh(rec)
    return {
        "message": f"👋 Goodbye, {emp.full_name}! Work hours: {rec.work_hours}h",
        "work_hours": rec.work_hours,
        "check_out_time": now.strftime("%H:%M:%S"),
        "record": _fmt_record(rec, db),
    }


@router.get("/today")
def get_today_records(db: Session = Depends(get_db)):
    today = get_ist_date()
    records = db.query(FaceAttendance).filter(FaceAttendance.date == today).all()
    return [_fmt_record(r, db) for r in records]


@router.get("/employee/{employee_id}")
def get_employee_face_records(employee_id: int, db: Session = Depends(get_db)):
    records = db.query(FaceAttendance).filter(
        FaceAttendance.employee_id == employee_id
    ).order_by(FaceAttendance.date.desc()).limit(30).all()
    return [_fmt_record(r, db) for r in records]
