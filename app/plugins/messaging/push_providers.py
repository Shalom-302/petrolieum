"""
Push notification providers implementation for the messaging plugin.
"""

from onesignal_sdk.client import Client as OneSignalClient
from onesignal_sdk.error import OneSignalHTTPError

from . import MessagingProvider, Message, MessageType

class OneSignalProvider(MessagingProvider):
    def __init__(self, app_id: str, rest_api_key: str):
        self._client = OneSignalClient(
            app_id=app_id,
            rest_api_key=rest_api_key
        )

    def send_message(self, message: Message) -> bool:
        try:
            # Create the notification body
            notification_body = {
                'contents': {'en': message.body},
                'headings': {'en': message.subject} if message.subject else None,
                'include_external_user_ids': [r.address for r in message.recipients],
                'channel_for_external_user_ids': 'push'
            }
            
            # Add additional data if present in the metadata
            if message.metadata:
                notification_body['data'] = message.metadata

            # Send the notification
            response = self._client.send_notification(notification_body)
            return response.status_code == 200
        except OneSignalHTTPError as e:
            print(f"Error sending notification via OneSignal: {str(e)}")
            return False
        except Exception as e:
            print(f"Unexpected error sending notification via OneSignal: {str(e)}")
            return False

    def validate_message(self, message: Message) -> bool:
        # OneSignal use the term external_user_ids for external_user_ids, so we just check
        # that each recipient has a non-empty address
        return all(
            bool(recipient.address and recipient.address.strip())
            for recipient in message.recipients
        )

    @property
    def provider_name(self) -> str:
        return "OneSignal"

    @property
    def message_type(self) -> MessageType:
        return MessageType.PUSH  # Changed from SMS to PUSH
