"""Salary Benchmarking router — India market data comparison."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.employee import Employee, Department

router = APIRouter(prefix="/api/benchmarking", tags=["Salary Benchmarking"])

# India market salary data (INR annual CTC) — sourced from AmbitionBox / Glassdoor / LinkedIn 2024
MARKET_DATA: dict = {
    # designation_keyword → {p25, p50, p75, p90}
    "junior developer":       {"p25": 400000,  "p50": 600000,  "p75": 900000,  "p90": 1200000},
    "developer":              {"p25": 600000,  "p50": 900000,  "p75": 1400000, "p90": 1800000},
    "senior developer":       {"p25": 1200000, "p50": 1800000, "p75": 2400000, "p90": 3200000},
    "full stack developer":   {"p25": 700000,  "p50": 1200000, "p75": 1800000, "p90": 2500000},
    "tech lead":              {"p25": 1800000, "p50": 2400000, "p75": 3200000, "p90": 4500000},
    "engineering manager":    {"p25": 2500000, "p50": 3500000, "p75": 5000000, "p90": 7000000},
    "vp engineering":         {"p25": 4000000, "p50": 6000000, "p75": 9000000, "p90": 14000000},
    "devops engineer":        {"p25": 800000,  "p50": 1400000, "p75": 2000000, "p90": 2800000},
    "qa engineer":            {"p25": 500000,  "p50": 800000,  "p75": 1200000, "p90": 1600000},
    "product manager":        {"p25": 1500000, "p50": 2200000, "p75": 3200000, "p90": 5000000},
    "product designer":       {"p25": 800000,  "p50": 1300000, "p75": 1900000, "p90": 2800000},
    "ui/ux designer":         {"p25": 600000,  "p50": 1000000, "p75": 1600000, "p90": 2200000},
    "hr director":            {"p25": 1500000, "p50": 2200000, "p75": 3200000, "p90": 5000000},
    "hr executive":           {"p25": 300000,  "p50": 500000,  "p75": 800000,  "p90": 1200000},
    "hr manager":             {"p25": 700000,  "p50": 1100000, "p75": 1600000, "p90": 2400000},
    "finance manager":        {"p25": 1000000, "p50": 1600000, "p75": 2400000, "p90": 3500000},
    "sales manager":          {"p25": 800000,  "p50": 1400000, "p75": 2200000, "p90": 3500000},
    "sales executive":        {"p25": 300000,  "p50": 500000,  "p75": 800000,  "p90": 1200000},
    "marketing lead":         {"p25": 800000,  "p50": 1300000, "p75": 2000000, "p90": 3000000},
    "data analyst":           {"p25": 500000,  "p50": 900000,  "p75": 1400000, "p90": 2000000},
    "data scientist":         {"p25": 900000,  "p50": 1500000, "p75": 2400000, "p90": 3500000},
}

DEFAULT_BENCHMARK = {"p25": 500000, "p50": 900000, "p75": 1400000, "p90": 2000000}


def _get_benchmark(designation: str) -> dict:
    if not designation:
        return DEFAULT_BENCHMARK
    d = designation.lower()
    for key, data in MARKET_DATA.items():
        if key in d or d in key:
            return data
    return DEFAULT_BENCHMARK


def _percentile_label(ctc: float, bench: dict) -> str:
    if ctc >= bench["p90"]:
        return "Top 10% — Above market"
    elif ctc >= bench["p75"]:
        return "Top 25% — Competitive"
    elif ctc >= bench["p50"]:
        return "Above median"
    elif ctc >= bench["p25"]:
        return "Below median"
    else:
        return "Bottom 25% — At risk"


def _risk_level(ctc: float, bench: dict) -> str:
    if ctc < bench["p25"]:
        return "high"
    elif ctc < bench["p50"]:
        return "medium"
    return "low"


@router.get("/")
def get_benchmarking(db: Session = Depends(get_db)):
    """Return salary benchmarking for all active employees."""
    employees = db.query(Employee).filter(Employee.is_active == True).all()
    results = []
    for emp in employees:
        bench = _get_benchmark(emp.designation or "")
        dept = db.query(Department).filter(Department.id == emp.department_id).first()
        gap = emp.ctc - bench["p50"]
        results.append({
            "employee_id": emp.id,
            "employee_code": emp.employee_id,
            "full_name": emp.full_name,
            "designation": emp.designation or "—",
            "department": dept.name if dept else "—",
            "current_ctc": emp.ctc,
            "market_p25": bench["p25"],
            "market_p50": bench["p50"],
            "market_p75": bench["p75"],
            "market_p90": bench["p90"],
            "gap_from_median": round(gap, 0),
            "gap_percent": round((gap / bench["p50"]) * 100, 1) if bench["p50"] else 0,
            "percentile_label": _percentile_label(emp.ctc, bench),
            "retention_risk": _risk_level(emp.ctc, bench),
        })
    results.sort(key=lambda x: x["gap_from_median"])
    return results


@router.get("/summary")
def benchmarking_summary(db: Session = Depends(get_db)):
    employees = db.query(Employee).filter(Employee.is_active == True).all()
    high_risk = 0
    medium_risk = 0
    low_risk = 0
    total_gap = 0
    for emp in employees:
        bench = _get_benchmark(emp.designation or "")
        risk = _risk_level(emp.ctc, bench)
        gap = emp.ctc - bench["p50"]
        total_gap += gap
        if risk == "high":
            high_risk += 1
        elif risk == "medium":
            medium_risk += 1
        else:
            low_risk += 1
    return {
        "total_employees": len(employees),
        "high_risk": high_risk,
        "medium_risk": medium_risk,
        "low_risk": low_risk,
        "avg_gap_from_median": round(total_gap / len(employees), 0) if employees else 0,
    }


@router.get("/designation/{designation}")
def benchmark_by_designation(designation: str):
    """Get market benchmark for a specific designation."""
    bench = _get_benchmark(designation)
    return {
        "designation": designation,
        "market_p25": bench["p25"],
        "market_p50": bench["p50"],
        "market_p75": bench["p75"],
        "market_p90": bench["p90"],
        "source": "AmbitionBox / Glassdoor / LinkedIn India 2024",
    }
