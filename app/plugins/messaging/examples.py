"""
Examples of using the messaging plugin with different providers and message types.
"""

from typing import List
from . import Message, MessageRecipient, EmailTemplate, MessageType
from .factory import MessagingProviderFactory
from app.core.config import settings

class MessagingExamples:
    def __init__(self):
        # Initialize providers with credentials
        self.gmail_provider = MessagingProviderFactory.create_provider(
            "gmail",
            username=settings.GMAIL_USERNAME,
            password=settings.GMAIL_PASSWORD
        )
        
        self.sendgrid_provider = MessagingProviderFactory.create_provider(
            "sendgrid",
            api_key=settings.SENDGRID_API_KEY
        )
        
        self.infobip_provider = MessagingProviderFactory.create_provider(
            "infobip",
            api_key=settings.INFOBIP_API_KEY,
            base_url=settings.INFOBIP_BASE_URL,
            from_number=settings.INFOBIP_FROM_NUMBER
        )
        
        self.twilio_provider = MessagingProviderFactory.create_provider(
            "twilio",
            account_sid=settings.TWILIO_ACCOUNT_SID,
            auth_token=settings.TWILIO_AUTH_TOKEN,
            from_number=settings.TWILIO_FROM_NUMBER
        )
        
        self.push_provider = MessagingProviderFactory.create_provider(
            "onesignal",
            app_id=settings.ONESIGNAL_APP_ID,
            rest_api_key=settings.ONESIGNAL_REST_API_KEY
        )

    def send_welcome_email(self, user_data: dict) -> bool:
        """
        Send a welcome email using HTML template and dynamic data.
        """
        # Create template with user data
        template = EmailTemplate(
            template_path="templates/welcome.html",
            template_data={
                "user_name": user_data["name"],
                "username": user_data["username"],
                "email": user_data["email"],
                "company_name": "Kaapi",
                "account_type": user_data["account_type"],
                "activation_link": f"https://kaapi.io/activate/{user_data['activation_token']}",
                "expiry_hours": 24
            },
            subject_template="Welcome to Kaapi, {{ user_name }}!"
        )

        # Create message with template
        message = Message(
            recipients=[
                MessageRecipient(
                    address=user_data["email"],
                    name=user_data["name"]
                )
            ],
            template=template,
            content_type="text/html"
        )

        # Send using SendGrid (or fallback to Gmail)
        try:
            return self.sendgrid_provider.send_message(message)
        except Exception as e:
            print(f"SendGrid failed, falling back to Gmail: {str(e)}")
            return self.gmail_provider.send_message(message)

    def send_push_notification(self, users: List[dict], notification: dict) -> bool:
        """
        Send push notification using OneSignal.
        """
        message = Message(
            subject=notification["title"],
            body=notification["message"],
            recipients=[
                MessageRecipient(address=user["device_id"])
                for user in users
            ],
            metadata={
                "type": notification["type"],
                "action": notification.get("action"),
                "data": notification.get("extra_data", {})
            }
        )

        return self.push_provider.send_message(message)

    def send_sms_verification(self, phone_number: str, code: str) -> bool:
        """
        Send SMS verification code using preferred provider (InfoBip with Twilio fallback).
        """
        message = Message(
            body=f"Your Kaapi verification code is: {code}. Valid for 5 minutes.",
            recipients=[MessageRecipient(address=phone_number)]
        )

        # Try InfoBip first, fallback to Twilio if needed
        try:
            return self.infobip_provider.send_message(message)
        except Exception as e:
            print(f"InfoBip failed, falling back to Twilio: {str(e)}")
            return self.twilio_provider.send_message(message)

    def send_marketing_campaign(self, campaign: dict) -> dict:
        """
        Send a marketing campaign using multiple channels.
        """
        results = {
            "email": False,
            "sms": False,
            "push": False
        }

        # 1. Send HTML email newsletter
        if campaign.get("email_recipients"):
            template = EmailTemplate(
                template_path=campaign["email_template"],
                template_data=campaign["template_data"],
                subject_template=campaign["email_subject"]
            )
            
            message = Message(
                recipients=[
                    MessageRecipient(address=email, name=name)
                    for email, name in campaign["email_recipients"]
                ],
                template=template,
                content_type="text/html"
            )
            
            results["email"] = self.sendgrid_provider.send_message(message)

        # 2. Send SMS notification using InfoBip
        if campaign.get("sms_recipients"):
            message = Message(
                body=campaign["sms_content"],
                recipients=[
                    MessageRecipient(address=phone)
                    for phone in campaign["sms_recipients"]
                ]
            )
            
            results["sms"] = self.infobip_provider.send_message(message)

        # 3. Send push notification
        if campaign.get("push_recipients"):
            message = Message(
                subject=campaign["push_title"],
                body=campaign["push_content"],
                recipients=[
                    MessageRecipient(address=device_id)
                    for device_id in campaign["push_recipients"]
                ],
                metadata=campaign.get("push_data", {})
            )
            
            results["push"] = self.push_provider.send_message(message)

        return results


# Example usage:
def main():
    # Set up environment variables first
    os.environ.update({
        "GMAIL_USERNAME": "your.email@gmail.com",
        "GMAIL_PASSWORD": "your-app-specific-password",
        "SENDGRID_API_KEY": "your-sendgrid-api-key",
        "INFOBIP_API_KEY": "your-infobip-api-key",
        "INFOBIP_BASE_URL": "https://api.infobip.com",
        "INFOBIP_FROM_NUMBER": "+1234567890",
        "TWILIO_ACCOUNT_SID": "your-twilio-account-sid",
        "TWILIO_AUTH_TOKEN": "your-twilio-auth-token",
        "TWILIO_FROM_NUMBER": "+1234567890",
        "ONESIGNAL_APP_ID": "your-onesignal-app-id",
        "ONESIGNAL_REST_API_KEY": "your-onesignal-rest-api-key"
    })

    # Create messaging example instance
    messaging = MessagingExamples()

    # 1. Send welcome email
    user_data = {
        "name": "John Doe",
        "username": "johndoe",
        "email": "john@example.com",
        "account_type": "Premium",
        "activation_token": "abc123xyz789"
    }
    success = messaging.send_welcome_email(user_data)
    print(f"Welcome email sent: {success}")

    # 2. Send verification SMS
    success = messaging.send_sms_verification("+33612345678", "123456")
    print(f"Verification SMS sent: {success}")

    # 3. Send push notification to multiple users
    users = [
        {"device_id": "user1-device-id"},
        {"device_id": "user2-device-id"}
    ]
    notification = {
        "title": "New Feature Available",
        "message": "Check out our new AI-powered recommendations!",
        "type": "feature_announcement",
        "action": "open_recommendations",
        "extra_data": {"feature_id": "ai_recommendations"}
    }
    success = messaging.send_push_notification(users, notification)
    print(f"Push notification sent: {success}")

    # 4. Send marketing campaign
    campaign = {
        "email_recipients": [
            ("user1@example.com", "User One"),
            ("user2@example.com", "User Two")
        ],
        "email_template": "templates/newsletter.html",
        "email_subject": "{{ user_name }}, check out our latest offers!",
        "template_data": {
            "offers": ["Offer 1", "Offer 2"],
            "valid_until": "2025-03-01"
        },
        
        "sms_recipients": ["+33612345678", "+33687654321"],
        "sms_content": "Limited time offer: Use code KAAPI25 for 25% off!",
        
        "push_recipients": ["device-id-1", "device-id-2"],
        "push_title": "Special Offer",
        "push_content": "25% off all products today!",
        "push_data": {
            "offer_code": "KAAPI25",
            "valid_until": "2025-03-01"
        }
    }
    results = messaging.send_marketing_campaign(campaign)
    print("Marketing campaign results:", results)


if __name__ == "__main__":
    main()
