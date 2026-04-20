"""
Test script for segmented notifications functionality
"""

import json
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import sys

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.plugins.pwa_support.models import Base, NotificationSegment, PushSubscription
from app.plugins.pwa_support.push_service import create_notification_segment, assign_subscriptions_to_segment
from app.core.db import get_db

# Test configuration
BASE_URL = "http://localhost:8000"
TEST_DB_URL = "sqlite:///./test_pwa.db"

def setup_test_db():
    """Set up test database"""
    engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

def create_test_subscription(db):
    """Create a test push subscription"""
    # This is a mock subscription - in a real app, this would come from a browser
    subscription = PushSubscription(
        endpoint="https://fcm.googleapis.com/fcm/send/test-endpoint",
        p256dh_key="BGzDpO_LQdg0VoBIkbz0VDzWWYnx_izuAkjJM3AxrNWhDJxXiR5jA8Gwl_8r7NKMrQUKZCO8ZA6fdxdoUuZQxcA",
        auth_key="OqYLtD2BG_gD2ph-G_JmBQ",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/91.0.4472.124",
        device_type="desktop",
        language="en-US",
        location="San Francisco",
        tags="test,beta"
    )
    
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    
    print(f"Created test subscription with ID: {subscription.id}")
    return subscription

def test_create_segment():
    """Test creating a notification segment"""
    db = setup_test_db()
    
    # Create a segment
    segment_data = {
        "name": "Test Segment",
        "description": "A test segment for testing",
        "is_dynamic": False,
        "criteria": {
            "device_types": ["desktop"],
            "languages": ["en-US"],
            "locations": ["San Francisco"],
            "tags": ["test"]
        }
    }
    
    segment = create_notification_segment(db, segment_data)
    print(f"Created segment with ID: {segment.id}")
    
    # Create a test subscription
    subscription = create_test_subscription(db)
    
    # Assign subscription to segment
    success_count, failed_count = assign_subscriptions_to_segment(
        db, segment.id, [subscription.id]
    )
    
    print(f"Assigned subscriptions: {success_count} success, {failed_count} failed")
    
    return segment.id, subscription.id

def test_send_to_segment(segment_id):
    """Test sending a notification to a segment"""
    # This would typically be a POST request to the API endpoint
    # but we'll just print the request details for demo purposes
    notification_data = {
        "title": "Test Notification",
        "message": "This is a test notification for the segment",
        "icon": "/static/icons/icon-192x192.png",
        "segment_id": segment_id,
        "url": "https://example.com/test"
    }
    
    print(f"Would send notification to segment {segment_id}:")
    print(json.dumps(notification_data, indent=2))
    
    # In a real test, you would do:
    # response = requests.post(
    #     f"{BASE_URL}/pwa/send-to-segment",
    #     json=notification_data,
    #     headers={"Authorization": f"Bearer {token}"}
    # )
    # print(f"Response: {response.status_code}")
    # print(response.json())

def main():
    """Run the test"""
    print("Testing segmented notifications...")
    segment_id, subscription_id = test_create_segment()
    test_send_to_segment(segment_id)
    print("Test completed successfully!")

if __name__ == "__main__":
    main()
