from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import smtplib

from loguru import logger

# TODO: Replace with apprise

def send_email(
    subject: str,
    body: str,
    to: list[str],
) -> None:
    """
    Compile subject and body into an email, and send using the computer's SMTP server.

    NOTE: this only works on linux, windows machines don't have an smtp server running by default.
    """
    # Build message
    # msg.add_header("Content-Type", "text/html")
    # msg.set_payload(body, charset="utf-8")

    msg = MIMEMultipart("alternative")
    # Attach the HTML body
    html_part = MIMEText(body, "html", "utf-8")
    msg.attach(html_part)

    msg["Subject"] = subject
    msg["From"] = "svc_mpe@alleninstitute.org"
    if email_override := os.getenv("H2RODENT_EMAIL_OVERRIDE_TO", False):
        to = [email_override]
    msg["To"] = ", ".join(to)

    smtp_server = os.getenv("H2RODENT_SMTP_SERVER", "aidc-mx-1.corp.alleninstitute.org")

    # Send message
    try:
        if int(os.getenv("H2RODENT_ENABLE_EMAILS", 0)) == 1:
            with smtplib.SMTP(smtp_server) as s:
                s.send_message(msg)
                print(f"EMAILING {to}")
        logger.info(
            f"Sent email",
            subject=subject,
            to=to,
            body=body,
        )
    except:
        logger.exception(
            "Failed to send email",
            subject=subject,
            to=to,
            body=body,
        )


def html_table(input_dict: dict) -> str:
    """Convert a dictionary to an HTML table string."""

    html = "<table border='1' cellpadding='4' cellspacing='0'>"
    # html += "<tr><th>Key</th><th>Value</th></tr>"
    for key, value in input_dict.items():
        html += f"<tr><td><b>{key}</b></td><td>{value}</td></tr>"
    html += "</table>"
    return html


def fancy_html_table(columns: list[str], rows: list[dict]) -> str:
    """Convert a list of dicts and column names to an HTML table string."""
    html = "<table border='1' cellpadding='4' cellspacing='0'>"
    # Header row
    html += "<tr>"
    for col in columns:
        html += f"<th>{col}</th>"
    html += "</tr>"
    # Data rows
    for row in rows:
        html += "<tr>"
        for col in columns:
            html += f"<td>{row.get(col, '')}</td>"
        html += "</tr>"
    html += "</table>"
    return html
