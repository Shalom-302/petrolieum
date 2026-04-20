# Push Notifications Plugin for KAAPI

The Push Notifications Plugin provides a complete solution for sending real-time notifications to users through various push notification services, including Firebase Cloud Messaging (FCM), Apple Push Notification service (APNs), and Web Push.

## Features

- Multi-provider support (FCM, APNs, Web Push)
- Device registration and management
- Template-based notifications
- Scheduled and recurring notifications
- Notification history and tracking
- Batched delivery for high throughput
- Delivery status tracking
- Analytics and metrics
- Localization support
- A/B testing capabilities
- Rate limiting and throttling
- Fallback mechanisms
- User segmentation for targeted notifications

## Architecture

The Push Notifications Plugin follows a high-performance, modular architecture:

1. **Core Components**:
   - Provider abstraction layer
   - Device registration service
   - Notification dispatch service
   - Template management
   - Notification history and tracking
   - Analytics service
   - Segmentation service

2. **Performance Considerations**:
   - Message queue integration with RabbitMQ for asynchronous processing
   - Redis for caching frequently accessed data and rate limiting
   - Batched sending for optimal API usage
   - Retry logic with exponential backoff

3. **Security**:
   - Encryption of sensitive metadata
   - Secure credential storage
   - Comprehensive transaction logging
   - Payload validation
   - Secure transmission and storage of device tokens

## Installation

The Push Notifications Plugin is installed as part of the KAAPI application. Make sure your environment includes RabbitMQ and Redis for optimal performance.

## Configuration

Configure the plugin in your environment variables or `app/core/config.py`:

```python
# Push Notification Settings
PUSH_NOTIFICATION_ENABLED=True
FCM_API_KEY=your_fcm_api_key
APNS_KEY_ID=your_apns_key_id
APNS_TEAM_ID=your_apns_team_id
APNS_BUNDLE_ID=your.app.bundle.id
APNS_KEY_FILE=/path/to/AuthKey_KEYID.p8
VAPID_PRIVATE_KEY=your_vapid_private_key
VAPID_PUBLIC_KEY=your_vapid_public_key
VAPID_CLAIMS_EMAIL=mailto:your-email@example.com
PWA_SUPPORT_ENABLED=true  # Enable integration with PWA support module
```

## Provider Integration

This plugin supports multiple providers for maximum reach:

- **Firebase Cloud Messaging (FCM)**: For Android devices and web applications
- **Apple Push Notification service (APNs)**: For iOS and macOS devices
- **Web Push**: For web browser notifications (Chrome, Firefox, Edge, etc.)

## Usage

### Basic Notifications

```python
from app.plugins.push_notifications import push_notifications_service

# Register a device
device_id = push_notifications_service.register_device(
    user_id="user123",
    device_token="fcm_device_token",
    platform="android",
    app_version="1.0.0"
)

# Send a notification
notification_id = push_notifications_service.send_notification(
    user_ids=["user123"],
    title="New Message",
    body="You've received a new message from John Doe",
    data={"message_id": "msg456", "sender_id": "user789"},
    high_priority=True
)

# Use notification templates
notification_id = push_notifications_service.send_template_notification(
    user_ids=["user123"],
    template_id="new_message",
    template_data={
        "sender_name": "John Doe",
        "message_preview": "Hello, how are you?"
    }
)

# Schedule a notification
scheduled_id = push_notifications_service.schedule_notification(
    user_ids=["user123"],
    title="Reminder",
    body="Don't forget your appointment tomorrow!",
    scheduled_time=datetime.now() + timedelta(days=1)
)
```

### Segmentation Features

```python
from app.plugins.push_notifications.services import segment_service, segmented_notification_service

# Create a segment
segment_id = segment_service.create_segment(
    db=db_session,
    name="Premium Users",
    description="Users with active premium subscription",
    criteria={"subscription_type": "premium", "is_active": True},
    is_dynamic=True
)

# Send notification to a segment
result = segmented_notification_service.send_notification_to_segment(
    db=db_session,
    segment_id=segment_id,
    title="Premium Feature Update",
    body="We've just added new exclusive features for our premium users!",
    data={"feature_id": "new_feature_123"},
    high_priority=True
)

# Create a static segment and manually assign devices
static_segment_id = segment_service.create_segment(
    db=db_session,
    name="Beta Testers",
    description="Users participating in beta testing program",
    is_dynamic=False
)

# Add devices to segment
segment_service.add_device_to_segment(db=db_session, segment_id=static_segment_id, device_id=device_id)

# Get all segments
segments = segment_service.get_segments(db=db_session)

# Get devices in a segment
devices = segment_service.get_segment_devices(db=db_session, segment_id=segment_id)
```

## Analytics

The plugin tracks key metrics to help you optimize your notification strategy:

- Delivery rates
- Open rates
- Conversion rates
- Best times to send
- User engagement patterns
- Segment performance metrics

## Extending the Plugin

You can extend the plugin by adding new providers or custom notification types. Follow the provider interface to ensure compatibility with the existing system.

## Security Approach

This plugin follows KAAPI's standardized security approach:
- Validation of notification requests
- Encryption of sensitive metadata
- Comprehensive transaction logging
- Standardized configuration and initialization
- Secure handling of segmentation data
