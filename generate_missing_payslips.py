import sys
import os
from sqlalchemy.orm import Session
from sqlalchemy import extract, func

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.database import SessionLocal
from app.models.employee import Employee, EmploymentStatus
from app.models.payroll import PayrollRun, Payslip
from app.models.attendance import Attendance, AttendanceStatus, LeaveRequest, LeaveStatus
from app.services.payroll_service import process_payslip

def generate_missing():
    db = SessionLocal()
    try:
        # Get all completed runs
        runs = db.query(PayrollRun).all()
        print(f"Found {len(runs)} payroll runs.")
        
        # Get all employees that should be paid
        employees = db.query(Employee).filter(
            Employee.employment_status.in_([
                EmploymentStatus.ACTIVE,
                EmploymentStatus.ON_NOTICE,
                EmploymentStatus.ON_LEAVE
            ])
        ).all()
        print(f"Found {len(employees)} employees eligible for payroll.")
        
        for run in runs:
            print(f"\nProcessing Run: {run.month}/{run.year} (Run ID: {run.id})")
            
            # Recalculate totals for the run later
            run_total_gross = 0
            run_total_deductions = 0
            run_total_net = 0
            run_total_employees = 0
            
            for emp in employees:
                # Check if payslip already exists for this employee and this run
                payslip = db.query(Payslip).filter(
                    Payslip.payroll_run_id == run.id,
                    Payslip.employee_id == emp.id
                ).first()
                
                if payslip:
                    print(f"  Payslip already exists for {emp.full_name} (ID: {emp.id})")
                    run_total_gross += payslip.basic_salary + payslip.hra + payslip.da + payslip.special_allowance + payslip.overtime_pay + payslip.bonus
                    run_total_deductions += payslip.pf_employee + payslip.professional_tax + payslip.tds + payslip.other_deductions
                    run_total_net += payslip.net_salary
                    run_total_employees += 1
                    continue
                
                print(f"  Generating missing payslip for {emp.full_name} (ID: {emp.id})")
                
                working_days = 22
                # Count present days
                present_count = db.query(Attendance).filter(
                    Attendance.employee_id == emp.id,
                    extract('month', Attendance.date) == run.month,
                    extract('year', Attendance.date) == run.year,
                    Attendance.status.in_([
                        AttendanceStatus.PRESENT,
                        AttendanceStatus.WORK_FROM_HOME,
                        AttendanceStatus.HALF_DAY,
                    ])
                ).count()

                approved_leave_days = db.query(
                    func.sum(LeaveRequest.days)
                ).filter(
                    LeaveRequest.employee_id == emp.id,
                    LeaveRequest.status == LeaveStatus.APPROVED,
                    extract('month', LeaveRequest.start_date) == run.month,
                    extract('year', LeaveRequest.start_date) == run.year,
                ).scalar() or 0

                present_days = min(int(present_count + approved_leave_days), working_days) if present_count > 0 else working_days
                
                payslip_data = process_payslip(emp, working_days, present_days)
                
                new_payslip = Payslip(
                    payroll_run_id=run.id,
                    employee_id=emp.id,
                    month=run.month,
                    year=run.year,
                    **payslip_data,
                    status="generated",
                )
                db.add(new_payslip)
                db.flush() # get ID/fields populated
                
                run_total_gross += payslip_data["total_earnings"]
                run_total_deductions += payslip_data["total_deductions"]
                run_total_net += payslip_data["net_salary"]
                run_total_employees += 1
            
            # Update the run totals
            run.total_gross = round(run_total_gross, 2)
            run.total_deductions = round(run_total_deductions, 2)
            run.total_net = round(run_total_net, 2)
            run.total_employees = run_total_employees
            db.add(run)
            print(f"Updated Run {run.id} totals: Gross={run.total_gross}, Deductions={run.total_deductions}, Net={run.total_net}, Employees={run.total_employees}")
        
        db.commit()
        print("\nAll missing payslips generated successfully and database committed!")
    except Exception as e:
        db.rollback()
        print(f"Error occurred: {e}")
        raise e
    finally:
        db.close()

if __name__ == '__main__':
    generate_missing()
