"""PDF generation service for payslips, offer letters, experience letters etc."""
import os
from datetime import date, datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, HRFlowable, PageBreak
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


def generate_offer_letter_pdf(candidate_name: str, job_title: str, ctc: float, joining_date: str, probation_months: int, valid_until: str) -> bytes:
    """Generate a formal multi-page PDF Offer Letter, Annexure, and Corporate Policies."""
    import io
    from reportlab.lib.pagesizes import letter
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles to avoid duplicate key errors
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#6c63ff'),
        alignment=1, # Center
        spaceAfter=15
    )
    
    h1_style = ParagraphStyle(
        'DocH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#1e1b4b'),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor('#334155'),
        spaceAfter=10
    )
    
    bullet_style = ParagraphStyle(
        'DocBullet',
        parent=body_style,
        leftIndent=20,
        spaceAfter=6
    )
    
    table_text_style = ParagraphStyle(
        'TableText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor('#334155')
    )
    
    table_header_style = ParagraphStyle(
        'TableHeaderText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=colors.white
    )

    story = []
    
    # ── PAGE 1: OFFER LETTER ──
    # Company Header
    story.append(Paragraph(settings.COMPANY_NAME, title_style))
    story.append(Paragraph(f"{settings.COMPANY_ADDRESS} | hr@techcorp.com", ParagraphStyle('HeaderSub', parent=body_style, alignment=1, fontSize=9, textColor=colors.HexColor('#64748b'))))
    story.append(Spacer(1, 20))
    
    # Date
    today_str = datetime.today().strftime("%d %B %Y")
    story.append(Paragraph(f"Date: {today_str}", body_style))
    story.append(Spacer(1, 10))
    
    # Candidate Address
    story.append(Paragraph(f"To,<br/><b>{candidate_name}</b>", body_style))
    story.append(Spacer(1, 10))
    
    # Subject
    story.append(Paragraph(f"<b>Subject: Letter of Offer of Employment — {job_title}</b>", h1_style))
    story.append(Spacer(1, 8))
    
    # Letter body
    story.append(Paragraph(f"Dear {candidate_name},", body_style))
    
    letter_text = (
        f"Following our recent discussions and interview rounds, we are absolutely delighted to extend to you a formal offer of employment "
        f"for the position of <b>{job_title}</b> at {settings.COMPANY_NAME}. "
        f"Your technical qualifications, problem-solving skills, and alignment with our company values were highly appreciated by the interview board."
    )
    story.append(Paragraph(letter_text, body_style))
    
    terms_intro = "The detailed terms and conditions of your employment are as follows:"
    story.append(Paragraph(terms_intro, body_style))
    
    # Bullet points of terms
    story.append(Paragraph(f"• <b>Designation:</b> {job_title}", bullet_style))
    story.append(Paragraph(f"• <b>Annual Compensation:</b> INR {ctc:,.2f} per annum (detailed breakdown provided in Annexure A)", bullet_style))
    story.append(Paragraph(f"• <b>Proposed Joining Date:</b> {joining_date}", bullet_style))
    story.append(Paragraph(f"• <b>Probation Period:</b> You will be on probation for a period of {probation_months} months from your date of joining.", bullet_style))
    story.append(Paragraph(f"• <b>Offer Validity:</b> This offer is valid until {valid_until}. Please sign and return a duplicate copy of this letter as acceptance of this offer.", bullet_style))
    
    closing_text = (
        "We are excited about the prospect of you joining our team and contributing to the next phase of our growth. "
        "We look forward to a mutually rewarding relationship."
    )
    story.append(Paragraph(closing_text, body_style))
    story.append(Spacer(1, 15))
    
    # Signatures
    story.append(Paragraph(f"For <b>{settings.COMPANY_NAME}</b>,", body_style))
    story.append(Spacer(1, 20))
    story.append(Paragraph("<b>Global Talent Acquisition Operations</b>", ParagraphStyle('SignText', parent=body_style, fontName='Helvetica-Bold')))
    story.append(Paragraph("Authorized Signatory", ParagraphStyle('SignSub', parent=body_style, fontSize=9, textColor=colors.HexColor('#64748b'))))
    
    # Force Page Break to Annexure
    story.append(PageBreak())
    
    # ── PAGE 2: ANNEXURE A (COMPENSATION SUMMARY) ──
    story.append(Paragraph("ANNEXURE A — COMPENSATION STRUCTURE", h1_style))
    story.append(Paragraph(f"<b>Candidate Name:</b> {candidate_name} | <b>Designation:</b> {job_title}", body_style))
    story.append(Spacer(1, 10))
    
    # Calculate breakdowns
    monthly_ctc = ctc / 12.0
    basic = monthly_ctc * 0.5
    hra = monthly_ctc * 0.2
    special = monthly_ctc * 0.3
    
    # Table data
    data = [
        [Paragraph("Earnings Component", table_header_style), Paragraph("Monthly (INR)", table_header_style), Paragraph("Annualized (INR)", table_header_style)],
        [Paragraph("Basic Salary (50%)", table_text_style), Paragraph(f"₹{basic:,.2f}", table_text_style), Paragraph(f"₹{basic * 12.0:,.2f}", table_text_style)],
        [Paragraph("House Rent Allowance (20%)", table_text_style), Paragraph(f"₹{hra:,.2f}", table_text_style), Paragraph(f"₹{hra * 12.0:,.2f}", table_text_style)],
        [Paragraph("Special Allowance (30%)", table_text_style), Paragraph(f"₹{special:,.2f}", table_text_style), Paragraph(f"₹{special * 12.0:,.2f}", table_text_style)],
        [Paragraph("<b>Total Gross CTC</b>", table_text_style), Paragraph(f"<b>₹{monthly_ctc:,.2f}</b>", table_text_style), Paragraph(f"<b>₹{ctc:,.2f}</b>", table_text_style)]
    ]
    
    col_widths = [200, 150, 150]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (2,0), colors.HexColor('#6c63ff')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,4), (2,4), colors.HexColor('#f1f0ff')),
    ]))
    
    story.append(t)
    story.append(Spacer(1, 20))
    story.append(Paragraph("<i>Note: All salary payments are subject to applicable statutory tax deductions as per income tax regulations in force.</i>", ParagraphStyle('NoteText', parent=body_style, fontSize=8.5, textColor=colors.HexColor('#64748b'))))
    
    # Force Page Break to Policies
    story.append(PageBreak())
    
    # ── PAGE 3: COMPANY POLICIES & TERMS ──
    story.append(Paragraph(f"{settings.COMPANY_NAME} — EMPLOYMENT POLICIES & TERMS", h1_style))
    story.append(Spacer(1, 10))
    
    story.append(Paragraph("<b>1. Code of Conduct & Ethics</b>", ParagraphStyle('SectionH', parent=h1_style, fontSize=11, spaceBefore=6)))
    story.append(Paragraph(
        f"All employees are expected to maintain the highest standards of integrity, professionalism, and ethical behavior during their association "
        f"with {settings.COMPANY_NAME}. Any compliance breach, financial misconduct, or behavior detrimental to corporate harmony shall result in immediate disciplinary action up to termination.",
        body_style
    ))
    
    story.append(Paragraph("<b>2. Confidentiality & Non-Disclosure</b>", ParagraphStyle('SectionH', parent=h1_style, fontSize=11, spaceBefore=6)))
    story.append(Paragraph(
        "As an employee, you will have access to confidential corporate databases, client strategies, code bases, and intellectual property. "
        "You are strictly prohibited from copying, distributing, sharing, or discussing any proprietary company files with any external parties, during or after your tenure. "
        "All intellectual work created during your employment remains the exclusive property of the company.",
        body_style
    ))
    
    story.append(Paragraph("<b>3. Hours of Work & Hybrid Policy</b>", ParagraphStyle('SectionH', parent=h1_style, fontSize=11, spaceBefore=6)))
    story.append(Paragraph(
        "Our standard working hour requirement is 45 hours per week (Monday to Friday, 9:00 AM to 6:00 PM). "
        "The company operates on a hybrid model. Employees are required to report to the corporate campus for a minimum of 3 days per week, "
        "with remote work allowed on the remaining days, subject to manager approval and team alignment.",
        body_style
    ))
    
    story.append(Paragraph("<b>4. Leaves & Holidays</b>", ParagraphStyle('SectionH', parent=h1_style, fontSize=11, spaceBefore=6)))
    story.append(Paragraph(
        "Employees accrue 24 calendar days of paid leaves annually, allocated on a pro-rata basis. "
        "All leaves must be requested and approved in advance by the reporting manager via the HRMS portal. "
        "In addition, the company provides 10 national/gazetted public holidays annually, published at the beginning of each calendar year.",
        body_style
    ))
    
    story.append(Paragraph("<b>5. Termination & Resignation</b>", ParagraphStyle('SectionH', parent=h1_style, fontSize=11, spaceBefore=6)))
    story.append(Paragraph(
        f"During your probation period ({probation_months} months), either party may terminate this employment agreement by providing a 15-day written notice. "
        f"Post successful confirmation, the notice period requirement shall be 30 days. The company reserves the right to relieve the employee earlier by paying "
        f"salary in lieu of notice.",
        body_style
    ))
    
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
