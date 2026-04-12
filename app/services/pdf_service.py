"""PDF generation service for payslips, offer letters, experience letters etc."""
import os
from datetime import date, datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

from app.config import settings


def generate_payslip_pdf(payslip_data: dict, employee_data: dict, output_path: str) -> str:
    """Generate a professional payslip PDF."""
    
    doc = SimpleDocTemplate(output_path, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    elements = []
    
    # Title style
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=16, textColor=colors.HexColor('#1a1a2e'))
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=10, textColor=colors.grey)
    header_style = ParagraphStyle('Header', parent=styles['Normal'], fontSize=12, textColor=colors.HexColor('#1a1a2e'), spaceAfter=6)
    
    # Company Header
    elements.append(Paragraph(settings.COMPANY_NAME, title_style))
    elements.append(Paragraph(settings.COMPANY_ADDRESS, subtitle_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#6c63ff')))
    elements.append(Spacer(1, 10))
    
    month_names = ["", "January", "February", "March", "April", "May", "June", 
                   "July", "August", "September", "October", "November", "December"]
    period = f"{month_names[payslip_data.get('month', 1)]} {payslip_data.get('year', 2024)}"
    elements.append(Paragraph(f"PAYSLIP — {period}", header_style))
    elements.append(Spacer(1, 10))
    
    # Employee Info Table
    emp_data = [
        ["Employee Name:", employee_data.get("full_name", ""), "Employee ID:", employee_data.get("employee_id", "")],
        ["Department:", employee_data.get("department", ""), "Designation:", employee_data.get("designation", "")],
        ["Working Days:", str(payslip_data.get("working_days", 0)), "Present Days:", str(payslip_data.get("present_days", 0))],
    ]
    
    emp_table = Table(emp_data, colWidths=[100, 150, 100, 150])
    emp_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(emp_table)
    elements.append(Spacer(1, 15))
    
    # Earnings & Deductions Table
    salary_data = [
        ["EARNINGS", "Amount (₹)", "DEDUCTIONS", "Amount (₹)"],
        ["Basic Salary", f"{payslip_data.get('basic_salary', 0):,.2f}", "PF (Employee)", f"{payslip_data.get('pf_employee', 0):,.2f}"],
        ["HRA", f"{payslip_data.get('hra', 0):,.2f}", "Professional Tax", f"{payslip_data.get('professional_tax', 0):,.2f}"],
        ["DA", f"{payslip_data.get('da', 0):,.2f}", "TDS", f"{payslip_data.get('tds', 0):,.2f}"],
        ["Special Allowance", f"{payslip_data.get('special_allowance', 0):,.2f}", "", ""],
        ["", "", "", ""],
        ["Total Earnings", f"{payslip_data.get('total_earnings', 0):,.2f}", "Total Deductions", f"{payslip_data.get('total_deductions', 0):,.2f}"],
    ]
    
    salary_table = Table(salary_data, colWidths=[130, 120, 130, 120])
    salary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c63ff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f5')),
    ]))
    elements.append(salary_table)
    elements.append(Spacer(1, 15))
    
    # Net Salary
    net_data = [["NET SALARY", f"₹ {payslip_data.get('net_salary', 0):,.2f}"]]
    net_table = Table(net_data, colWidths=[380, 120])
    net_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
    ]))
    elements.append(net_table)
    elements.append(Spacer(1, 20))
    
    # Footer
    elements.append(Paragraph("This is a system-generated document and does not require a signature.", 
                             ParagraphStyle('Footer', fontSize=8, textColor=colors.grey, alignment=TA_CENTER)))
    
    doc.build(elements)
    return output_path


def generate_experience_letter_pdf(employee_data: dict, output_path: str) -> str:
    """Generate experience letter PDF."""
    
    doc = SimpleDocTemplate(output_path, pagesize=A4, topMargin=30*mm, bottomMargin=30*mm)
    styles = getSampleStyleSheet()
    elements = []
    
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=16, textColor=colors.HexColor('#1a1a2e'))
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=11, leading=18, spaceBefore=6, spaceAfter=6)
    
    elements.append(Paragraph(settings.COMPANY_NAME, title_style))
    elements.append(Paragraph(settings.COMPANY_ADDRESS, ParagraphStyle('Addr', fontSize=10, textColor=colors.grey)))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#6c63ff')))
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph(f"Date: {date.today().strftime('%B %d, %Y')}", body_style))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<b>EXPERIENCE CERTIFICATE</b>", ParagraphStyle('H', fontSize=14, alignment=TA_CENTER, spaceBefore=10, spaceAfter=20)))
    
    elements.append(Paragraph("To Whom It May Concern,", body_style))
    elements.append(Spacer(1, 10))
    
    name = employee_data.get("full_name", "Employee")
    emp_id = employee_data.get("employee_id", "N/A")
    designation = employee_data.get("designation", "N/A")
    department = employee_data.get("department", "N/A")
    joining = employee_data.get("joining_date", "N/A")
    lwd = employee_data.get("last_working_day", date.today().strftime("%Y-%m-%d"))
    
    body = f"""This is to certify that <b>{name}</b> (Employee ID: {emp_id}) was employed with 
    {settings.COMPANY_NAME} from <b>{joining}</b> to <b>{lwd}</b> in the capacity of 
    <b>{designation}</b> in the <b>{department}</b> department."""
    elements.append(Paragraph(body, body_style))
    elements.append(Spacer(1, 10))
    
    body2 = f"""During the tenure with us, we found {name} to be sincere, hardworking, and dedicated. 
    Their conduct was found to be good, and their performance was satisfactory."""
    elements.append(Paragraph(body2, body_style))
    elements.append(Spacer(1, 10))
    
    body3 = f"""We wish {name} all the best in future endeavors."""
    elements.append(Paragraph(body3, body_style))
    elements.append(Spacer(1, 30))
    
    elements.append(Paragraph("For and on behalf of", body_style))
    elements.append(Paragraph(f"<b>{settings.COMPANY_NAME}</b>", body_style))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Authorized Signatory", body_style))
    elements.append(Paragraph("Human Resources Department", ParagraphStyle('Dept', fontSize=10, textColor=colors.grey)))
    
    doc.build(elements)
    return output_path


def generate_relieving_letter_pdf(employee_data: dict, output_path: str) -> str:
    """Generate relieving letter PDF."""
    
    doc = SimpleDocTemplate(output_path, pagesize=A4, topMargin=30*mm, bottomMargin=30*mm)
    styles = getSampleStyleSheet()
    elements = []
    
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=16, textColor=colors.HexColor('#1a1a2e'))
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=11, leading=18, spaceBefore=6, spaceAfter=6)
    
    elements.append(Paragraph(settings.COMPANY_NAME, title_style))
    elements.append(Paragraph(settings.COMPANY_ADDRESS, ParagraphStyle('Addr', fontSize=10, textColor=colors.grey)))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#6c63ff')))
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph(f"Date: {date.today().strftime('%B %d, %Y')}", body_style))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<b>RELIEVING LETTER</b>", ParagraphStyle('H', fontSize=14, alignment=TA_CENTER, spaceBefore=10, spaceAfter=20)))
    
    name = employee_data.get("full_name", "Employee")
    emp_id = employee_data.get("employee_id", "N/A")
    designation = employee_data.get("designation", "N/A")
    lwd = employee_data.get("last_working_day", date.today().strftime("%Y-%m-%d"))
    
    elements.append(Paragraph(f"Dear <b>{name}</b>,", body_style))
    elements.append(Spacer(1, 10))
    
    body = f"""With reference to your resignation letter, we hereby confirm that you have been 
    relieved from your duties at {settings.COMPANY_NAME} effective <b>{lwd}</b>."""
    elements.append(Paragraph(body, body_style))
    elements.append(Spacer(1, 10))
    
    body2 = f"""You were working as <b>{designation}</b> (Employee ID: {emp_id}). Your full and 
    final settlement will be processed as per company policy."""
    elements.append(Paragraph(body2, body_style))
    elements.append(Spacer(1, 10))
    
    body3 = """We confirm that you have handed over all company property and there are no dues 
    pending from your side. We wish you all the best in your future endeavors."""
    elements.append(Paragraph(body3, body_style))
    elements.append(Spacer(1, 30))
    
    elements.append(Paragraph("For and on behalf of", body_style))
    elements.append(Paragraph(f"<b>{settings.COMPANY_NAME}</b>", body_style))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Authorized Signatory", body_style))
    elements.append(Paragraph("Human Resources Department", ParagraphStyle('Dept', fontSize=10, textColor=colors.grey)))
    
    doc.build(elements)
    return output_path
