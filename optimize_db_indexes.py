import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.logger import logger
"""Database Index Optimizer for HRMS SQLite Database."""
import sqlite3
import os

db_path = r"c:\Users\Utkarsh Gupta\Downloads\hrm\backend\hrms.db"

if not os.path.exists(db_path):
    logger.error(f"Error: Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

indexes = [
    # 1. Attendance Table Indexes
    "CREATE INDEX IF NOT EXISTS ix_attendance_employee_date ON attendance(employee_id, date);",
    "CREATE INDEX IF NOT EXISTS ix_attendance_date ON attendance(date);",
    "CREATE INDEX IF NOT EXISTS ix_attendance_employee_id ON attendance(employee_id);",
    
    # 2. Leave Requests Table Indexes
    "CREATE INDEX IF NOT EXISTS ix_leave_requests_employee_id ON leave_requests(employee_id);",
    "CREATE INDEX IF NOT EXISTS ix_leave_requests_status ON leave_requests(status);",
    
    # 3. Employees Table Indexes
    "CREATE INDEX IF NOT EXISTS ix_employees_user_id ON employees(user_id);",
    "CREATE INDEX IF NOT EXISTS ix_employees_department_id ON employees(department_id);",
    "CREATE INDEX IF NOT EXISTS ix_employees_reporting_manager_id ON employees(reporting_manager_id);",
    
    # 4. Approval Requests Table Indexes
    "CREATE INDEX IF NOT EXISTS ix_approval_requests_approver_id ON approval_requests(approver_id);",
    "CREATE INDEX IF NOT EXISTS ix_approval_requests_status ON approval_requests(status);",
    "CREATE INDEX IF NOT EXISTS ix_approval_requests_requested_by ON approval_requests(requested_by);",
    
    # 5. Expenses Table Indexes
    "CREATE INDEX IF NOT EXISTS ix_expenses_employee_id ON expenses(employee_id);",
    "CREATE INDEX IF NOT EXISTS ix_expenses_status ON expenses(status);",
    
    # 6. Face Attendance Table Indexes
    "CREATE INDEX IF NOT EXISTS ix_face_attendance_employee_id ON face_attendance(employee_id);",
    "CREATE INDEX IF NOT EXISTS ix_face_attendance_date ON face_attendance(date);",
    
    # 7. Payslips Table Indexes
    "CREATE INDEX IF NOT EXISTS ix_payslips_employee_id ON payslips(employee_id);",
    "CREATE INDEX IF NOT EXISTS ix_payslips_payroll_run_id ON payslips(payroll_run_id);",
    
    # 8. Performance Reviews Table Indexes
    "CREATE INDEX IF NOT EXISTS ix_performance_reviews_employee_id ON performance_reviews(employee_id);",
    "CREATE INDEX IF NOT EXISTS ix_performance_reviews_status ON performance_reviews(status);",
    
    # 9. Goals Table Indexes
    "CREATE INDEX IF NOT EXISTS ix_goals_employee_id ON goals(employee_id);",
    "CREATE INDEX IF NOT EXISTS ix_goals_status ON goals(status);",
    
    # 10. Documents Table Indexes
    "CREATE INDEX IF NOT EXISTS ix_documents_employee_id ON documents(employee_id);",
    "CREATE INDEX IF NOT EXISTS ix_documents_candidate_id ON documents(candidate_id);"
]

logger.info(f"Applying {len(indexes)} index optimization commands to {db_path}...")

try:
    for idx_sql in indexes:
        # Extract index name for log transparency
        idx_name = idx_sql.split("IF NOT EXISTS ")[1].split(" ON")[0]
        cursor.execute(idx_sql)
        logger.info(f"  [OK] Index ensured: {idx_name}")
    conn.commit()
    logger.info("Database index optimizations applied successfully!")
except Exception as e:
    conn.rollback()
    logger.error(f"Error executing database migrations: {e}")
finally:
    conn.close()
