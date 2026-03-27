"""Email sender — loads credentials from EMAIL_CREDENTIALS env var."""

import json
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr
from typing import Optional, Tuple

from config import EMAIL_CREDENTIALS_JSON


class EmailSender:
    """Send emails via SMTP using the first account per publisher."""

    def __init__(self):
        self.credentials = self._load_credentials()

    def _load_credentials(self) -> dict:
        """Load credentials from EMAIL_CREDENTIALS env var (JSON string)."""
        raw = EMAIL_CREDENTIALS_JSON
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def get_publishers(self) -> list:
        """Return list of publishers that use Brevo SMTP."""
        result = []
        for key, val in self.credentials.items():
            smtp = (val.get("smtp_server") or "").lower()
            if "brevo" not in smtp:
                continue
            accounts = val.get("accounts", [])
            primary_email = accounts[0]["email"] if accounts else ""
            result.append({
                "id": key,
                "name": val.get("name", key),
                "email": primary_email,
                "account_count": len(accounts),
            })
        return result

    def get_all_publisher_options(self) -> list:
        """Return all publishers regardless of SMTP server."""
        result = []
        for key, val in self.credentials.items():
            accounts = val.get("accounts", [])
            primary_email = accounts[0]["email"] if accounts else ""
            result.append({
                "id": key,
                "name": val.get("name", key),
                "email": primary_email,
                "account_count": len(accounts),
            })
        return result

    def get_publisher_name(self, publisher_id: str) -> str:
        if publisher_id in self.credentials:
            return self.credentials[publisher_id].get("name", "")
        return ""

    def get_publisher_email(self, publisher_id: str) -> str:
        if publisher_id in self.credentials:
            accounts = self.credentials[publisher_id].get("accounts", [])
            if accounts:
                return accounts[0]["email"]
        return ""

    def send_email(
        self,
        publisher_id: str,
        to_email: str,
        subject: str,
        body: str,
        to_name: Optional[str] = None,
        pdf_attachment: Optional[bytes] = None,
        attachment_filename: str = "Invitation_Letter.pdf",
    ) -> Tuple[bool, str]:
        if publisher_id not in self.credentials:
            return False, f"Unknown publisher: {publisher_id}"
        if not to_email or "@" not in to_email:
            return False, f"Invalid recipient email: '{to_email}'"

        pub_config = self.credentials[publisher_id]
        accounts = pub_config.get("accounts", [])
        if not accounts:
            return False, "No email accounts configured for this publisher"

        account = accounts[0]
        sender_email = account.get("email", "")
        sender_password = account.get("password", "")
        login_user = account.get("smtp_login") or sender_email

        if not sender_email or "@" not in sender_email:
            return False, "Invalid sender email in account"

        try:
            if pdf_attachment:
                message = MIMEMultipart("mixed")
            else:
                message = MIMEMultipart("alternative")

            message["Subject"] = subject
            message["From"] = formataddr((pub_config.get("name", ""), sender_email))

            if to_name:
                safe_name = "".join(c for c in to_name if c.isalnum() or c in " .-")
                message["To"] = formataddr((safe_name, to_email))
            else:
                message["To"] = to_email

            body_part = MIMEMultipart("alternative")
            text_part = MIMEText(body, "plain", "utf-8")
            body_part.attach(text_part)
            html_body = self._text_to_html(body)
            html_part = MIMEText(html_body, "html", "utf-8")
            body_part.attach(html_part)

            if pdf_attachment:
                message.attach(body_part)
                pdf_part = MIMEBase("application", "pdf")
                pdf_part.set_payload(pdf_attachment)
                encoders.encode_base64(pdf_part)
                pdf_part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={attachment_filename}",
                )
                message.attach(pdf_part)
            else:
                message.attach(text_part)
                message.attach(html_part)

            context = ssl.create_default_context()

            if pub_config.get("use_ssl", True):
                with smtplib.SMTP_SSL(
                    pub_config["smtp_server"],
                    pub_config.get("smtp_port", 465),
                    context=context,
                ) as server:
                    server.login(login_user, sender_password)
                    server.sendmail(sender_email, to_email, message.as_string())
            else:
                with smtplib.SMTP(
                    pub_config["smtp_server"],
                    pub_config.get("smtp_port", 587),
                ) as server:
                    server.starttls(context=context)
                    server.login(login_user, sender_password)
                    server.sendmail(sender_email, to_email, message.as_string())

            info = " with PDF attachment" if pdf_attachment else ""
            return True, f"Email sent from {sender_email}{info}"

        except smtplib.SMTPAuthenticationError:
            return False, f"Authentication failed for {sender_email}. Check credentials."
        except smtplib.SMTPRecipientsRefused:
            return False, f"Recipient refused: {to_email}"
        except smtplib.SMTPException as e:
            return False, f"SMTP error: {str(e)}"
        except Exception as e:
            return False, f"Error sending email: {str(e)}"

    def _text_to_html(self, text: str) -> str:
        html = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = html.replace("\n\n", "</p><p>").replace("\n", "<br>")
        return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>body{{font-family:'Georgia','Times New Roman',serif;font-size:14px;
line-height:1.6;color:#333;max-width:600px;margin:0 auto;padding:20px}}
p{{margin-bottom:16px}}</style></head><body><p>{html}</p></body></html>"""

    def test_connection(self, publisher_id: str) -> Tuple[bool, str]:
        if publisher_id not in self.credentials:
            return False, f"Unknown publisher: {publisher_id}"

        pub_config = self.credentials[publisher_id]
        accounts = pub_config.get("accounts", [])
        if not accounts:
            return False, "No accounts configured"

        account = accounts[0]
        login_user = account.get("smtp_login") or account.get("email", "")

        try:
            context = ssl.create_default_context()
            if pub_config.get("use_ssl", True):
                with smtplib.SMTP_SSL(
                    pub_config["smtp_server"],
                    pub_config.get("smtp_port", 465),
                    context=context,
                    timeout=10,
                ) as server:
                    server.login(login_user, account.get("password", ""))
                    return True, "Connection successful!"
            else:
                with smtplib.SMTP(
                    pub_config["smtp_server"],
                    pub_config.get("smtp_port", 587),
                    timeout=10,
                ) as server:
                    server.starttls(context=context)
                    server.login(login_user, account.get("password", ""))
                    return True, "Connection successful!"
        except smtplib.SMTPAuthenticationError:
            return False, f"Authentication failed for {login_user}."
        except smtplib.SMTPException as e:
            return False, f"SMTP error: {str(e)}"
        except Exception as e:
            return False, f"Connection error: {str(e)}"
