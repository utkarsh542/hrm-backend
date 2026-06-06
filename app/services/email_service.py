"""Email dispatch service — SMTP integration and terminal simulation logging."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional
from app.config import settings
from app.logger import logger


def _print_simulated_email(to_email: str, subject: str, body_text: str):
    """Log a beautifully structured corporate email box simulation in the server console."""
    divider = "═" * 70
    border = "─" * 70
    logger.info(f"\n{divider}")
    logger.info("  [CORPORATE EMAIL DISPATCH SIMULATION]")
    logger.info(divider)
    logger.info(f"  TO:      {to_email}")
    logger.info(f"  FROM:    {getattr(settings, 'SMTP_FROM', 'noreply@techcorp.com')}")
    logger.info(f"  SUBJECT: {subject}")
    logger.info(border)
    for line in body_text.strip().split("\n"):
        logger.info(f"  {line}")
    logger.info(divider + "\n")


def send_email(to_email: str, subject: str, html_content: str, text_content: str) -> bool:
    """Send an email using configured SMTP credentials or simulate delivery in terminal."""
    server = getattr(settings, "SMTP_SERVER", None)
    port = getattr(settings, "SMTP_PORT", 587)
    user = getattr(settings, "SMTP_USER", None)
    password = getattr(settings, "SMTP_PASSWORD", None)
    sender = getattr(settings, "SMTP_FROM", "noreply@techcorp.com")
    
    # If not configured, trigger the console delivery simulation
    if not server or not user or not password:
        _print_simulated_email(to_email, subject, text_content)
        return True
        
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email
        
        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))
        
        with smtplib.SMTP(server, port) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.sendmail(sender, to_email, msg.as_string())
        logger.info(f"Successfully sent email to {to_email} via SMTP.")
        return True
    except Exception as e:
        logger.error(f"Error sending SMTP email to {to_email}: {e}")
        # Graceful fallback to console logging
        _print_simulated_email(to_email, f"[SMTP FAIL FALLBACK] {subject}", text_content)
        return False


def send_email_with_attachment(to_email: str, subject: str, html_content: str, text_content: str, attachment_bytes: bytes, attachment_name: str) -> bool:
    """Send an email with a file attachment (such as a PDF)."""
    server = getattr(settings, "SMTP_SERVER", None)
    port = getattr(settings, "SMTP_PORT", 587)
    user = getattr(settings, "SMTP_USER", None)
    password = getattr(settings, "SMTP_PASSWORD", None)
    sender = getattr(settings, "SMTP_FROM", "noreply@techcorp.com")
    
    # If not configured, trigger the console delivery simulation with attachment notification
    if not server or not user or not password:
        _print_simulated_email(
            to_email, 
            subject, 
            text_content + f"\n\n[SIMULATED ATTACHMENT: {attachment_name} ({len(attachment_bytes)} bytes)]"
        )
        return True
        
    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email
        
        # Attach text and html content as alternative bodies
        body_part = MIMEMultipart("alternative")
        body_part.attach(MIMEText(text_content, "plain"))
        body_part.attach(MIMEText(html_content, "html"))
        msg.attach(body_part)
        
        # Attach the file
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={attachment_name}")
        msg.attach(part)
        
        with smtplib.SMTP(server, port) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.sendmail(sender, to_email, msg.as_string())
        logger.info(f"Successfully sent email with attachment {attachment_name} to {to_email} via SMTP.")
        return True
    except Exception as e:
        logger.error(f"Error sending SMTP email with attachment to {to_email}: {e}")
        # Fallback simulation
        _print_simulated_email(
            to_email, 
            f"[SMTP FAIL FALLBACK] {subject}", 
            text_content + f"\n\n[SIMULATED ATTACHMENT: {attachment_name} ({len(attachment_bytes)} bytes)]"
        )
        return False


def send_welcome_email(to_email: str, name: str, temp_pass: str):
    """Notify a new hire that their account is provisioned, sending their temporary credentials."""
    subject = "Welcome to TechCorp! Your HRMS Access Credentials"
    
    text = (
        f"Hi {name},\n\n"
        f"Welcome to the TechCorp team! A secure user account has been successfully provisioned for you.\n\n"
        f"You can log into your personal HRMS dashboard using the following access credentials:\n"
        f"  - Username (Email): {to_email}\n"
        f"  - Temporary Password: {temp_pass}\n\n"
        f"Please log in and update your password immediately by clicking your avatar icon -> 'Change Password'.\n\n"
        f"Best regards,\n"
        f"TechCorp HR Operations Team"
    )
    
    html = (
        f"<div style='font-family: sans-serif; max-width: 550px; margin: auto; padding: 24px; border: 1px solid #ddd; border-radius: 12px; background-color: #fcfcfc;'>"
        f"  <h2 style='color: #6c63ff; margin-bottom: 20px;'>Welcome to TechCorp!</h2>"
        f"  <p>Dear <strong>{name}</strong>,</p>"
        f"  <p>A secure login account has been successfully provisioned for you in the company's Human Resource Management System (HRMS).</p>"
        f"  <div style='background-color: #f1f0ff; border-left: 4px solid #6c63ff; padding: 16px; margin: 24px 0; border-radius: 8px;'>"
        f"    <p style='margin: 0 0 8px;'><strong>Your Access Credentials:</strong></p>"
        f"    <p style='margin: 0 0 6px; font-family: monospace;'><strong>Username:</strong> {to_email}</p>"
        f"    <p style='margin: 0; font-family: monospace;'><strong>Temporary Password:</strong> {temp_pass}</p>"
        f"  </div>"
        f"  <p>Please log into your dashboard and change your password immediately for security purposes.</p>"
        f"  <hr style='border: none; border-top: 1px solid #eee; margin: 24px 0;' />"
        f"  <p style='font-size: 12px; color: #888;'>Best regards,<br/>TechCorp HR Operations Team</p>"
        f"</div>"
    )
    
    return send_email(to_email, subject, html, text)


def send_password_change_alert(to_email: str, name: str):
    """Notify a user that their account password was updated successfully."""
    subject = "Security Alert: TechCorp HRMS Password Updated"
    
    text = (
        f"Hi {name},\n\n"
        f"This is a security confirmation that the password for your TechCorp HRMS login account ({to_email}) was successfully changed.\n\n"
        f"If you initiated this change, no further action is required.\n\n"
        f"If you did not initiate this change, please contact the HR Systems Administrator immediately to lock your account.\n\n"
        f"Best regards,\n"
        f"TechCorp Security Team"
    )
    
    html = (
        f"<div style='font-family: sans-serif; max-width: 550px; margin: auto; padding: 24px; border: 1px solid #ddd; border-radius: 12px;'>"
        f"  <h2 style='color: #ef4444; margin-bottom: 20px;'>Security Alert</h2>"
        f"  <p>Dear <strong>{name}</strong>,</p>"
        f"  <p>This is a security confirmation that the password for your HRMS account (<strong>{to_email}</strong>) was successfully changed.</p>"
        f"  <p style='color: #555;'>If you initiated this change, no action is required.</p>"
        f"  <div style='background-color: #fff8f8; border-left: 4px solid #ef4444; padding: 12px; margin: 20px 0; border-radius: 8px; font-size: 13px; color: #ef4444;'>"
        f"    <strong>If you did not change your password:</strong> Contact HR Operations or your Systems Admin immediately."
        f"  </div>"
        f"  <hr style='border: none; border-top: 1px solid #eee; margin: 24px 0;' />"
        f"  <p style='font-size: 12px; color: #888;'>Best regards,<br/>TechCorp Security Operations</p>"
        f"</div>"
    )
    
    return send_email(to_email, subject, html, text)


def send_password_reset_alert(to_email: str, name: str, temp_pass: str):
    """Notify a user that their account password was reset by an administrator."""
    subject = "Security Notice: Your TechCorp HRMS Password Reset"
    
    text = (
        f"Hi {name},\n\n"
        f"An administrator has successfully reset the login password for your TechCorp HRMS account.\n\n"
        f"Your temporary login credentials are:\n"
        f"  - Username: {to_email}\n"
        f"  - Temporary Password: {temp_pass}\n\n"
        f"Please log in and update your password immediately.\n\n"
        f"Best regards,\n"
        f"TechCorp Security Team"
    )
    
    html = (
        f"<div style='font-family: sans-serif; max-width: 550px; margin: auto; padding: 24px; border: 1px solid #ddd; border-radius: 12px;'>"
        f"  <h2 style='color: #ef4444; margin-bottom: 20px;'>Password Reset Complete</h2>"
        f"  <p>Dear <strong>{name}</strong>,</p>"
        f"  <p>An administrator has successfully reset the login password for your HRMS account.</p>"
        f"  <div style='background-color: #fdf2f2; border-left: 4px solid #ef4444; padding: 16px; margin: 20px 0; border-radius: 8px;'>"
        f"    <p style='margin: 0 0 8px;'><strong>Your Temporary Credentials:</strong></p>"
        f"    <p style='margin: 0 0 6px; font-family: monospace;'><strong>Username:</strong> {to_email}</p>"
        f"    <p style='margin: 0; font-family: monospace;'><strong>Temporary Password:</strong> {temp_pass}</p>"
        f"  </div>"
        f"  <p>Please log in and change this temporary password immediately.</p>"
        f"  <hr style='border: none; border-top: 1px solid #eee; margin: 24px 0;' />"
        f"  <p style='font-size: 12px; color: #888;'>Best regards,<br/>TechCorp Security Operations</p>"
        f"</div>"
    )
    
    return send_email(to_email, subject, html, text)


def send_leave_notification(to_email: str, employee_name: str, leave_type: str, start_date: str, end_date: str, days: float, reason: str):
    """Notify a manager/HR that an employee has applied for leave and action is pending."""
    subject = f"Leave Request Pending: {employee_name} — {days} Day(s)"
    
    text = (
        f"Hello,\n\n"
        f"An employee has submitted a leave request that requires your review:\n"
        f"  - Employee: {employee_name}\n"
        f"  - Leave Type: {leave_type.title()} Leave\n"
        f"  - Duration: {start_date} to {end_date} ({days} day(s))\n"
        f"  - Reason: \"{reason}\"\n\n"
        f"Please log into your HRMS dashboard and visit the Leave Management or Approval Center to act on this request.\n\n"
        f"Best regards,\n"
        f"TechCorp HRMS Notifications"
    )
    
    html = (
        f"<div style='font-family: sans-serif; max-width: 550px; margin: auto; padding: 24px; border: 1px solid #ddd; border-radius: 12px;'>"
        f"  <h2 style='color: #6c63ff; margin-bottom: 20px;'>Time-Off Request Received</h2>"
        f"  <p>A new leave request has been submitted and is currently pending review:</p>"
        f"  <table style='width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px;'>"
        f"    <tr><td style='padding: 8px 0; color: #666; width: 140px;'><strong>Employee:</strong></td><td style='padding: 8px 0;'><strong>{employee_name}</strong></td></tr>"
        f"    <tr><td style='padding: 8px 0; color: #666;'><strong>Leave Type:</strong></td><td style='padding: 8px 0;'>{leave_type.title()} Leave</td></tr>"
        f"    <tr><td style='padding: 8px 0; color: #666;'><strong>Duration:</strong></td><td style='padding: 8px 0;'>{start_date} to {end_date} ({days} day(s))</td></tr>"
        f"    <tr><td style='padding: 8px 0; color: #666;'><strong>Reason:</strong></td><td style='padding: 8px 0; font-style: italic;'>\"{reason}\"</td></tr>"
        f"  </table>"
        f"  <p>Please log in and approve or reject this request in the **Approval Center**.</p>"
        f"  <hr style='border: none; border-top: 1px solid #eee; margin: 24px 0;' />"
        f"  <p style='font-size: 12px; color: #888;'>Best regards,<br/>TechCorp Leave Operations</p>"
        f"</div>"
    )
    
    return send_email(to_email, subject, html, text)


def send_leave_status_update(to_email: str, employee_name: str, leave_type: str, status: str, comments: str = None):
    """Notify the employee when their leave request has been approved or rejected."""
    subject = f"Leave Request Update: {status.upper()} — {leave_type.title()} Leave"
    color = "#10b981" if status == "approved" else "#ef4444"
    
    text = (
        f"Hi {employee_name},\n\n"
        f"Your leave request has been {status} by HR/Administration.\n"
        f"  - Leave Type: {leave_type.title()} Leave\n"
        f"  - Status: {status.upper()}\n"
        f"  - Remarks: \"{comments or 'No remarks provided.'}\"\n\n"
        f"You can view updated balances inside your dashboard.\n\n"
        f"Best regards,\n"
        f"TechCorp HR Operations"
    )
    
    html = (
        f"<div style='font-family: sans-serif; max-width: 550px; margin: auto; padding: 24px; border: 1px solid #ddd; border-radius: 12px;'>"
        f"  <h2 style='color: {color}; margin-bottom: 20px;'>Leave Request {status.title()}</h2>"
        f"  <p>Dear <strong>{employee_name}</strong>,</p>"
        f"  <p>Your request for <strong>{leave_type.title()} Leave</strong> has been reviewed:</p>"
        f"  <div style='background-color: #fafafa; border: 1px solid #eee; padding: 16px; margin: 20px 0; border-radius: 8px; font-size: 14px;'>"
        f"    <p style='margin: 0 0 8px;'><strong>Status:</strong> <span style='color: {color}; font-weight: 700;'>{status.upper()}</span></p>"
        f"    <p style='margin: 0;'><strong>HR Remarks:</strong> \"{comments or 'No remarks provided.'}\"</p>"
        f"  </div>"
        f"  <hr style='border: none; border-top: 1px solid #eee; margin: 24px 0;' />"
        f"  <p style='font-size: 12px; color: #888;'>Best regards,<br/>TechCorp HR Operations Team</p>"
        f"</div>"
    )
    
    return send_email(to_email, subject, html, text)


def send_resignation_notification(to_email: str, employee_name: str, notice_days: int, lwd: str, reason: str):
    """Notify HR and managers that an employee has submitted their resignation."""
    subject = f"Alert: Resignation Submitted by {employee_name}"
    
    text = (
        f"Hello HR Operations,\n\n"
        f"An employee has formally submitted their resignation request:\n"
        f"  - Employee: {employee_name}\n"
        f"  - Notice Period: {notice_days} days\n"
        f"  - Proposed Last Working Day: {lwd}\n"
        f"  - Reason: \"{reason}\"\n\n"
        f"Please visit the Offboarding pipeline dashboard to process exit interview clearings and final settlements.\n\n"
        f"Best regards,\n"
        f"TechCorp HRMS Notifications"
    )
    
    html = (
        f"<div style='font-family: sans-serif; max-width: 550px; margin: auto; padding: 24px; border: 1px solid #ddd; border-radius: 12px;'>"
        f"  <h2 style='color: #ef4444; margin-bottom: 20px;'>Resignation Request Received</h2>"
        f"  <p>A formal resignation proposal has been recorded in the offboarding registry:</p>"
        f"  <table style='width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px;'>"
        f"    <tr><td style='padding: 8px 0; color: #666; width: 150px;'><strong>Employee Name:</strong></td><td style='padding: 8px 0;'><strong>{employee_name}</strong></td></tr>"
        f"    <tr><td style='padding: 8px 0; color: #666;'><strong>Notice Period:</strong></td><td style='padding: 8px 0;'>{notice_days} days</td></tr>"
        f"    <tr><td style='padding: 8px 0; color: #666;'><strong>Last Working Day:</strong></td><td style='padding: 8px 0;'><strong>{lwd}</strong></td></tr>"
        f"    <tr><td style='padding: 8px 0; color: #666;'><strong>Reason:</strong></td><td style='padding: 8px 0; font-style: italic;'>\"{reason}\"</td></tr>"
        f"  </table>"
        f"  <p>Please review this proposal in the **Offboarding** dashboard.</p>"
        f"  <hr style='border: none; border-top: 1px solid #eee; margin: 24px 0;' />"
        f"  <p style='font-size: 12px; color: #888;'>Best regards,<br/>TechCorp Offboarding Operations</p>"
        f"</div>"
    )
    
    return send_email(to_email, subject, html, text)


def send_offboarding_completion_email(to_email: str, name: str, lwd: str, total_settlement: float, exit_interview_done: bool):
    """Notify the employee that their offboarding has been completed and final settlement cleared."""
    subject = "TechCorp HRMS: Offboarding Completed & Final Settlement Cleared"
    
    text = (
        f"Hi {name},\n\n"
        f"We are writing to confirm that your offboarding process at TechCorp has been successfully completed.\n\n"
        f"Details:\n"
        f"  - Last Working Day: {lwd}\n"
        f"  - Final Settlement Amount: ${total_settlement:,.2f}\n"
        f"  - Exit Interview Status: {'Completed' if exit_interview_done else 'Pending/Skipped'}\n\n"
        f"Your login credentials and company system access have been deactivated as of today. If you have any questions regarding your final settlement, relieving documents, or experience letter, please feel free to reach out to the HR Operations team.\n\n"
        f"We thank you for your contributions to TechCorp and wish you the very best in your future endeavors!\n\n"
        f"Best regards,\n"
        f"TechCorp HR Operations"
    )
    
    html = (
        f"<div style='font-family: sans-serif; max-width: 550px; margin: auto; padding: 24px; border: 1px solid #ddd; border-radius: 12px; background-color: #fcfcfc;'>"
        f"  <h2 style='color: #10b981; margin-bottom: 20px;'>Offboarding Completed</h2>"
        f"  <p>Dear <strong>{name}</strong>,</p>"
        f"  <p>This email confirms that your formal offboarding process at TechCorp has been successfully completed and approved by HR/Administration.</p>"
        f"  <div style='background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 16px; margin: 24px 0; border-radius: 8px;'>"
        f"    <p style='margin: 0 0 8px;'><strong>Final Offboarding Summary:</strong></p>"
        f"    <p style='margin: 0 0 6px;'><strong>Last Working Day:</strong> {lwd}</p>"
        f"    <p style='margin: 0 0 6px;'><strong>Exit Interview:</strong> {'Completed' if exit_interview_done else 'Pending / Skipped'}</p>"
        f"    <p style='margin: 0;'><strong>Final Settlement:</strong> <span style='color: #10b981; font-weight: 700;'>${total_settlement:,.2f}</span></p>"
        f"  </div>"
        f"  <p>Your access credentials have been deactivated. Your experience and relieving letters are generated and attached to your offboarding records. Please contact HR Operations if you have any questions.</p>"
        f"  <p>We sincerely appreciate your dedicated service and contributions to TechCorp. We wish you the very best of success in all your future professional and personal endeavors.</p>"
        f"  <hr style='border: none; border-top: 1px solid #eee; margin: 24px 0;' />"
        f"  <p style='font-size: 12px; color: #888;'>Best regards,<br/>TechCorp HR Operations Team</p>"
        f"</div>"
    )
    
    return send_email(to_email, subject, html, text)


def send_interview_invitation_email(to_email: str, candidate_name: str, job_title: str, round_number: int, interview_type: str, scheduled_at: str, interviewer_name: str, meeting_link: str, is_update: bool = False):
    """Send an interview invitation email containing round details, schedule, and join link."""
    action_type = "Updated Invitation" if is_update else "Invitation"
    subject = f"{action_type}: Round {round_number} {interview_type.title()} Interview — {job_title}"
    
    text = (
        f"Hi {candidate_name},\n\n"
        f"We are pleased to invite you for the next round of interview for the {job_title} position at TechCorp.\n\n"
        f"Interview Details:\n"
        f"  - Stage: Round {round_number} ({interview_type.title()} Interview)\n"
        f"  - Date & Time: {scheduled_at}\n"
        f"  - Interviewer: {interviewer_name or 'TechCorp Interviewing Panel'}\n"
        f"  - Meeting Link: {meeting_link}\n\n"
        f"Please click the link above at the scheduled time to join the interview room.\n\n"
        f"Best regards,\n"
        f"TechCorp Recruitment Team"
    )
    
    html = (
        f"<div style='font-family: sans-serif; max-width: 550px; margin: auto; padding: 24px; border: 1px solid #ddd; border-radius: 12px; background-color: #fcfcfc;'>"
        f"  <h2 style='color: #6c63ff; margin-bottom: 20px;'>Interview Invitation</h2>"
        f"  <p>Dear <strong>{candidate_name}</strong>,</p>"
        f"  <p>We are pleased to invite you for the next round of interview for the <strong>{job_title}</strong> position at TechCorp.</p>"
        f"  <div style='background-color: #f1f0ff; border-left: 4px solid #6c63ff; padding: 16px; margin: 24px 0; border-radius: 8px; font-size: 14px;'>"
        f"    <p style='margin: 0 0 8px;'><strong>Interview Round Details:</strong></p>"
        f"    <p style='margin: 0 0 6px;'><strong>Round:</strong> Round {round_number} ({interview_type.title()} Interview)</p>"
        f"    <p style='margin: 0 0 6px;'><strong>Date & Time:</strong> {scheduled_at}</p>"
        f"    <p style='margin: 0 0 6px;'><strong>Interviewer:</strong> {interviewer_name or 'TechCorp Interviewing Panel'}</p>"
        f"    <p style='margin: 0;'><strong>Meeting Link:</strong> <a href='{meeting_link}' style='color: #6c63ff; font-weight: 600;'>Join Interview Room</a></p>"
        f"  </div>"
        f"  <p>Please click the meeting link at the scheduled time to enter the interview room. If you need to reschedule, please notify the recruiter immediately.</p>"
        f"  <hr style='border: none; border-top: 1px solid #eee; margin: 24px 0;' />"
        f"  <p style='font-size: 12px; color: #888;'>Best regards,<br/>TechCorp Recruitment Team</p>"
        f"</div>"
    )
    
    return send_email(to_email, subject, html, text)

