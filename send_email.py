"""Email sending logic for the Resolution Alert System."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date

from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_FROM, EMAIL_TO


def send_alert_email(html_content: str, plaintext_content: str, target_date: date,
                     recipients: list[str] = None) -> bool:
    """
    Send the resolution alert email.

    Returns True if sent successfully, False otherwise.
    If SMTP is not configured, prints a warning and returns False.
    """
    if recipients is None:
        recipients = EMAIL_TO

    if not SMTP_HOST or not recipients:
        print("  Email delivery not configured. Set SMTP_HOST and EMAIL_TO environment variables.")
        print("  The HTML output has been saved to the output directory instead.")
        return False

    subject = f"Congressional Resolution Alert — {target_date.strftime('%B %-d, %Y')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(recipients)

    # Attach plaintext and HTML (email clients prefer the last part)
    msg.attach(MIMEText(plaintext_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            if SMTP_PORT == 587:
                server.starttls()
                server.ehlo()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, recipients, msg.as_string())
        print(f"  Email sent to {', '.join(recipients)}")
        return True
    except Exception as e:
        print(f"  Failed to send email: {e}")
        return False
