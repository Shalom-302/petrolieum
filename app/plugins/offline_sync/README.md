# Offline Synchronization Plugin

## Overview

The Offline Synchronization Plugin provides robust capabilities for queuing operations when offline and synchronizing them when connectivity is restored. This plugin enables applications to maintain functionality even when users don't have an active internet connection, enhancing user experience and application resilience.

## Features

- **Operation Queueing**: Automatically queue operations when offline
- **Prioritized Synchronization**: Process operations based on configurable priorities (Critical, High, Normal, Low)
- **Batch Operations**: Group related operations for atomic processing
- **Conflict Resolution**: Configurable strategies for handling synchronization conflicts
- **Secure Data Storage**: Encryption of sensitive operation data
- **Advanced Retry Logic**: Configurable retry attempts with exponential backoff
- **User Configuration**: Per-user synchronization preferences
- **Background Processing**: Non-blocking synchronization in the background
- **Comprehensive Logging**: Detailed audit trail of all synchronization activities

## Installation

This plugin is automatically included with the Kaapi framework. No additional installation is required.

## Dependencies

- FastAPI
- SQLAlchemy
- Pydantic
- Cryptography

## Plugin Configuration

The plugin can be configured through the application's settings:

```python
# Default settings in app/core/config.py
OFFLINE_SYNC_AUTO_ENABLED = True
OFFLINE_SYNC_INTERVAL = 15  # minutes
OFFLINE_SYNC_MAX_STORAGE = 100  # MB
```

## Database Models

The plugin uses three primary database models:

### SyncOperationDB

Stores individual operations to be synchronized:

- `id`: Unique identifier
- `user_id`: Associated user
- `endpoint`: API endpoint for the operation
- `method`: HTTP method (GET, POST, PUT, DELETE)
- `payload`: Request payload data
- `headers`: Request headers
- `query_params`: URL query parameters
- `status`: Current status (PENDING, IN_PROGRESS, SUCCEEDED, FAILED, CONFLICT)
- `priority`: Operation priority (CRITICAL, HIGH, NORMAL, LOW)
- `retry_count`: Number of retry attempts
- `max_retries`: Maximum retry attempts allowed
- `last_error`: Last error message
- `batch_id`: Associated batch (optional)
- `is_encrypted`: Whether payload is encrypted
- `encryption_metadata`: Metadata for encryption
- `response_status`: HTTP status from response
- `response_data`: Data returned from response

### SyncBatchDB

Groups related operations:

- `id`: Unique identifier
- `user_id`: Associated user
- `name`: Batch name
- `description`: Batch description
- `status`: Current status
- `priority`: Batch priority

### SyncConfigDB

Stores user synchronization preferences:

- `id`: Unique identifier
- `user_id`: Associated user
- `auto_sync_enabled`: Whether automatic sync is enabled
- `sync_on_connectivity`: Whether to sync when connectivity is restored
- `sync_interval_minutes`: Interval between sync attempts
- `max_offline_storage_mb`: Maximum local storage
- `conflict_resolution_strategy`: How to resolve conflicts
- `prioritize_by_endpoint`: Custom endpoint priorities

## API Endpoints

### Operations

- `POST /sync/operations`: Create a new sync operation
- `GET /sync/operations`: List sync operations
- `GET /sync/operations/{operation_id}`: Get a specific operation
- `PUT /sync/operations/{operation_id}`: Update an operation
- `DELETE /sync/operations/{operation_id}`: Delete an operation
- `POST /sync/operations/{operation_id}/sync`: Manually trigger synchronization

### Batches

- `POST /sync/batches`: Create a new batch
- `GET /sync/batches`: List batches
- `GET /sync/batches/{batch_id}`: Get a specific batch
- `PUT /sync/batches/{batch_id}`: Update a batch
- `DELETE /sync/batches/{batch_id}`: Delete a batch
- `POST /sync/batches/{batch_id}/sync`: Sync all operations in a batch

### Configuration

- `POST /sync/config`: Create user sync configuration
- `GET /sync/config`: Get user sync configuration
- `PUT /sync/config`: Update user sync configuration

## Usage Examples

### Queue an Operation for Later Synchronization

```python
from app.plugins.offline_sync.main import plugin as offline_sync

# Queue a create operation
await offline_sync.enqueue_operation(
    endpoint="/apitasks",
    method="POST",
    payload={"title": "New Task", "description": "Task details"},
    user_id="user123",
    priority="HIGH"
)
```

### Create a Batch and Add Operations

```python
# Create a batch
from app.plugins.offline_sync.schemas.sync_batch import SyncBatchCreate
from app.plugins.offline_sync.models.base import SyncPriority

batch = SyncBatchCreate(
    name="User Profile Update",
    description="Update user profile data",
    priority=SyncPriority.HIGH
)

# Use your application's dependency injection to get these
db = next(get_db())
current_user = await get_current_active_user(...)

# Create the batch via API
batch_router = get_batches_router()
batch_response = await batch_router.create_sync_batch(
    batch=batch, 
    db=db, 
    current_user=current_user
)

# Queue operations with the batch ID
batch_id = batch_response.id
await offline_sync.enqueue_operation(
    endpoint="/apiusers/profile",
    method="PUT",
    payload={"name": "Updated Name"},
    user_id=current_user.id,
    batch_id=batch_id
)
```

### Trigger Synchronization

```python
from fastapi import BackgroundTasks

background_tasks = BackgroundTasks()
await offline_sync.trigger_sync(
    background_tasks=background_tasks,
    user_id="user123"
)
```

## Security Considerations

The plugin implements several security features:

1. **Payload Encryption**: Sensitive data is automatically encrypted using Fernet symmetric encryption
2. **Data Integrity**: HMAC signatures verify data hasn't been tampered with
3. **Input Validation**: All inputs are validated to prevent injection attacks
4. **Audit Logging**: Comprehensive logging for all operations
5. **Authentication**: All endpoints require user authentication
6. **Authorization**: Operations are scoped to the user who created them

## Best Practices

1. **Prioritize Critical Operations**: Use the priority system to ensure critical operations sync first
2. **Group Related Operations**: Use batches to ensure related operations succeed or fail together
3. **Handle Conflicts**: Implement client-side conflict resolution for key data
4. **Clean Up**: Periodically clean up successful operations to reduce storage requirements
5. **Monitor Storage**: Check `max_offline_storage_mb` to prevent excessive local storage usage

## Contributing

To extend or modify this plugin:

1. Follow the Kaapi plugin architecture guidelines
2. Ensure comprehensive test coverage for new features
3. Maintain the established security patterns
4. Document API changes in this README

## License

This plugin is part of the Kaapi framework and is licensed under the same terms as the main project.
