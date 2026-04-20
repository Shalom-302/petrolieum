# Messaging Service for KAAPI

This plugin provides a comprehensive messaging service for the KAAPI application, allowing users to communicate via direct messages and group conversations.

## Features

- **Direct Messages**: Private communication between two users.
- **Group Conversations**: Discussions with multiple participants.
- **Message Encryption**: Protection of messages with end-to-end encryption.
- **Attachments**: Ability to share files and media.
- **Real-time Notifications**: Instant alerts for new messages.
- **WebSocket Communication**: Real-time messaging via WebSockets.
- **Message Statuses**: Delivery and read confirmations.
- **Typing Indicators**: Visualization when someone is typing.
- **User Blocking**: Control of unwanted interactions.
- **Customization**: Options to personalize appearance and notifications.

## Architecture

The service uses a modular architecture including:

1. **Schemas** (`/schemas`): Data validation and serialization with Pydantic.
2. **Services** (`/services`): Core business logic.
3. **Routes** (`/routes`): API endpoints for the application.
4. **Utilities** (`/utils`): Helper functions for security, notifications, etc.
5. **Tasks** (`/tasks`): Scheduled and background tasks.

## Standardized Security

The messaging service implements a standardized security approach across all its components:

- **Consistent Encryption**: Consistent use of the central encryption handler.
- **Secure Logging**: Use of standardized logging techniques that protect sensitive information.
- **Protected Metadata**: Encryption of sensitive metadata before storage.
- **Request Validation**: Systematic verification of user inputs.
- **Access Rights Management**: Consistent verification of access permissions.

This approach ensures that all components of the messaging service benefit from the same level of protection, regardless of their specific function.

## API Endpoints

### Messages

- `POST /messaging/messages`: Create a new message
- `GET /messaging/messages/{message_id}`: Retrieve a message
- `PATCH /messaging/messages/{message_id}`: Modify a message
- `POST /messaging/messages/bulk`: Retrieve multiple messages
- `POST /messaging/messages/search`: Search for messages
- `POST /messaging/messages/forward`: Forward a message
- `POST /messaging/messages/status`: Update message status
- `POST /messaging/messages/delete-bulk`: Delete multiple messages
- `GET /messaging/messages/typing/{conversation_id}`: Send a typing notification

### Conversations

- `POST /messaging/conversations/direct`: Create a direct conversation
- `POST /messaging/conversations/group`: Create a group conversation
- `GET /messaging/conversations`: Retrieve all conversations
- `GET /messaging/conversations/{conversation_id}`: Retrieve a conversation
- `PATCH /messaging/conversations/{conversation_id}`: Modify a conversation
- `PATCH /messaging/conversations/group/{conversation_id}`: Modify a group conversation
- `PATCH /messaging/conversations/{conversation_id}/settings`: Modify conversation settings
- `POST /messaging/conversations/{conversation_id}/members`: Add a member to a conversation
- `DELETE /messaging/conversations/{conversation_id}/members/{member_id}`: Remove a member from a conversation
- `DELETE /messaging/conversations/{conversation_id}`: Leave or delete a conversation

### User Blocking

- `POST /messaging/blocks`: Block a user
- `GET /messaging/blocks`: Retrieve blocked users
- `DELETE /messaging/blocks/{blocked_id}`: Unblock a user

### WebSocket

- `WebSocket /messaging/ws/{conversation_id}`: WebSocket entry point for a conversation

## Installation and Configuration

### Integration with the Main Application

1. Ensure the main application is properly configured with the required dependencies.
2. Import and initialize the messaging service in the main application file:

```python
from app.plugins.messaging_service.main import messaging_service

# In the application startup function
def start_app():
    app = FastAPI()
    
    # Initialize the messaging plugin
    messaging_service.init_app(app, encryption_handler=app.encryption_handler)
    
    # Other configurations...
    return app
```

### Custom Configuration

The messaging service offers several configuration options that you can customize according to your needs:

```python
# Example of custom configuration
custom_config = {
    "max_message_length": 10000,  # Maximum message length
    "max_file_size_mb": 50,       # Maximum file size (in MB)
    "message_retention_days": 180  # Message retention period
}

# Apply the configuration
messaging_service.update_config(custom_config)
```

## Database Models

The service uses the following models to store data:

- `ConversationDB`: Stores basic conversation information
- `GroupChatDB`: Stores settings specific to group conversations
- `UserConversationSettingsDB`: Stores user preferences for each conversation
- `MessageDB`: Stores messages
- `MessageAttachmentDB`: Stores message attachments
- `UserBlockDB`: Stores blocking relationships between users

## Testing and Development

To test the messaging service, you can use the provided test scripts or create your own tests.

```bash
# Example command to run tests
pytest -xvs app/plugins/messaging_service/tests/
```

## Security and Privacy

The messaging service takes security and user privacy seriously:

- Messages can be encrypted end-to-end
- Sensitive metadata is protected
- Rate limits are imposed to prevent abuse
- Files are scanned for malware
- Privacy settings allow users to control who can contact them

## Contributions and Support

To contribute to the development of the messaging service or report issues, please consult the contribution guide of the main KAAPI project.

For help or support, contact the KAAPI development team.
