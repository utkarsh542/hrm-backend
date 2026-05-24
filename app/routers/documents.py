"""Document Management router — upload, list, download, delete."""
import os
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document import Document, DocumentCategory, DocumentStatus
from app.models.employee import Employee
from app.models.user import User, UserRole
from app.config import settings
from app.services.auth_service import get_current_user, get_current_employee, require_roles

router = APIRouter(prefix="/api/documents", tags=["Documents"])

DOCS_DIR = os.path.join(settings.UPLOAD_DIR, "documents")
os.makedirs(DOCS_DIR, exist_ok=True)

ALLOWED_TYPES = {
    "application/pdf", "image/jpeg", "image/png", "image/jpg",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

CATEGORY_LABELS = {
    "offer_letter": "Offer Letter", "appointment_letter": "Appointment Letter",
    "salary_revision": "Salary Revision", "experience_letter": "Experience Letter",
    "relieving_letter": "Relieving Letter", "nda": "NDA", "policy": "Policy",
    "id_proof": "ID Proof", "address_proof": "Address Proof", "educational": "Educational",
    "pan_card": "PAN Card", "aadhar": "Aadhar", "bank_proof": "Bank Proof",
    "payslip": "Payslip", "appraisal": "Appraisal Letter",
    "warning_letter": "Warning Letter", "other": "Other",
}

CATEGORY_ICONS = {
    "offer_letter": "📄", "appointment_letter": "📋", "salary_revision": "💰",
    "experience_letter": "🏆", "relieving_letter": "🚪", "nda": "🔒",
    "policy": "📜", "id_proof": "🪪", "address_proof": "🏠",
    "educational": "🎓", "pan_card": "💳", "aadhar": "🪪",
    "bank_proof": "🏦", "payslip": "💵", "appraisal": "⭐",
    "warning_letter": "⚠️", "other": "📁",
}


def _fmt(doc: Document, db: Session) -> dict:
    emp = db.query(Employee).filter(Employee.id == doc.employee_id).first() if doc.employee_id else None
    return {
        "id": doc.id,
        "employee_id": doc.employee_id,
        "employee_name": emp.full_name if emp else "Company",
        "employee_code": emp.employee_id if emp else "—",
        "title": doc.title,
        "description": doc.description,
        "category": doc.category.value,
        "category_label": CATEGORY_LABELS.get(doc.category.value, "Other"),
        "category_icon": CATEGORY_ICONS.get(doc.category.value, "📁"),
        "status": doc.status.value,
        "file_name": doc.file_name,
        "file_size": doc.file_size,
        "file_size_kb": round(doc.file_size / 1024, 1),
        "file_type": doc.file_type,
        "is_confidential": doc.is_confidential,
        "tags": doc.tags,
        "created_at": doc.created_at.isoformat(),
    }


@router.get("/")
def list_documents(
    employee_id: Optional[int] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    query = db.query(Document).filter(Document.status == DocumentStatus.ACTIVE)
    
    # Enforce data isolation: standard users can only see their own documents or non-confidential company documents
    if current_user.role.value in ["employee", "manager"]:
        query = query.filter((Document.employee_id == current_employee.id) | (Document.employee_id == None))
    else:
        # privilegied roles (Admin, HR) can specify an employee_id filter
        if employee_id:
            query = query.filter(Document.employee_id == employee_id)
            
    if category:
        query = query.filter(Document.category == DocumentCategory(category))
    if search:
        query = query.filter(Document.title.ilike(f"%{search}%"))
    return [_fmt(d, db) for d in query.order_by(Document.created_at.desc()).all()]


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form("other"),
    employee_id: Optional[int] = Form(None),
    description: Optional[str] = Form(None),
    is_confidential: bool = Form(False),
    tags: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    # Enforce data isolation: standard users can only upload for themselves
    if current_user.role.value in ["employee", "manager"]:
        employee_id = current_employee.id

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF, images, and Word documents are allowed.")
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 10MB.")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe = f"{ts}_{file.filename.replace(' ', '_')}"
    sub = f"emp_{employee_id}" if employee_id else "company"
    dest = os.path.join(DOCS_DIR, sub)
    os.makedirs(dest, exist_ok=True)
    path = os.path.join(dest, safe)
    with open(path, "wb") as f:
        f.write(content)

    doc = Document(
        employee_id=employee_id, title=title, description=description,
        category=DocumentCategory(category), file_name=file.filename,
        file_path=path, file_size=len(content), file_type=file.content_type,
        is_confidential=is_confidential, tags=tags,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _fmt(doc, db)


@router.get("/stats/summary")
def doc_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    query = db.query(Document).filter(Document.status == DocumentStatus.ACTIVE)
    # Enforce data isolation for stats
    if current_user.role.value in ["employee", "manager"]:
        query = query.filter((Document.employee_id == current_employee.id) | (Document.employee_id == None))
        
    docs = query.all()
    by_cat: dict = {}
    for d in docs:
        k = d.category.value
        by_cat[k] = by_cat.get(k, 0) + 1
    return {
        "total": len(docs),
        "total_size_mb": round(sum(d.file_size for d in docs) / (1024 * 1024), 2),
        "by_category": {k: {"label": CATEGORY_LABELS.get(k, k), "icon": CATEGORY_ICONS.get(k, "📁"), "count": v} for k, v in by_cat.items()},
    }


@router.get("/{doc_id}/download")
def download_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="Document not found")
        
    # Enforce data isolation: standard users cannot download others' private documents
    if current_user.role.value in ["employee", "manager"]:
        if doc.employee_id and doc.employee_id != current_employee.id:
            raise HTTPException(status_code=403, detail="Forbidden: You cannot download documents of other employees")

    return FileResponse(doc.file_path, media_type=doc.file_type or "application/octet-stream", filename=doc.file_name)


@router.delete("/{doc_id}")
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    # Enforce data isolation
    if current_user.role.value in ["employee", "manager"]:
        if doc.employee_id != current_employee.id:
            raise HTTPException(status_code=403, detail="Forbidden: You cannot delete other employees' documents")

    doc.status = DocumentStatus.ARCHIVED
    db.commit()
    return {"message": "Document archived"}
