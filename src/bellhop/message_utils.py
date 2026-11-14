import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger

# TODO: Replace with apprise and fix config


def send_email(
    subject: str,
    body: str,
    to: list[str],
    from_email: str,
    smtp_server: str | None,
) -> None:
    """
    Compile subject and body into an email, and send using the specified SMTP server.
    """
    # Build message
    # msg.add_header("Content-Type", "text/html")
    # msg.set_payload(body, charset="utf-8")

    msg = MIMEMultipart("alternative")
    # Attach the HTML body
    html_part = MIMEText(body, "html", "utf-8")
    msg.attach(html_part)

    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = ", ".join(to)

    # Send message
    try:
        if int(os.getenv("BELLHOP_DISABLE_EMAILS", 0)) == 1:
            logger.info("BELLHOP_DISABLE_EMAILS is set; skipping email")
            return
        if not smtp_server:
            logger.warning("No SMTP server configured (Config.smtp_server); skipping email")
            return
        with smtplib.SMTP(smtp_server) as s:
            s.send_message(msg)
        logger.info(
            "Sent email",
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
