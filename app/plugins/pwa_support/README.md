# PWA Support Plugin for Kaapi

This plugin adds Progressive Web App (PWA) capabilities to your Kaapi application, allowing users to install your app on their devices and access it offline.

## Features

- **Web App Manifest Management**: Dynamically generate and customize your app's manifest.json
- **Service Worker Management**: Configure caching strategies and offline capabilities
- **Push Notifications**: Send push notifications to users who have subscribed
- **Offline Support**: Provide fallback content when users are offline
- **Segmented Notifications**: Target specific user groups with tailored notifications

## Installation

This plugin is included with Kaapi by default. To activate it, go to the Admin dashboard at `/admin/plugins` and ensure the "pwa_support" plugin is enabled.

## Usage

### 1. Web App Manifest

The manifest.json file is automatically served at `/manifest.json`. You can customize it through the admin interface at `/admin/pwa/manifest`.

Include this in your HTML `<head>` section:

```html
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#4F46E5">
```

### 2. Service Worker

The service worker is automatically generated and served at `/service-worker.js`. Include this script in your main layout to register it:

```html
<script src="/pwa-register.js"></script>
```

You can customize the service worker's caching behavior through the admin interface at `/admin/pwa/service-worker`.

### 3. Offline Support

An offline fallback page is automatically served at `/offline.html` when users are offline. You can customize this page through the admin interface.

### 4. Push Notifications

To send push notifications:

```python
from app.plugins.pwa_support.push_service import send_push_notification

# In your route handler
@app.post("/send-notification")
async def send_notification(db: Session = Depends(get_db)):
    sent_count = send_push_notification(
        db,
        title="New Feature!",
        message="Check out our latest update",
        icon="/static/icons/icon-192x192.png",
        url="/feature"
    )
    return {"success": True, "sent_count": sent_count}
```

Or use the admin interface at `/admin/push/send`.

### 5. Segmented Notifications

The plugin offers a powerful segmented notifications system that allows you to target specific groups of users:

```python
from app.plugins.pwa_support.push_service import send_segmented_notification
from app.plugins.pwa_support.schemas import SegmentedNotificationSend

# In your route handler
@app.post("/send-segmented-notification")
async def send_to_segment(db: Session = Depends(get_db)):
    notification = SegmentedNotificationSend(
        title="Special Offer",
        message="Check out our latest products!",
        icon="/static/icons/icon-192x192.png",
        segment_id=1,  # ID of the target segment
        data={"url": "/promotions"}
    )
    
    sent_count = send_segmented_notification(db, notification)
    return {"success": True, "sent_count": sent_count}
```

#### Key Segmentation Features

&#10004; **Fully functional API endpoints** for creating, reading, updating, and deleting notification segments  
&#10004; **Dynamic segment population** based on user-defined criteria  
&#10004; **Subscription management** for assigning and removing subscriptions from segments  
&#10004; **Targeted notification delivery** to specific user segments  
&#10004; **Notification history tracking** for monitoring campaign performance  
&#10004; **Modern UI elements** with glassmorphism, gradient backgrounds, and geometric shapes  
&#10004; **Comprehensive testing documentation**

#### Segmentation API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/pwa/segments` | Create a new notification segment |
| GET | `/pwa/segments` | List all notification segments |
| GET | `/pwa/segments/{segment_id}` | Get a specific segment's details |
| PUT | `/pwa/segments/{segment_id}` | Update a segment's properties |
| DELETE | `/pwa/segments/{segment_id}` | Delete a notification segment |
| POST | `/pwa/segments/{segment_id}/assign` | Assign subscriptions to a segment |
| POST | `/pwa/segments/{segment_id}/remove` | Remove subscriptions from a segment |
| POST | `/pwa/segments/{segment_id}/populate` | Repopulate a dynamic segment based on criteria |
| POST | `/pwa/send-to-segment` | Send a notification to a specific segment |
| GET | `/pwa/notification-history` | View notification sending history |
| GET | `/pwa/statistics` | Get notification delivery statistics |

For detailed testing instructions, refer to the `TESTING.md` file included with this plugin.

## Requirements

This plugin requires the following packages:

- pywebpush
- py-vapid (optional, for generating VAPID keys)

Add these to your requirements.txt:

```
pywebpush>=1.12.0
py-vapid>=1.8.2
```

## Configuration

The plugin stores its configuration in the database using the `PWASettings`, `PushSubscription`, `NotificationSegment`, and `NotificationHistory` models.

### Default Icons

You should create and place PWA icons in your static folder:

- `/static/icons/icon-192x192.png`
- `/static/icons/icon-512x512.png`
- `/static/icons/icon-maskable-192x192.png` (optional, for adaptive icons)
- `/static/icons/icon-maskable-512x512.png` (optional, for adaptive icons)

## Additional Resources

- [Web App Manifest Documentation](https://developer.mozilla.org/en-US/docs/Web/Manifest)
- [Service Workers API Documentation](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
- [Push API Documentation](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)
