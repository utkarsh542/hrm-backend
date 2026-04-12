"""Payroll router — run payroll, generate payslips, download PDFs."""
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.payroll import PayrollRun, Payslip, PayrollStatus
from app.models.employee import Employee, Department, EmploymentStatus
from app.schemas.schemas import PayrollRunCreate, PayrollRunResponse, PayslipResponse
from app.services.payroll_service import process_payslip
from app.services.pdf_service import generate_payslip_pdf
from app.config import settings

router = APIRouter(prefix="/api/payroll", tags=["Payroll"])


@router.get("/runs", response_model=list[PayrollRunResponse])
def list_payroll_runs(db: Session = Depends(get_db)):
    runs = db.query(PayrollRun).order_by(PayrollRun.year.desc(), PayrollRun.month.desc()).all()
    result = []
    for run in runs:
        resp = PayrollRunResponse.model_validate(run)
        # Get payslips for this run
        payslips = db.query(Payslip).filter(Payslip.payroll_run_id == run.id).all()
        resp.payslips = []
        for ps in payslips:
            emp = db.query(Employee).filter(Employee.id == ps.employee_id).first()
            dept = db.query(Department).filter(Department.id == emp.department_id).first() if emp else None
            ps_resp = PayslipResponse.model_validate(ps)
            ps_resp.employee_name = emp.full_name if emp else ""
            ps_resp.employee_code = emp.employee_id if emp else ""
            ps_resp.department = dept.name if dept else ""
            ps_resp.designation = emp.designation if emp else ""
            resp.payslips.append(ps_resp)
        result.append(resp)
    return result


@router.post("/run", response_model=PayrollRunResponse)
def run_payroll(request: PayrollRunCreate, db: Session = Depends(get_db)):
    # Check if already processed for this month/year
    existing = db.query(PayrollRun).filter(
        PayrollRun.month == request.month,
        PayrollRun.year == request.year
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Payroll already processed for {request.month}/{request.year}")
    
    # Get all active employees
    employees = db.query(Employee).filter(Employee.employment_status == EmploymentStatus.ACTIVE).all()
    if not employees:
        raise HTTPException(status_code=400, detail="No active employees found")
    
    # Create payroll run
    payroll_run = PayrollRun(
        month=request.month,
        year=request.year,
        status=PayrollStatus.PROCESSING,
        total_employees=len(employees),
    )
    db.add(payroll_run)
    db.commit()
    db.refresh(payroll_run)
    
    total_gross = 0
    total_deductions = 0
    total_net = 0
    
    for emp in employees:
        # Assume 22 working days and calculate based on basic attendance
        working_days = 22
        present_days = 22  # Simplified for MVP
        
        payslip_data = process_payslip(emp, working_days, present_days)
        
        payslip = Payslip(
            payroll_run_id=payroll_run.id,
            employee_id=emp.id,
            month=request.month,
            year=request.year,
            **payslip_data,
            status="generated",
        )
        db.add(payslip)
        
        total_gross += payslip_data["total_earnings"]
        total_deductions += payslip_data["total_deductions"]
        total_net += payslip_data["net_salary"]
    
    payroll_run.total_gross = round(total_gross, 2)
    payroll_run.total_deductions = round(total_deductions, 2)
    payroll_run.total_net = round(total_net, 2)
    payroll_run.status = PayrollStatus.COMPLETED
    payroll_run.processed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(payroll_run)
    
    resp = PayrollRunResponse.model_validate(payroll_run)
    return resp


@router.get("/payslips/{employee_id}")
def get_employee_payslips(employee_id: int, db: Session = Depends(get_db)):
    payslips = db.query(Payslip).filter(Payslip.employee_id == employee_id).order_by(
        Payslip.year.desc(), Payslip.month.desc()
    ).all()
    
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    dept = db.query(Department).filter(Department.id == emp.department_id).first() if emp else None
    
    result = []
    for ps in payslips:
        resp = PayslipResponse.model_validate(ps)
        resp.employee_name = emp.full_name if emp else ""
        resp.employee_code = emp.employee_id if emp else ""
        resp.department = dept.name if dept else ""
        resp.designation = emp.designation if emp else ""
        result.append(resp)
    return result


@router.get("/payslips/{payslip_id}/download")
def download_payslip(payslip_id: int, db: Session = Depends(get_db)):
    payslip = db.query(Payslip).filter(Payslip.id == payslip_id).first()
    if not payslip:
        raise HTTPException(status_code=404, detail="Payslip not found")
    
    emp = db.query(Employee).filter(Employee.id == payslip.employee_id).first()
    dept = db.query(Department).filter(Department.id == emp.department_id).first() if emp else None
    
    output_path = os.path.join(settings.GENERATED_DIR, f"payslip_{emp.employee_id}_{payslip.month}_{payslip.year}.pdf")
    
    payslip_data = {
        "month": payslip.month,
        "year": payslip.year,
        "basic_salary": payslip.basic_salary,
        "hra": payslip.hra,
        "da": payslip.da,
        "special_allowance": payslip.special_allowance,
        "total_earnings": payslip.total_earnings,
        "pf_employee": payslip.pf_employee,
        "professional_tax": payslip.professional_tax,
        "tds": payslip.tds,
        "total_deductions": payslip.total_deductions,
        "net_salary": payslip.net_salary,
        "working_days": payslip.working_days,
        "present_days": payslip.present_days,
    }
    
    employee_data = {
        "full_name": emp.full_name if emp else "",
        "employee_id": emp.employee_id if emp else "",
        "department": dept.name if dept else "",
        "designation": emp.designation if emp else "",
    }
    
    generate_payslip_pdf(payslip_data, employee_data, output_path)
    
    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename=f"Payslip_{emp.employee_id}_{payslip.month}_{payslip.year}.pdf"
    )
