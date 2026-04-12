# HRMS Backend

Enterprise Human Resource Management System — Backend API built with **FastAPI**.

## Tech Stack

- **Framework:** FastAPI 0.115
- **Database:** SQLite (SQLAlchemy 2.0 ORM)
- **Auth:** JWT (python-jose) + bcrypt password hashing
- **PDF Generation:** ReportLab
- **Server:** Uvicorn

## Modules

| Module | Description |
|--------|-------------|
| **Auth** | JWT-based login, role-based access (Admin, HR, Manager, Employee) |
| **Dashboard** | Org-wide stats and analytics |
| **Recruitment** | Job postings, candidate tracking, AI-powered resume screening |
| **Interviews** | Interview scheduling and management |
| **Employees** | Employee directory, departments, onboarding |
| **Attendance** | Check-in/out, leave requests, holiday calendar |
| **Payroll** | Salary breakup, payslip generation (PDF), payroll runs |
| **Performance** | Reviews, goals, ratings across multiple cycles |
| **Offboarding** | Resignation workflow, exit management |

## Project Structure

```
backend/
├── main.py                  # App entry point + demo data seeder
├── requirements.txt         # Python dependencies
├── app/
│   ├── config.py            # App settings (Pydantic Settings)
│   ├── database.py          # SQLAlchemy engine & session
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── routers/             # API route handlers
│   └── services/            # Business logic (auth, payroll, AI, PDF)
```

## Getting Started

### Prerequisites

- Python 3.10+

### Setup

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

### API Docs

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Demo Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@techcorp.com | admin123 |
| HR | hr@techcorp.com | hr123 |
| Manager | manager@techcorp.com | manager123 |
| Employee | employee@techcorp.com | employee123 |

## Frontend

The frontend (Next.js) is maintained in a separate repo: [hrm-frontend](https://github.com/utkarsh542/hrm-frontend)
