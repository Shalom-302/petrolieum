# Social Subscriptions Plugin

## Overview

The Social Subscriptions plugin provides a comprehensive solution for implementing social networking features within your application. It enables users to subscribe to other users, receive notifications about their activities, and maintain personalized activity feeds.

## Key Features

- **User Subscriptions**: Subscribe to users with customizable categories
- **Activity Tracking**: Track user activities across different types and resources
- **Personalized Feeds**: Generate personalized activity feeds for users
- **Notifications**: Integrate with push notifications for real-time alerts
- **Security**: Robust security with encryption, validation, and comprehensive logging

## Components

### Models

- `Subscription`: Manages user subscription relationships with categories and preferences
- `ActivityEvent`: Records user activities with type, metadata, and resource information
- `FeedItem`: Stores feed items for each user with read status and visibility settings
- `NotificationRecord`: Tracks notification delivery and read status for activities
- `UserPreference`: Stores user preferences for notifications and feeds

### Services

- `SubscriptionService`: Manages user subscriptions
- `ActivityService`: Handles activity creation and retrieval
- `FeedService`: Generates and manages user activity feeds
- `NotificationService`: Processes notifications for activities

### Routes

- `/social/subscriptions/*`: Endpoints for managing subscriptions
- `/social/feed/*`: Endpoints for retrieving and managing activity feeds

## Security Implementation

Security is a core focus of this plugin, built around these key principles:

### 1. Encryption and Data Protection

- Sensitive metadata is encrypted using cryptographic standards
- Subscription metadata is protected with encryption
- Activity payload data is secured through encryption

### 2. Request Validation

- All incoming requests are validated against schema definitions
- Rate limiting and subscription limits are enforced
- Resource ownership verification for all operations

### 3. Comprehensive Logging

- Detailed audit logs for all subscription events
- Activity tracking with timestamps and user information
- Notification delivery status logging

### 4. Standardized Security Patterns

- Consistent security approach across all services
- Follows the same security principles used in payment providers
- Common encryption and validation methods

## Installation

The plugin is automatically included in the application structure. To enable it:

1. Make sure the plugin directory exists at `app/plugins/social_subscriptions`
2. Update your main application file to include the plugin:

```python
from app.plugins.social_subscriptions.main import setup_social_subscriptions

# In your app initialization
setup_social_subscriptions(app)
```

## Usage Examples

### Subscribe to a User

```python
# Create a subscription
subscription = await social_subscriptions_plugin.create_standard_subscription(
    db, 
    subscriber_id="user123", 
    publisher_id="user456", 
    categories=["post", "comment", "update"]
)
```

### Create an Activity

```python
# Record a user activity
activity = await social_subscriptions_plugin.create_standard_activity(
    db,
    publisher_id="user456",
    activity_type="post",
    resource_type="blog",
    resource_id="post123",
    title="New blog post",
    description="I just published a new blog post about coding"
)

# Process the activity for feeds and notifications
await social_subscriptions_plugin.process_activity(db, activity.id)
```

### Get User Feed

```python
# Retrieve a user's activity feed
feed_items = await social_subscriptions_plugin.get_user_feed(
    db, 
    user_id="user123", 
    skip=0, 
    limit=20
)
```

## Best Practices

1. Process activities in background tasks to avoid blocking the main request flow
2. Regularly clean up old feed items to maintain database performance
3. Respect user notification preferences, especially quiet hours
4. Use appropriate subscription categories to give users control over what they receive
5. Always validate subscription relationships before sending sensitive information
