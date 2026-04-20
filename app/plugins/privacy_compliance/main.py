"""
Main module for the GDPR compliance plugin
"""

import json
import secrets
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.core.db import get_db
from app.core.security import get_current_user
from app.plugins.advanced_auth.models import User

from .models import (
    CookieSettings, CookieCategory, Cookie, UserConsent, 
    DataRequest, DataRequestType, DataRequestStatus, ExportedData,
    DataProcessingRecord, PrivacyPolicy, AnonymizationLog
)

from .schemas import (
    CookieCategoryCreate, CookieCategoryRead,
    CookieCreate, CookieRead, CookieSettingsBase, CookieSettingsUpdate, 
    CookieSettingsRead, UserConsentCreate, UserConsentRead,
    CookieConsentSubmit, DataRequestCreate, DataRequestRead, DataRequestUpdate,
    ExportedDataCreate, ExportedDataRead, DataProcessingRecordCreate, 
    DataProcessingRecordRead, PrivacyPolicyCreate, PrivacyPolicyRead,
    AnonymizationRequest, AnonymizationLogRead
)

from .anonymization import anonymize_data, anonymize_entity, anonymize_user_data


logger = logging.getLogger("privacy")


def get_router():
    """Return the FastAPI router for the plugin"""
    router = APIRouter()
    
    # Cookie settings management
    @router.get("/cookie-settings", response_model=CookieSettingsRead)
    async def get_cookie_settings(db: Session = Depends(get_db)):
        """Get the current cookie settings"""
        settings = db.query(CookieSettings).first()
        if not settings:
            # Create default settings if not exists
            settings = CookieSettings(
                consent_expiry_days=180,
                block_until_consent=False
            )
            db.add(settings)
            db.commit()
            db.refresh(settings)
        return settings
    
    @router.put("/cookie-settings", response_model=CookieSettingsRead)
    async def update_cookie_settings(
        settings_update: CookieSettingsUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """Update cookie settings (admin only)"""
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        settings = db.query(CookieSettings).first()
        if not settings:
            settings = CookieSettings()
            db.add(settings)
        
        for key, value in settings_update.dict(exclude_unset=True).items():
            setattr(settings, key, value)
        
        db.commit()
        db.refresh(settings)
        return settings
    
    @router.options("/cookie-settings")
    async def options_cookie_settings():
        """Handle preflight OPTIONS request for cookie-settings endpoint"""
        return {"detail": "OK"}
    
    # Cookie category management
    @router.get("/cookie-categories", response_model=List[CookieCategoryRead])
    async def get_cookie_categories(db: Session = Depends(get_db)):
        """Get all cookie categories"""
        categories = db.query(CookieCategory).all()
        if not categories:
            # Create default categories if none exist
            necessary = CookieCategory(
                name="Necessary",
                description="These cookies are essential for the website to function properly.",
                is_necessary=True
            )
            preferences = CookieCategory(
                name="Preferences",
                description="These cookies allow the website to remember choices you make and provide enhanced features.",
                is_necessary=False
            )
            statistics = CookieCategory(
                name="Statistics",
                description="These cookies collect information about how you use the website, which pages you visited and which links you clicked on.",
                is_necessary=False
            )
            marketing = CookieCategory(
                name="Marketing",
                description="These cookies are used to track visitors across websites to display relevant advertisements.",
                is_necessary=False
            )
            
            db.add_all([necessary, preferences, statistics, marketing])
            db.commit()
            
            categories = [necessary, preferences, statistics, marketing]
        
        return categories
    
    @router.post("/cookie-categories", response_model=CookieCategoryRead)
    async def create_cookie_category(
        category: CookieCategoryCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """Create a new cookie category (admin only)"""
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        new_category = CookieCategory(**category.dict())
        db.add(new_category)
        db.commit()
        db.refresh(new_category)
        return new_category
    
    @router.put("/cookie-categories/{category_id}", response_model=CookieCategoryRead)
    async def update_cookie_category(
        category_id: int,
        category_update: CookieCategoryCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """Update a cookie category (admin only)"""
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        category = db.query(CookieCategory).filter(CookieCategory.id == category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
            
        for key, value in category_update.dict().items():
            setattr(category, key, value)
            
        db.commit()
        db.refresh(category)
        return category
    
    @router.delete("/cookie-categories/{category_id}", status_code=204)
    async def delete_cookie_category(
        category_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """Delete a cookie category (admin only)"""
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        category = db.query(CookieCategory).filter(CookieCategory.id == category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
            
        if category.is_necessary:
            raise HTTPException(status_code=400, detail="Cannot delete necessary cookie category")
            
        db.delete(category)
        db.commit()
        return Response(status_code=204)
    
    # Cookie management
    @router.get("/cookies", response_model=List[CookieRead])
    async def get_cookies(
        category_id: Optional[int] = None,
        db: Session = Depends(get_db)
    ):
        """Get all cookies or filter by category"""
        query = db.query(Cookie)
        if category_id:
            query = query.filter(Cookie.category_id == category_id)
        return query.all()
    
    @router.post("/cookies", response_model=CookieRead)
    async def create_cookie(
        cookie: CookieCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """Create a new cookie (admin only)"""
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        # Check if category exists
        category = db.query(CookieCategory).filter(CookieCategory.id == cookie.category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
            
        new_cookie = Cookie(**cookie.dict())
        db.add(new_cookie)
        db.commit()
        db.refresh(new_cookie)
        return new_cookie
    
    @router.delete("/cookies/{cookie_id}", status_code=204)
    async def delete_cookie(
        cookie_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """Delete a cookie (admin only)"""
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        cookie = db.query(Cookie).filter(Cookie.id == cookie_id).first()
        if not cookie:
            raise HTTPException(status_code=404, detail="Cookie not found")
            
        db.delete(cookie)
        db.commit()
        return Response(status_code=204)
    
    # Cookie consent data API - For frontend
    @router.get("/cookie-consent/config", response_model=Dict[str, Any])
    async def get_cookie_consent_config(db: Session = Depends(get_db)):
        """Get all cookie consent configuration data for frontend implementation"""
        settings = db.query(CookieSettings).first()
        if not settings:
            # Create default settings if not exists
            settings = CookieSettings(
                consent_expiry_days=180,
                block_until_consent=False
            )
            db.add(settings)
            db.commit()
            db.refresh(settings)
        
        categories = db.query(CookieCategory).all()
        if not categories:
            # Create default categories if none exist
            necessary = CookieCategory(
                name="Necessary",
                description="These cookies are essential for the website to function properly.",
                is_necessary=True
            )
            preferences = CookieCategory(
                name="Preferences",
                description="These cookies allow the website to remember choices you make and provide enhanced features.",
                is_necessary=False
            )
            statistics = CookieCategory(
                name="Statistics",
                description="These cookies collect information about how you use the website, which pages you visited and which links you clicked on.",
                is_necessary=False
            )
            marketing = CookieCategory(
                name="Marketing",
                description="These cookies are used to track visitors across websites to display relevant advertisements.",
                is_necessary=False
            )
            
            db.add_all([necessary, preferences, statistics, marketing])
            db.commit()
            
            categories = [necessary, preferences, statistics, marketing]
        
        # Format categories for the API
        categories_data = []
        for category in categories:
            categories_data.append({
                "id": category.id,
                "name": category.name,
                "description": category.description,
                "isNecessary": category.is_necessary
            })
        
        # Return all configuration in a single object
        return {
            "settings": {
                "consentExpiryDays": settings.consent_expiry_days,
                "blockUntilConsent": settings.block_until_consent
            },
            "categories": categories_data,
            "version": "1.0"
        }
    
    # User consent management
    @router.post("/cookie-consent", response_model=UserConsentRead)
    async def submit_cookie_consent(
        consent: CookieConsentSubmit,
        request: Request,
        db: Session = Depends(get_db)
    ):
        """Submit cookie consent preferences"""
        try:
            # Get IP and User Agent
            client_ip = request.client.host if request.client else "unknown"
            user_agent = request.headers.get("user-agent", "unknown")
            
            # Convert to dict for JSON storage
            if hasattr(consent, "model_dump"):
                # Pydantic v2
                consent_details = consent.model_dump()
            else:
                # Pydantic v1
                consent_details = consent.dict()
            
            # Convert dict to JSON string for database storage
            consent_details_json = json.dumps(consent_details)
            
            # Create user consent record
            user_consent = UserConsent(
                consent_type="cookie",
                consent_details=consent_details_json,
                ip_address=client_ip,
                user_agent=user_agent
            )
            
            # Get cookie settings for expiry calculation
            settings = db.query(CookieSettings).first()
            if settings and settings.consent_expiry_days > 0:
                # Calculate expiry date
                user_consent.expires_at = datetime.utcnow() + timedelta(days=settings.consent_expiry_days)
            
            db.add(user_consent)
            db.commit()
            db.refresh(user_consent)
            
            logger.info(f"Cookie consent submitted from {client_ip}: necessary={consent.necessary}, "
                        f"preferences={consent.preferences}, statistics={consent.statistics}, "
                        f"marketing={consent.marketing}")
            
            # Parse JSON back to dict for response
            if user_consent.consent_details:
                try:
                    user_consent.consent_details = json.loads(user_consent.consent_details)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse consent details for user consent ID {user_consent.id}")
            
            return user_consent
        except Exception as e:
            logger.error(f"Error in submit_cookie_consent: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing cookie consent: {str(e)}")
    
    @router.options("/cookie-consent")
    async def options_cookie_consent():
        """Handle preflight OPTIONS request for cookie-consent endpoint"""
        return {"detail": "OK"}
    
    # Get user consent
    @router.get("/my-cookie-consent", response_model=UserConsentRead)
    async def get_my_cookie_consent(
        request: Request,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """Get current user's cookie consent preferences"""
        consent = db.query(UserConsent).filter(
            UserConsent.user_id == current_user.id,
            UserConsent.consent_type == "cookie"
        ).first()
        if not consent:
            raise HTTPException(status_code=404, detail="No consent record found")
        
        # Parse JSON consent details if they exist
        if consent.consent_details:
            try:
                consent.consent_details = json.loads(consent.consent_details)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse consent details for user {current_user.id}")
        
        return consent
    
    @router.options("/my-cookie-consent")
    async def options_my_cookie_consent():
        """Handle preflight OPTIONS request for my-cookie-consent endpoint"""
        return {"detail": "OK"}
    
    # GDPR Data Requests
    @router.post("/data-requests", response_model=DataRequestRead, status_code=201)
    async def create_data_request(
        request_data: DataRequestCreate,
        request: Request,
        db: Session = Depends(get_db),
        current_user: Optional[User] = Depends(get_current_user)
    ):
        """Create a new GDPR data request (access or deletion)"""
        # Generate verification token
        verification_token = secrets.token_urlsafe(32)
        verification_expires = datetime.utcnow() + timedelta(hours=24)
        
        # Create the request
        data_request = DataRequest(
            email=request_data.email,
            request_type=request_data.request_type,
            status=DataRequestStatus.PENDING,
            ip_address=request.client.host,
            user_agent=request.headers.get("User-Agent"),
            verification_token=verification_token,
            verification_expires=verification_expires,
            request_details=request_data.request_details
        )
        
        # If user is logged in, associate request with their account
        if current_user:
            data_request.user_id = current_user.id
        
        db.add(data_request)
        db.commit()
        db.refresh(data_request)
        
        # TODO: Send verification email to user
        
        return data_request
    
    @router.get("/data-requests", response_model=List[DataRequestRead])
    async def get_data_requests(
        status: Optional[DataRequestStatus] = None,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """Get all data requests (admin only)"""
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        query = db.query(DataRequest)
        if status:
            query = query.filter(DataRequest.status == status)
        
        return query.all()
    
    @router.get("/data-requests/{request_id}", response_model=DataRequestRead)
    async def get_data_request(
        request_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """Get a specific data request"""
        request = db.query(DataRequest).filter(DataRequest.id == request_id).first()
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        
        # Users can only see their own requests, admins can see all
        if not current_user.is_admin and (not request.user_id or request.user_id != current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized")
        
        return request
    
    @router.put("/data-requests/{request_id}", response_model=DataRequestRead)
    async def update_data_request(
        request_id: int,
        request_update: DataRequestUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """Update a data request status (admin only)"""
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        request = db.query(DataRequest).filter(DataRequest.id == request_id).first()
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
            
        for key, value in request_update.dict(exclude_unset=True).items():
            setattr(request, key, value)
            
        db.commit()
        db.refresh(request)
        return request
    
    @router.get("/data-requests/verify/{token}", response_model=DataRequestRead)
    async def verify_data_request(
        token: str,
        db: Session = Depends(get_db)
    ):
        """Verify a data request with a token"""
        now = datetime.utcnow()
        
        request = db.query(DataRequest).filter(
            DataRequest.verification_token == token,
            DataRequest.verification_expires > now,
            DataRequest.verified_at.is_(None)
        ).first()
        
        if not request:
            raise HTTPException(
                status_code=404, 
                detail="Invalid or expired verification token"
            )
            
        # Mark as verified
        request.verified_at = now
        request.status = DataRequestStatus.PROCESSING
        db.commit()
        db.refresh(request)
        
        return request
    
    # Data Anonymization
    @router.post("/anonymize", status_code=200)
    async def anonymize_entity_data(
        request: AnonymizationRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """Anonymize entity data (admin only)"""
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        result = anonymize_entity(
            db=db,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            fields=request.fields,
            method=request.method,
            reason=request.reason,
            performed_by=current_user.id
        )
        
        if not result:
            raise HTTPException(status_code=400, detail="Anonymization failed")
            
        return {"status": "success"}
    
    @router.get("/anonymization-logs", response_model=List[AnonymizationLogRead])
    async def get_anonymization_logs(
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """Get anonymization logs (admin only)"""
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        query = db.query(AnonymizationLog)
        if entity_type:
            query = query.filter(AnonymizationLog.entity_type == entity_type)
        if entity_id:
            query = query.filter(AnonymizationLog.entity_id == entity_id)
            
        return query.all()
    
    # Privacy Policy Management
    @router.post("/privacy-policies", response_model=PrivacyPolicyRead, status_code=201)
    async def create_privacy_policy(
        policy: PrivacyPolicyCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """Create a new privacy policy (admin only)"""
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        # Set created_by if not provided
        if not policy.created_by:
            policy.created_by = current_user.id
            
        new_policy = PrivacyPolicy(**policy.dict())
        db.add(new_policy)
        db.commit()
        db.refresh(new_policy)
        
        return new_policy
    
    @router.get("/privacy-policies", response_model=List[PrivacyPolicyRead])
    async def get_privacy_policies(
        active_only: bool = False,
        db: Session = Depends(get_db)
    ):
        """Get all privacy policies"""
        query = db.query(PrivacyPolicy)
        if active_only:
            query = query.filter(PrivacyPolicy.is_active == True)
        return query.all()
    
    @router.get("/privacy-policies/{policy_id}", response_model=PrivacyPolicyRead)
    async def get_privacy_policy(
        policy_id: int,
        db: Session = Depends(get_db)
    ):
        """Get a specific privacy policy"""
        policy = db.query(PrivacyPolicy).filter(PrivacyPolicy.id == policy_id).first()
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")
        return policy
    
    @router.put("/privacy-policies/{policy_id}/activate", response_model=PrivacyPolicyRead)
    async def activate_privacy_policy(
        policy_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """Activate a privacy policy (admin only)"""
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        policy = db.query(PrivacyPolicy).filter(PrivacyPolicy.id == policy_id).first()
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")
            
        # Deactivate all other policies
        db.query(PrivacyPolicy).filter(PrivacyPolicy.id != policy_id).update(
            {"is_active": False}
        )
        
        # Activate this policy
        policy.is_active = True
        policy.activated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(policy)
        
        return policy
    
    # Data Processing Records
    @router.post("/processing-records", response_model=DataProcessingRecordRead, status_code=201)
    async def create_processing_record(
        record: DataProcessingRecordCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """Create a new data processing record (admin only)"""
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        new_record = DataProcessingRecord(**record.dict())
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
        
        return new_record
    
    @router.get("/processing-records", response_model=List[DataProcessingRecordRead])
    async def get_processing_records(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """Get all data processing records (admin only)"""
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        return db.query(DataProcessingRecord).all()
    
    @router.get("/processing-records/{record_id}", response_model=DataProcessingRecordRead)
    async def get_processing_record(
        record_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """Get a specific data processing record (admin only)"""
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        record = db.query(DataProcessingRecord).filter(DataProcessingRecord.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
            
        return record
    
    return router


privacy_compliance_router = get_router()
