"""Payroll calculation service — Indian tax structure (INR)."""
from datetime import date
from typing import Dict


def calculate_salary_breakup(annual_ctc: float) -> Dict:
    """Calculate monthly salary components from annual CTC.
    
    Indian salary structure:
    - Basic: 40% of CTC
    - HRA: 20% of CTC
    - DA: 10% of CTC
    - Special Allowance: Remaining
    - PF (Employee): 12% of Basic
    - PF (Employer): 12% of Basic
    """
    monthly_ctc = annual_ctc / 12
    
    basic = round(annual_ctc * 0.40 / 12, 2)
    hra = round(annual_ctc * 0.20 / 12, 2)
    da = round(annual_ctc * 0.10 / 12, 2)
    pf_employee = round(basic * 0.12, 2)
    pf_employer = round(basic * 0.12, 2)
    
    # Special allowance = CTC - Basic - HRA - DA - PF(employer)
    special_allowance = round(monthly_ctc - basic - hra - da - pf_employer, 2)
    
    return {
        "basic": basic,
        "hra": hra,
        "da": da,
        "special_allowance": max(special_allowance, 0),
        "pf_employee": pf_employee,
        "pf_employer": pf_employer,
    }


def calculate_tds(annual_income: float, regime: str = "new") -> float:
    """Calculate monthly TDS based on Indian New Tax Regime (2024-25).
    
    New Regime Slabs:
    0 - 3L: Nil
    3L - 7L: 5%
    7L - 10L: 10%
    10L - 12L: 15%
    12L - 15L: 20%
    15L+: 30%
    
    Standard deduction: ₹75,000
    """
    taxable_income = max(annual_income - 75000, 0)  # Standard deduction
    
    tax = 0
    if taxable_income <= 300000:
        tax = 0
    elif taxable_income <= 700000:
        tax = (taxable_income - 300000) * 0.05
    elif taxable_income <= 1000000:
        tax = 20000 + (taxable_income - 700000) * 0.10
    elif taxable_income <= 1200000:
        tax = 50000 + (taxable_income - 1000000) * 0.15
    elif taxable_income <= 1500000:
        tax = 80000 + (taxable_income - 1200000) * 0.20
    else:
        tax = 140000 + (taxable_income - 1500000) * 0.30
    
    # Add 4% cess
    tax = tax * 1.04
    
    # Rebate u/s 87A (if taxable income <= 7L, tax = 0)
    if taxable_income <= 700000:
        tax = 0
    
    monthly_tds = round(tax / 12, 2)
    return monthly_tds


def calculate_professional_tax(monthly_gross: float, state: str = "karnataka") -> float:
    """Calculate professional tax based on state.
    Karnataka: ₹200/month if salary > ₹15,000
    """
    if state == "karnataka":
        return 200 if monthly_gross > 15000 else 0
    elif state == "maharashtra":
        if monthly_gross > 10000:
            return 200
        elif monthly_gross > 7500:
            return 175
        else:
            return 0
    return 200 if monthly_gross > 15000 else 0


def process_payslip(employee, working_days: int, present_days: int) -> Dict:
    """Process payslip for an employee for a given month."""
    
    # Pro-rate salary based on attendance
    attendance_factor = present_days / working_days if working_days > 0 else 1
    
    basic = round(employee.basic_salary * attendance_factor, 2)
    hra = round(employee.hra * attendance_factor, 2)
    da = round(employee.da * attendance_factor, 2)
    special_allowance = round(employee.special_allowance * attendance_factor, 2)
    
    total_earnings = basic + hra + da + special_allowance
    
    # Deductions
    pf_employee = round(basic * 0.12, 2)
    pf_employer = round(basic * 0.12, 2)
    professional_tax = calculate_professional_tax(total_earnings)
    tds = calculate_tds(employee.ctc)
    
    total_deductions = pf_employee + professional_tax + tds
    net_salary = round(total_earnings - total_deductions, 2)
    
    return {
        "basic_salary": basic,
        "hra": hra,
        "da": da,
        "special_allowance": special_allowance,
        "total_earnings": total_earnings,
        "pf_employee": pf_employee,
        "pf_employer": pf_employer,
        "professional_tax": professional_tax,
        "tds": tds,
        "total_deductions": total_deductions,
        "net_salary": net_salary,
        "working_days": working_days,
        "present_days": present_days,
    }
