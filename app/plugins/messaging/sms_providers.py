"""
SMS providers implementation for the messaging plugin.
"""

import re
from twilio.rest import Client as TwilioClient
from infobip_api_client.api_client import ApiClient, Configuration
from infobip_api_client.model.sms_advanced_textual_request import SmsAdvancedTextualRequest
from infobip_api_client.model.sms_destination import SmsDestination
from infobip_api_client.model.sms_textual_message import SmsTextualMessage
from infobip_api_client.api.send_sms_api import SendSmsApi

from . import MessagingProvider, Message, MessageType

class TwilioProvider(MessagingProvider):
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self._client = TwilioClient(account_sid, auth_token)
        self._from_number = from_number

    def send_message(self, message: Message) -> bool:
        try:
            for recipient in message.recipients:
                self._client.messages.create(
                    body=message.body,
                    from_=self._from_number,
                    to=recipient.address
                )
            return True
        except Exception as e:
            print(f"Error sending SMS via Twilio: {str(e)}")
            return False

    def validate_message(self, message: Message) -> bool:
        phone_pattern = re.compile(r'^\+?1?\d{9,15}$')
        return all(
            phone_pattern.match(recipient.address) for recipient in message.recipients
        )

    @property
    def provider_name(self) -> str:
        return "Twilio"

    @property
    def message_type(self) -> MessageType:
        return MessageType.SMS

class InfoBipProvider(MessagingProvider):
    def __init__(self, api_key: str, base_url: str, from_number: str):
        configuration = Configuration(
            host=base_url,
            api_key={'APIKeyHeader': api_key}
        )
        api_client = ApiClient(configuration)
        self._client = SendSmsApi(api_client)
        self._from_number = from_number

    def send_message(self, message: Message) -> bool:
        try:
            # Create destinations for each recipient
            destinations = [
                SmsDestination(
                    to=recipient.address,
                    message_id=f"kaapi-{hash(recipient.address)}"
                )
                for recipient in message.recipients
            ]

            # Create the message request
            sms_message = SmsTextualMessage(
                destinations=destinations,
                _from=self._from_number,
                text=message.body
            )

            # Create the advanced request
            request = SmsAdvancedTextualRequest(
                messages=[sms_message],
                bulk_id=f"kaapi-bulk-{hash(message.body)}"
            )

            # Send the message
            response = self._client.send_sms_message(request)
            
            # Check if any messages were sent successfully
            if response.messages and any(msg.status.group_id == 1 for msg in response.messages):
                return True
            return False
            
        except Exception as e:
            print(f"Error sending SMS via InfoBip: {str(e)}")
            return False

    def validate_message(self, message: Message) -> bool:
        phone_pattern = re.compile(r'^\+?1?\d{9,15}$')
        return all(
            phone_pattern.match(recipient.address) for recipient in message.recipients
        )

    @property
    def provider_name(self) -> str:
        return "InfoBip"

    @property
    def message_type(self) -> MessageType:
        return MessageType.SMS
