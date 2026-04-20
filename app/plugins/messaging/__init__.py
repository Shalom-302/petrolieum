"""
Messaging plugin for sending messages via email and SMS using various providers.

from kaapi_cli.plugins.messaging import Message, MessageRecipient, EmailTemplate
from kaapi_cli.plugins.messaging.factory import MessagingProviderFactory

# Create HTML template with dynamic data
template = EmailTemplate(
    template_path="templates/welcome.html",
    template_data={
        "user_name": "John Doe",
        "activation_link": "https://example.com/activate/123",
        "company_name": "ACME Inc."
    },
    subject_template="Welcome to {{ company_name }}, {{ user_name }}!"
)

# Create message
message = Message(
    recipients=[MessageRecipient(address="john@example.com", name="John Doe")],
    template=template,
    content_type="text/html"
)

# Send message via Gmail
gmail_provider = MessagingProviderFactory.create_provider(
    "gmail",    
    username="your.email@gmail.com",
    password="your-app-specific-password"
)
success = gmail_provider.send_message(message)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from pathlib import Path
import jinja2

class MessageType(Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"

@dataclass
class MessageRecipient:
    address: str  # Email address or phone number
    name: Optional[str] = None

@dataclass
class EmailTemplate:
    """Class to handle email templates with dynamic data."""
    template_path: str
    template_data: Dict[str, Any]
    subject_template: Optional[str] = None

    def render(self, template_dir: Optional[str] = None) -> tuple[str, str]:
        """
        Render the template with the provided data.
        
        Args:
            template_dir: Optional directory containing the templates. If not provided,
                        template_path should be absolute.
        
        Returns:
            tuple[str, str]: Rendered subject and body
        """
        if template_dir:
            loader = jinja2.FileSystemLoader(template_dir)
        else:
            loader = jinja2.FileSystemLoader(str(Path(self.template_path).parent))
            
        env = jinja2.Environment(
            loader=loader,
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Render the body
        template = env.get_template(str(Path(self.template_path).name))
        body = template.render(**self.template_data)
        
        # Render the subject if a template is provided
        subject = self.subject_template
        if subject:
            subject_template = env.from_string(subject)
            subject = subject_template.render(**self.template_data)
            
        return subject, body

@dataclass
class Message:
    """
    Message class that supports both plain text and HTML templates.
    For HTML emails, either provide body or template, not both.
    """
    recipients: List[MessageRecipient]
    subject: Optional[str] = None
    body: Optional[str] = None
    template: Optional[EmailTemplate] = None
    sender: Optional[MessageRecipient] = None
    attachments: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    content_type: str = "text/plain"  # or "text/html" for HTML emails

class MessagingProvider(ABC):
    """Base class for all messaging providers."""
    
    @abstractmethod
    def send_message(self, message: Message) -> bool:
        """Send a message using the provider."""
        pass

    @abstractmethod
    def validate_message(self, message: Message) -> bool:
        """Validate if the message can be sent using this provider."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the name of the provider."""
        pass

    @property
    @abstractmethod
    def message_type(self) -> MessageType:
        """Get the type of messages this provider can handle."""
        pass
