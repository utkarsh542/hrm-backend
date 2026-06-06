"""Expense Management router."""
import os
from app.utils.timezone import get_ist_time
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.expense import Expense, ExpenseCategory, ExpenseStatus
from app.models.employee import Employee
from app.models.user import User, UserRole
from app.config import settings
from app.services.auth_service import get_current_user, get_current_employee, require_roles

router = APIRouter(prefix="/api/expenses", tags=["Expenses"])

RECEIPTS_DIR = os.path.join(settings.UPLOAD_DIR, "receipts")
os.makedirs(RECEIPTS_DIR, exist_ok=True)

CATEGORY_LABELS = {
    "travel": "Travel", "food": "Food & Meals", "accommodation": "Accommodation",
    "equipment": "Equipment", "training": "Training", "medical": "Medical",
    "internet": "Internet", "mobile": "Mobile", "other": "Other",
}
CATEGORY_ICONS = {
    "travel": "✈️", "food": "🍽️", "accommodation": "🏨",
    "equipment": "💻", "training": "📚", "medical": "🏥",
    "internet": "🌐", "mobile": "📱", "other": "📦",
}


def _fmt(exp: Expense, db: Session) -> dict:
    emp = db.query(Employee).filter(Employee.id == exp.employee_id).first()
    approver = db.query(Employee).filter(Employee.id == exp.approved_by).first() if exp.approved_by else None
    return {
        "id": exp.id,
        "employee_id": exp.employee_id,
        "employee_name": emp.full_name if emp else "",
        "employee_code": emp.employee_id if emp else "",
        "title": exp.title,
        "description": exp.description,
        "category": exp.category.value,
        "category_label": CATEGORY_LABELS.get(exp.category.value, "Other"),
        "category_icon": CATEGORY_ICONS.get(exp.category.value, "📦"),
        "amount": exp.amount,
        "currency": exp.currency,
        "expense_date": str(exp.expense_date),
        "status": exp.status.value,
        "receipt_name": exp.receipt_name,
        "has_receipt": bool(exp.receipt_path),
        "approved_by_name": approver.full_name if approver else None,
        "approved_at": exp.approved_at.isoformat() if exp.approved_at else None,
        "rejection_reason": exp.rejection_reason,
        "notes": exp.notes,
        "created_at": exp.created_at.isoformat(),
    }


class ExpenseCreate(BaseModel):
    employee_id: int
    title: str
    category: str = "other"
    amount: float
    expense_date: date
    description: Optional[str] = None
    notes: Optional[str] = None


class ExpenseAction(BaseModel):
    action: str          # approve | reject | pay
    rejection_reason: Optional[str] = None
    approved_by: Optional[int] = None


@router.get("/")
def list_expenses(
    employee_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    # Enforce data isolation
    if current_user.role.value in ["employee", "manager"]:
        employee_id = current_employee.id

    query = db.query(Expense)
    if employee_id:
        query = query.filter(Expense.employee_id == employee_id)
    if status:
        query = query.filter(Expense.status == ExpenseStatus(status))
    return [_fmt(e, db) for e in query.order_by(Expense.created_at.desc()).all()]


@router.post("/")
def create_expense(
    req: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    target_emp_id = req.employee_id
    # Enforce data isolation
    if current_user.role.value in ["employee", "manager"]:
        target_emp_id = current_employee.id

    emp = db.query(Employee).filter(Employee.id == target_emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    expense_data = req.model_dump()
    expense_data["employee_id"] = target_emp_id

    exp = Expense(**expense_data)
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return _fmt(exp, db)


@router.post("/{expense_id}/receipt")
async def upload_receipt(
    expense_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    exp = db.query(Expense).filter(Expense.id == expense_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Expense not found")
        
    # Enforce data isolation
    if current_user.role.value in ["employee", "manager"]:
        if exp.employee_id != current_employee.id:
            raise HTTPException(status_code=403, detail="Forbidden: You cannot upload receipts for other employees")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Receipt too large. Max 5MB.")
    ts = get_ist_time().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RECEIPTS_DIR, f"{ts}_{file.filename.replace(' ', '_')}")
    with open(path, "wb") as f:
        f.write(content)
    exp.receipt_path = path
    exp.receipt_name = file.filename
    db.commit()
    return {"message": "Receipt uploaded", "receipt_name": file.filename}


@router.put("/{expense_id}/action")
def action_expense(
    expense_id: int,
    req: ExpenseAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "hr")) # Guarded approval flow
):
    exp = db.query(Expense).filter(Expense.id == expense_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Expense not found")
    if req.action == "approve":
        exp.status = ExpenseStatus.APPROVED
        exp.approved_by = req.approved_by
        exp.approved_at = get_ist_time()
    elif req.action == "reject":
        exp.status = ExpenseStatus.REJECTED
        exp.rejection_reason = req.rejection_reason
    elif req.action == "pay":
        exp.status = ExpenseStatus.PAID
        exp.paid_at = get_ist_time()
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    db.commit()
    db.refresh(exp)
    return _fmt(exp, db)


@router.get("/stats/summary")
def expense_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    query = db.query(Expense)
    # Enforce data isolation for stats
    if current_user.role.value in ["employee", "manager"]:
        query = query.filter(Expense.employee_id == current_employee.id)

    all_exp = query.all()
    pending_amt = sum(e.amount for e in all_exp if e.status == ExpenseStatus.SUBMITTED)
    approved_amt = sum(e.amount for e in all_exp if e.status == ExpenseStatus.APPROVED)
    paid_amt = sum(e.amount for e in all_exp if e.status == ExpenseStatus.PAID)
    by_cat: dict = {}
    for e in all_exp:
        k = e.category.value
        by_cat[k] = by_cat.get(k, 0) + e.amount
    return {
        "total": len(all_exp),
        "pending": len([e for e in all_exp if e.status == ExpenseStatus.SUBMITTED]),
        "approved": len([e for e in all_exp if e.status == ExpenseStatus.APPROVED]),
        "paid": len([e for e in all_exp if e.status == ExpenseStatus.PAID]),
        "pending_amount": round(pending_amt, 2),
        "approved_amount": round(approved_amt, 2),
        "paid_amount": round(paid_amt, 2),
        "by_category": {k: {"label": CATEGORY_LABELS.get(k, k), "icon": CATEGORY_ICONS.get(k, "📦"), "amount": round(v, 2)} for k, v in by_cat.items()},
    }
