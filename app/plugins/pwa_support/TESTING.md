# Testing the Segmented Notifications System

This document provides instructions on how to test the PWA Support plugin's segmented notifications functionality once your Kaapi application is up and running.

## Prerequisites

1. A running Kaapi application with the PWA Support plugin installed
2. FastAPI dependencies installed (`pip install fastapi uvicorn pywebpush`)
3. A browser that supports Push Notifications (Chrome, Firefox, Edge)
4. Optional: A tool like Postman or cURL for making API requests

## Testing Plan

### 1. Setup Authentication

First, authenticate to get an access token:

```bash
# Replace with your actual authentication endpoint
curl -X POST "http://localhost:8000/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'
```

Save the token for subsequent requests.

### 2. Create a Notification Segment

```bash
curl -X POST "http://localhost:8000/pwa/segments" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Desktop English Users",
    "description": "Users with desktop devices and English language settings",
    "is_dynamic": true,
    "criteria": {
      "device_types": ["desktop"],
      "languages": ["en", "en-US", "en-GB"],
      "locations": [],
      "tags": []
    }
  }'
```

This will return the created segment with an ID.

### 3. List All Segments

```bash
curl -X GET "http://localhost:8000/pwa/segments" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4. Get a Specific Segment

```bash
# Replace SEGMENT_ID with the ID from step 2
curl -X GET "http://localhost:8000/pwa/segments/SEGMENT_ID" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 5. Update a Segment

```bash
# Replace SEGMENT_ID with the ID from step 2
curl -X PUT "http://localhost:8000/pwa/segments/SEGMENT_ID" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Desktop English Users - Updated",
    "description": "Updated description"
  }'
```

### 6. Populate a Dynamic Segment

For dynamic segments, you can trigger repopulation based on the criteria:

```bash
# Replace SEGMENT_ID with the ID from step 2
curl -X POST "http://localhost:8000/pwa/segments/SEGMENT_ID/populate" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 7. Register a Test Push Subscription

To test with an actual browser subscription:

1. Open your application in Chrome
2. Open the browser console (F12)
3. Navigate to the Application tab
4. Under "Service Workers", check if your service worker is active
5. Click "Push" in the sidebar and click "Subscribe"
6. Allow notifications when prompted

The subscription will be automatically sent to your backend via the `/pwa/push/subscribe` endpoint.

### 8. Manually Assign Subscriptions to a Segment

If you have subscription IDs, you can manually assign them:

```bash
# Replace SEGMENT_ID with the ID from step 2
curl -X POST "http://localhost:8000/pwa/segments/SEGMENT_ID/assign" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "subscription_ids": [1, 2, 3]
  }'
```

### 9. Send a Push Notification to a Segment

```bash
curl -X POST "http://localhost:8000/pwa/send-to-segment" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Special Offer",
    "message": "Check out our latest products!",
    "icon": "/static/icons/icon-192x192.png",
    "segment_id": SEGMENT_ID,
    "data": {
      "url": "/promotions"
    }
  }'
```

### 10. View Notification History

```bash
curl -X GET "http://localhost:8000/pwa/notification-history" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 11. View Notification Statistics

```bash
curl -X GET "http://localhost:8000/pwa/statistics" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Testing with the Interactive API Documentation

The FastAPI Swagger UI can be used for interactive testing:

1. Open your browser and go to `http://localhost:8000/docs`
2. Authenticate using the "Authorize" button
3. Explore the `/pwa` endpoints and test them interactively

## Automated Testing

For automated testing, you can adapt the `test_segments.py` script in this directory. It provides a basic structure for setting up test data and making API calls.

## Common Issues and Troubleshooting

### Push Notifications Not Working

1. Check that your VAPID keys are generated and properly stored in the database
2. Verify that the browser supports push notifications
3. Check that the subscription is properly registered in your database
4. Look for any JavaScript errors in the browser console

### Segments Not Populating Correctly

1. Verify that the segment criteria is properly formatted
2. Check that subscriptions have the expected metadata values (device_type, language, etc.)
3. Manually trigger repopulation using the `/segments/{segment_id}/populate` endpoint

### Permission Issues

1. Ensure you're including the Authorization header with a valid token
2. Verify that the user has appropriate permissions for push notification management

## Conclusion

By following these steps, you can thoroughly test your segmented notifications system. For production use, ensure you have proper error handling, rate limiting, and monitoring in place.

For any issues or suggestions, please file an issue on the Kaapi GitHub repository.
