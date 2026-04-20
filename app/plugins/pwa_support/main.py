"""
PWA Support Plugin for Kaapi

This plugin enables Progressive Web App (PWA) features:
- Web App Manifest (/manifest.json)
- Service Worker (/service-worker.js)
- PWA Registration Script (/pwa-register.js)
- Push Notifications
- Offline Support

All endpoints are prefixed with the plugin path.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Any
import json
import logging
from datetime import datetime

from app.core.db import get_db
from app.core.security import get_current_user, get_current_user_optional
from app.plugins.advanced_auth.models import User

from .models import PWASettings, PushSubscription, NotificationSegment, NotificationHistory, NotificationReceipt
from .schemas import (
    PWAManifestSchema, 
    ServiceWorkerConfigSchema, 
    PushSubscriptionSchema, 
    PushNotificationSchema,
    SegmentCriteriaSchema,
    NotificationSegmentCreate,
    NotificationSegmentUpdate,
    NotificationSegmentRead,
    SegmentSubscriptionAssignment,
    SegmentedNotificationSend,
    NotificationHistoryRead,
    NotificationStatistics
)
from .service_worker_builder import generate_service_worker
from .push_service import (
    register_subscription, 
    unregister_subscription, 
    get_vapid_keys, 
    send_push_notification,
    send_segmented_notification,
    create_notification_segment,
    update_notification_segment,
    delete_notification_segment,
    assign_subscriptions_to_segment,
    remove_subscriptions_from_segment,
    populate_dynamic_segment,
    get_notification_statistics
)


logger = logging.getLogger("pwa")


def get_router() -> APIRouter:
    """Get the router for the PWA Support plugin"""
    # Les routes seront accessibles sous /api/pwa grâce au préfixe défini dans main.py
    router = APIRouter()
    
    # Health check endpoint
    @router.get("/health/ping", response_model=dict)
    async def health_ping():
        """Simple health check endpoint for the PWA module"""
        return {"status": "ok", "timestamp": str(datetime.now())}
    
    # Push notification status endpoint
    @router.get("/push/status", response_model=dict)
    async def push_status(
        db: Session = Depends(get_db),
        current_user: Optional[User] = Depends(get_current_user_optional)
    ):
        """Check if the current user has any push subscriptions"""
        is_subscribed = False
        
        if current_user:
            # Check if user has any subscriptions
            subscriptions = db.query(PushSubscription).filter(
                PushSubscription.user_id == current_user.id
            ).all()
            is_subscribed = len(subscriptions) > 0
        
        return {"isSubscribed": is_subscribed}
    
    # Manifest endpoint
    @router.get("/manifest.json", response_class=JSONResponse)
    async def get_manifest(db: Session = Depends(get_db)):
        """Serve the PWA manifest.json file"""
        settings = db.query(PWASettings).first()
        
        if not settings or not settings.manifest:
            # Return default manifest
            return default_manifest()
        
        try:
            manifest_data = json.loads(settings.manifest)
            return manifest_data
        except:
            logger.error("Failed to parse manifest JSON")
            return default_manifest()
    
    @router.put("/manifest", response_model=PWAManifestSchema)
    async def update_manifest(
        manifest: PWAManifestSchema,
        db: Session = Depends(get_db),
        _: User = Depends(get_current_user)
    ):
        """Update the PWA manifest"""
        settings = db.query(PWASettings).first()
        
        if not settings:
            settings = PWASettings()
            db.add(settings)
        
        settings.manifest = json.dumps(manifest.dict())
        db.commit()
        
        return manifest
    
    # Service Worker endpoint
    @router.get("/service-worker.js", response_class=Response)
    async def get_service_worker(db: Session = Depends(get_db)):
        """Serve the service worker JavaScript file"""
        settings = db.query(PWASettings).first()
        
        config = None
        if settings and settings.service_worker_config:
            try:
                config = json.loads(settings.service_worker_config)
            except:
                logger.error("Failed to parse service worker config JSON")
        
        if not config:
            # Use default config
            config = {
                "cache_version": "v1",
                "cache_name": "kaapi-pwa-cache",
                "urls_to_cache": [
                    "/",
                    "/offline.html",
                    "/static/css/main.css",
                    "/static/js/main.js",
                    "/static/logo.png"
                ],
                "offline_fallback": "/offline.html",
                "dynamic_cache_enabled": True
            }
        
        service_worker_js = generate_service_worker(config)
        
        return Response(
            content=service_worker_js,
            media_type="application/javascript"
        )
    
    @router.put("/service-worker-config", response_model=ServiceWorkerConfigSchema)
    async def update_service_worker_config(
        config: ServiceWorkerConfigSchema,
        db: Session = Depends(get_db),
        _: User = Depends(get_current_user)
    ):
        """Update the service worker configuration"""
        settings = db.query(PWASettings).first()
        
        if not settings:
            settings = PWASettings()
            db.add(settings)
        
        settings.service_worker_config = json.dumps(config.dict())
        db.commit()
        
        return config
    
    # PWA registration script
    @router.get("/pwa-register.js", response_class=Response)
    async def get_pwa_register_script(request: Request, db: Session = Depends(get_db)):
        """Serve the PWA registration script"""
        # Get base URL for the app
        base_url = str(request.base_url).rstrip("/")
        
        # Get VAPID public key
        vapid_keys = get_vapid_keys(db)
        public_key = vapid_keys["public_key"]
        
        # Generate the registration script with the correct paths
        script = f"""
        // Kaapi PWA Registration Script
        const registerServiceWorker = async () => {{
            if ('serviceWorker' in navigator) {{
                try {{
                    const registration = await navigator.serviceWorker.register('{base_url}/api/pwa/service-worker.js', {{
                        scope: '/'
                    }});
                    
                    console.log('Kaapi PWA service worker registered:', registration);
                    
                    // Initialize push notifications if available
                    initPushNotifications(registration);
                    
                    return registration;
                }} catch (error) {{
                    console.error('Kaapi PWA service worker registration failed:', error);
                }}
            }}
        }};
        
        const initPushNotifications = async (registration) => {{
            if ('PushManager' in window) {{
                try {{
                    // Check if already subscribed
                    let subscription = await registration.pushManager.getSubscription();
                    
                    // If not subscribed, create a subscription
                    if (!subscription) {{
                        const vapidPublicKey = '{public_key}';
                        const convertedVapidKey = urlBase64ToUint8Array(vapidPublicKey);
                        
                        subscription = await registration.pushManager.subscribe({{
                            userVisibleOnly: true,
                            applicationServerKey: convertedVapidKey
                        }});
                        
                        // Send subscription to server
                        await sendSubscriptionToServer(subscription);
                    }}
                    
                    console.log('Kaapi push notification subscription:', subscription);
                }} catch (error) {{
                    console.error('Kaapi push notification initialization failed:', error);
                }}
            }}
        }};
        
        const sendSubscriptionToServer = async (subscription) => {{
            try {{
                // Get language preference
                const language = navigator.language || navigator.userLanguage;
                
                // Create metadata object with device info
                const metadata = {{
                    language: language,
                    location: null, // This could be populated if you have permission
                    tags: [] // This can be populated with user preferences
                }};
                
                const response = await fetch('{base_url}/api/pwa/push/subscribe', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify({{
                        subscription: subscription,
                        metadata: metadata
                    }})
                }});
                
                if (!response.ok) {{
                    throw new Error('Failed to send subscription to server');
                }}
                
                console.log('Kaapi push subscription sent to server');
            }} catch (error) {{
                console.error('Failed to send push subscription to server:', error);
            }}
        }};
        
        // Utility function to convert base64 to Uint8Array
        const urlBase64ToUint8Array = (base64String) => {{
            const padding = '='.repeat((4 - base64String.length % 4) % 4);
            const base64 = (base64String + padding)
                .replace(/-/g, '+')
                .replace(/_/g, '/');
            
            const rawData = window.atob(base64);
            const outputArray = new Uint8Array(rawData.length);
            
            for (let i = 0; i < rawData.length; ++i) {{
                outputArray[i] = rawData.charCodeAt(i);
            }}
            
            return outputArray;
        }};
        
        // Record push notification click
        navigator.serviceWorker.addEventListener('message', (event) => {{
            if (event.data && event.data.type === 'NOTIFICATION_CLICKED') {{
                const receiptId = event.data.receiptId;
                
                if (receiptId) {{
                    fetch('{base_url}/api/pwa/push/receipt/' + receiptId + '/clicked', {{
                        method: 'POST'
                    }}).catch(error => {{
                        console.error('Failed to record notification click:', error);
                    }});
                }}
            }}
        }});
        
        // Register service worker on load
        window.addEventListener('load', () => {{
            registerServiceWorker();
        }});
        """
        
        return Response(
            content=script,
            media_type="application/javascript"
        )
    
    # Offline fallback page
    @router.get("/offline.html", response_class=HTMLResponse)
    async def get_offline_page():
        """Serve the offline fallback page"""
        offline_html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Offline - Kaapi App</title>
            <link rel="manifest" href="/api/pwa/manifest.json">
            <style>
                :root {
                    --primary-color: #4F46E5;
                    --secondary-color: #818CF8;
                    --bg-gradient-from: #4338CA;
                    --bg-gradient-to: #6366F1;
                }
                
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
                    margin: 0;
                    padding: 0;
                    height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    color: #374151;
                    background: linear-gradient(135deg, var(--bg-gradient-from), var(--bg-gradient-to));
                    position: relative;
                    overflow: hidden;
                }
                
                .geometric-shapes {
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    overflow: hidden;
                    pointer-events: none;
                    z-index: 0;
                }
                
                .shape {
                    position: absolute;
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 50%;
                }
                
                .shape-1 {
                    width: 500px;
                    height: 500px;
                    top: -250px;
                    left: -250px;
                }
                
                .shape-2 {
                    width: 300px;
                    height: 300px;
                    bottom: -150px;
                    right: -150px;
                }
                
                .shape-3 {
                    width: 200px;
                    height: 200px;
                    top: 50%;
                    right: 10%;
                }
                
                .offline-card {
                    background: rgba(255, 255, 255, 0.1);
                    backdrop-filter: blur(10px);
                    -webkit-backdrop-filter: blur(10px);
                    border-radius: 20px;
                    padding: 2.5rem;
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                    text-align: center;
                    max-width: 90%;
                    width: 500px;
                    z-index: 10;
                    color: white;
                    border: 1px solid rgba(255, 255, 255, 0.2);
                }
                
                h1 {
                    margin-top: 0;
                    margin-bottom: 1rem;
                    font-size: 2rem;
                    font-weight: 600;
                }
                
                p {
                    margin-bottom: 1.5rem;
                    font-size: 1.1rem;
                    line-height: 1.5;
                    opacity: 0.9;
                }
                
                .icon {
                    font-size: 4rem;
                    margin-bottom: 1rem;
                }
                
                .retry-button {
                    background-color: white;
                    color: var(--primary-color);
                    border: none;
                    padding: 0.75rem 1.5rem;
                    font-size: 1rem;
                    font-weight: 600;
                    border-radius: 0.5rem;
                    cursor: pointer;
                    transition: all 0.2s ease;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }
                
                .retry-button:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 6px 8px rgba(0, 0, 0, 0.1);
                }
                
                @media (max-width: 768px) {
                    .offline-card {
                        padding: 1.5rem;
                    }
                    
                    h1 {
                        font-size: 1.5rem;
                    }
                    
                    p {
                        font-size: 1rem;
                    }
                    
                    .icon {
                        font-size: 3rem;
                    }
                }
            </style>
        </head>
        <body>
            <div class="geometric-shapes">
                <div class="shape shape-1"></div>
                <div class="shape shape-2"></div>
                <div class="shape shape-3"></div>
            </div>
            
            <div class="offline-card">
                <div class="icon">📶</div>
                <h1>You're Offline</h1>
                <p>It looks like you're currently offline. Please check your internet connection and try again.</p>
                <p>Some features of the Kaapi App are still available while you're offline.</p>
                <button class="retry-button" onclick="window.location.reload()">Try Again</button>
            </div>
            
            <script>
                // Check if we're back online
                window.addEventListener('online', () => {
                    window.location.reload();
                });
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=offline_html)
    
    # Push notification endpoints
    @router.post("/push/subscribe", response_model=dict)
    async def subscribe_push(
        data: dict,
        request: Request,
        db: Session = Depends(get_db),
        current_user: Optional[User] = Depends(get_current_user)
    ):
        """Subscribe to push notifications"""
        user_id = current_user.id if current_user else None
        
        # Extract the subscription from the data
        subscription_data = PushSubscriptionSchema(**data["subscription"])
        
        # Get user agent
        user_agent = request.headers.get("user-agent")
        
        # Extract metadata if available
        metadata = data.get("metadata")
        
        success = register_subscription(
            db,
            subscription_data,
            user_id=user_id,
            user_agent=user_agent,
            metadata=metadata
        )
        
        if success:
            return {"success": True, "message": "Subscription registered"}
        else:
            raise HTTPException(status_code=500, detail="Failed to register subscription")
    
    @router.delete("/push/unsubscribe", response_model=dict)
    async def unsubscribe_push(
        data: dict,
        db: Session = Depends(get_db)
    ):
        """Unsubscribe from push notifications"""
        # Extract the endpoint from the data
        endpoint = data.get("endpoint")
        
        if not endpoint:
            raise HTTPException(status_code=400, detail="Endpoint is required")
        
        success = unregister_subscription(db, endpoint)
        
        if success:
            return {"success": True, "message": "Subscription unregistered"}
        else:
            raise HTTPException(status_code=404, detail="Subscription not found")
    
    @router.get("/push/vapid-public-key", response_model=dict)
    async def get_vapid_public_key(db: Session = Depends(get_db)):
        """Get the VAPID public key for push notifications"""
        vapid_keys = get_vapid_keys(db)
        
        return {"publicKey": vapid_keys["public_key"]}
    
    @router.post("/push/send", response_model=dict)
    async def send_push(
        notification: PushNotificationSchema,
        db: Session = Depends(get_db),
        _: User = Depends(get_current_user)
    ):
        """Send a push notification to all subscribed users"""
        sent_count = send_push_notification(
            db,
            title=notification.title,
            message=notification.message,
            icon=notification.icon,
            url=notification.data.get("url") if notification.data else None,
            tag=notification.tag
        )
        
        return {"success": True, "sent_count": sent_count}
    
    # Record notification clicks
    @router.post("/push/receipt/{receipt_id}/clicked", response_model=dict)
    async def record_notification_click(
        receipt_id: int,
        db: Session = Depends(get_db)
    ):
        """Record that a push notification was clicked"""
        receipt = db.query(NotificationReceipt).filter(
            NotificationReceipt.id == receipt_id
        ).first()
        
        if not receipt:
            raise HTTPException(status_code=404, detail="Receipt not found")
        
        receipt.clicked = True
        receipt.clicked_at = datetime.utcnow()
        db.add(receipt)
        db.commit()
        
        return {"success": True}
    
    # New endpoints for segmented notifications
    
    @router.post("/segments", response_model=NotificationSegmentRead)
    async def create_segment(
        segment: NotificationSegmentCreate,
        db: Session = Depends(get_db),
        _: User = Depends(get_current_user)
    ):
        """Create a new notification segment"""
        new_segment = create_notification_segment(db, segment.dict())
        
        # Get subscription count
        subscription_count = len(new_segment.subscriptions)
        
        return {
            "id": new_segment.id,
            "name": new_segment.name,
            "description": new_segment.description,
            "criteria": json.loads(new_segment.criteria) if new_segment.criteria else None,
            "is_dynamic": new_segment.is_dynamic,
            "created_at": new_segment.created_at,
            "updated_at": new_segment.updated_at,
            "subscription_count": subscription_count
        }
    
    @router.get("/segments", response_model=List[NotificationSegmentRead])
    async def get_all_segments(
        db: Session = Depends(get_db),
        _: User = Depends(get_current_user)
    ):
        """Get all notification segments"""
        segments = db.query(NotificationSegment).all()
        
        result = []
        for segment in segments:
            subscription_count = len(segment.subscriptions)
            
            result.append({
                "id": segment.id,
                "name": segment.name,
                "description": segment.description,
                "criteria": json.loads(segment.criteria) if segment.criteria else None,
                "is_dynamic": segment.is_dynamic,
                "created_at": segment.created_at,
                "updated_at": segment.updated_at,
                "subscription_count": subscription_count
            })
        
        return result
    
    @router.get("/segments/{segment_id}", response_model=NotificationSegmentRead)
    async def get_segment(
        segment_id: int,
        db: Session = Depends(get_db),
        _: User = Depends(get_current_user)
    ):
        """Get a specific notification segment"""
        segment = db.query(NotificationSegment).filter(
            NotificationSegment.id == segment_id
        ).first()
        
        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")
        
        subscription_count = len(segment.subscriptions)
        
        return {
            "id": segment.id,
            "name": segment.name,
            "description": segment.description,
            "criteria": json.loads(segment.criteria) if segment.criteria else None,
            "is_dynamic": segment.is_dynamic,
            "created_at": segment.created_at,
            "updated_at": segment.updated_at,
            "subscription_count": subscription_count
        }
    
    @router.put("/segments/{segment_id}", response_model=NotificationSegmentRead)
    async def update_segment(
        segment_id: int,
        segment: NotificationSegmentUpdate,
        db: Session = Depends(get_db),
        _: User = Depends(get_current_user)
    ):
        """Update a notification segment"""
        updated_segment = update_notification_segment(db, segment_id, segment.dict(exclude_unset=True))
        
        if not updated_segment:
            raise HTTPException(status_code=404, detail="Segment not found")
        
        subscription_count = len(updated_segment.subscriptions)
        
        return {
            "id": updated_segment.id,
            "name": updated_segment.name,
            "description": updated_segment.description,
            "criteria": json.loads(updated_segment.criteria) if updated_segment.criteria else None,
            "is_dynamic": updated_segment.is_dynamic,
            "created_at": updated_segment.created_at,
            "updated_at": updated_segment.updated_at,
            "subscription_count": subscription_count
        }
    
    @router.delete("/segments/{segment_id}", response_model=dict)
    async def delete_segment(
        segment_id: int,
        db: Session = Depends(get_db),
        _: User = Depends(get_current_user)
    ):
        """Delete a notification segment"""
        success = delete_notification_segment(db, segment_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Segment not found")
        
        return {"success": True, "message": "Segment deleted"}
    
    @router.post("/segments/{segment_id}/assign", response_model=dict)
    async def assign_to_segment(
        segment_id: int,
        assignment: SegmentSubscriptionAssignment,
        db: Session = Depends(get_db),
        _: User = Depends(get_current_user)
    ):
        """Assign subscriptions to a segment"""
        success_count, failed_count = assign_subscriptions_to_segment(
            db, segment_id, assignment.subscription_ids
        )
        
        return {
            "success": True,
            "assigned_count": success_count,
            "failed_count": failed_count
        }
    
    @router.post("/segments/{segment_id}/remove", response_model=dict)
    async def remove_from_segment(
        segment_id: int,
        assignment: SegmentSubscriptionAssignment,
        db: Session = Depends(get_db),
        _: User = Depends(get_current_user)
    ):
        """Remove subscriptions from a segment"""
        success_count, failed_count = remove_subscriptions_from_segment(
            db, segment_id, assignment.subscription_ids
        )
        
        return {
            "success": True,
            "removed_count": success_count,
            "failed_count": failed_count
        }
    
    @router.post("/segments/{segment_id}/populate", response_model=dict)
    async def repopulate_segment(
        segment_id: int,
        db: Session = Depends(get_db),
        _: User = Depends(get_current_user)
    ):
        """Repopulate a dynamic segment based on its criteria"""
        segment = db.query(NotificationSegment).filter(
            NotificationSegment.id == segment_id
        ).first()
        
        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")
        
        if not segment.is_dynamic:
            raise HTTPException(status_code=400, detail="Only dynamic segments can be populated")
        
        # Clear current subscriptions
        segment.subscriptions = []
        db.add(segment)
        db.commit()
        
        # Repopulate
        count = populate_dynamic_segment(db, segment)
        
        return {"success": True, "added_count": count}
    
    @router.post("/send-to-segment", response_model=dict)
    async def send_to_segment(
        notification: SegmentedNotificationSend,
        db: Session = Depends(get_db),
        _: User = Depends(get_current_user)
    ):
        """Send a push notification to a specific segment"""
        sent_count = send_segmented_notification(db, notification)
        
        return {"success": True, "sent_count": sent_count}
    
    @router.get("/notification-history", response_model=List[NotificationHistoryRead])
    async def get_notification_history(
        db: Session = Depends(get_db),
        _: User = Depends(get_current_user),
        limit: int = 50,
        offset: int = 0
    ):
        """Get notification history"""
        notifications = db.query(NotificationHistory).order_by(
            NotificationHistory.sent_at.desc()
        ).offset(offset).limit(limit).all()
        
        result = []
        for notification in notifications:
            segment_name = None
            if notification.segment_id:
                segment = db.query(NotificationSegment).filter(
                    NotificationSegment.id == notification.segment_id
                ).first()
                if segment:
                    segment_name = segment.name
            
            result.append({
                "id": notification.id,
                "title": notification.title,
                "message": notification.message,
                "icon": notification.icon,
                "url": notification.url,
                "segment_id": notification.segment_id,
                "segment_name": segment_name,
                "sent_at": notification.sent_at,
                "sent_count": notification.sent_count
            })
        
        return result
    
    @router.get("/statistics", response_model=NotificationStatistics)
    async def get_statistics(
        db: Session = Depends(get_db),
        _: User = Depends(get_current_user)
    ):
        """Get notification delivery statistics"""
        return get_notification_statistics(db)
    
    return router


def default_manifest():
    """Return a default PWA manifest"""
    return {
        "name": "Kaapi App",
        "short_name": "Kaapi",
        "description": "Your Kaapi application",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#4F46E5",
        "theme_color": "#4F46E5",
        "icons": [
            {
                "src": "/static/icons/icon-192x192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/icons/icon-512x512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }


pwa_support_router = get_router()