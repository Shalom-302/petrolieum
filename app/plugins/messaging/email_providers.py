"""
Email providers implementation for the messaging plugin.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, HtmlContent

from . import MessagingProvider, Message, MessageType

class GmailProvider(MessagingProvider):
    def __init__(self, username: str, password: str):
        self._username = username
        self._password = password
        self._smtp_server = "smtp.gmail.com"
        self._smtp_port = 587

    def send_message(self, message: Message) -> bool:
        try:
            smtp = smtplib.SMTP(self._smtp_server, self._smtp_port)
            smtp.starttls()
            smtp.login(self._username, self._password)

            msg = MIMEMultipart('alternative')
            
            # Handle subject and sender
            if message.template:
                subject, body = message.template.render()
                msg["Subject"] = subject or message.subject
            else:
                msg["Subject"] = message.subject
                body = message.body
                
            msg["From"] = message.sender.address if message.sender else self._username
            msg["To"] = ", ".join(r.address for r in message.recipients)

            # Attach the content part
            content_type = message.content_type or "text/plain"
            msg.attach(MIMEText(body, 'html' if content_type == "text/html" else 'plain'))

            # Send the email
            smtp.send_message(msg)
            smtp.quit()
            return True
        except Exception as e:
            print(f"Error sending email via Gmail: {str(e)}")
            return False

    def validate_message(self, message: Message) -> bool:
        if not message.template and not (message.subject and message.body):
            return False
        return all(
            "@" in recipient.address for recipient in message.recipients
        )

    @property
    def provider_name(self) -> str:
        return "Gmail"

    @property
    def message_type(self) -> MessageType:
        return MessageType.EMAIL

class SendGridProvider(MessagingProvider):
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = SendGridAPIClient(api_key)

    def send_message(self, message: Message) -> bool:
        try:
            # Handle template rendering if present
            if message.template:
                subject, body = message.template.render()
                subject = subject or message.subject
            else:
                subject = message.subject
                body = message.body

            # Create the email
            mail = Mail(
                from_email=Email(message.sender.address if message.sender else "noreply@yourdomain.com"),
                subject=subject,
                to_emails=[To(r.address) for r in message.recipients]
            )

            # Add content based on type
            if message.content_type == "text/html":
                mail.content = [HtmlContent(body)]
            else:
                mail.content = [Content("text/plain", body)]

            # Add template data to personalization if present
            if message.template and message.template.template_data:
                for p in mail.personalizations:
                    p.dynamic_template_data = message.template.template_data

            response = self._client.send(mail)
            return 200 <= response.status_code < 300
        except Exception as e:
            print(f"Error sending email via SendGrid: {str(e)}")
            return False

    def validate_message(self, message: Message) -> bool:
        if not message.template and not (message.subject and message.body):
            return False
        return all(
            "@" in recipient.address for recipient in message.recipients
        )

    @property
    def provider_name(self) -> str:
        return "SendGrid"

    @property
    def message_type(self) -> MessageType:
        return MessageType.EMAIL
