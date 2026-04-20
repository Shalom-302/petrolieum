"""
Authentication service for Matomo integration.
Handles user synchronization between Kaapi and Matomo.
"""
import logging
import httpx
import uuid
import json
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, Dict, Any, List

from app.plugins.advanced_auth.models import User
from ..models import MatomoUserMapping, MatomoSettings
from ..schemas import MatomoUserSync, MatomoCredentials

logger = logging.getLogger(__name__)

class MatomoAuthService:
    """Service for handling Matomo authentication and user synchronization."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def login(self, credentials: MatomoCredentials) -> Optional[Dict[str, Any]]:
        """Login to Matomo with admin credentials."""
        try:
            # Get Matomo settings
            settings = self.db.query(MatomoSettings).first()
            if not settings:
                logger.error("Matomo settings not found")
                return None
            
            # Call Matomo API to authenticate
            async with httpx.AsyncClient() as client:
                # First, get login form to obtain CSRF token
                login_page_response = await client.get(f"{settings.matomo_url}/index.php?module=Login")
                
                # Extract CSRF token from response HTML
                import re
                csrf_token_match = re.search(r'name="form_nonce"\s+value="([^"]+)"', login_page_response.text)
                if not csrf_token_match:
                    logger.error("Failed to extract CSRF token from Matomo login page")
                    return None
                
                csrf_token = csrf_token_match.group(1)
                
                # Perform login
                login_response = await client.post(
                    f"{settings.matomo_url}/index.php",
                    data={
                        "form_login": credentials.username,
                        "form_password": credentials.password,
                        "form_nonce": csrf_token,
                        "form_rememberme": "1" if credentials.remember_me else "0",
                        "module": "Login",
                        "action": "submit"
                    },
                    follow_redirects=True
                )
                
                # Check if login was successful by looking for auth_token in cookies or response
                if "remember_me" in login_response.cookies or "login_auth_token" in login_response.cookies:
                    # Extract auth token from cookies or from page content
                    auth_token = None
                    
                    # Try to find token in page content
                    token_match = re.search(r'token_auth=([a-f0-9]{32})', login_response.text)
                    if token_match:
                        auth_token = token_match.group(1)
                    
                    # Update settings with the auth token if found
                    if auth_token:
                        settings.auth_token = auth_token
                        self.db.commit()
                    
                    return {
                        "status": "success",
                        "session_valid": True,
                        "auth_token": auth_token,
                        "cookies": dict(login_response.cookies)
                    }
                else:
                    logger.error("Failed to authenticate with Matomo")
                    return None
        except Exception as e:
            logger.error(f"Error authenticating with Matomo: {str(e)}")
            return None
    
    async def sync_user(self, user_data: MatomoUserSync) -> Optional[Dict[str, Any]]:
        """Synchronize a Kaapi user with Matomo."""
        try:
            # Get Matomo settings
            settings = self.db.query(MatomoSettings).first()
            if not settings or not settings.auth_token:
                logger.error("Matomo settings not found or missing auth token")
                return None
            
            # Check if user mapping already exists
            user_mapping = self.db.query(MatomoUserMapping).filter(
                MatomoUserMapping.kaapi_user_id == user_data.kaapi_user_id
            ).first()
            
            matomo_user_id = None
            
            if user_mapping:
                # User already mapped, update in Matomo
                matomo_user_id = user_mapping.matomo_user_id
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{settings.matomo_url}/index.php",
                        params={
                            "module": "API",
                            "method": "UsersManager.updateUser",
                            "userLogin": user_mapping.matomo_login,
                            "email": user_data.email,
                            "password": user_data.password if user_data.password else "",
                            "token_auth": settings.auth_token,
                            "format": "json"
                        }
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"Error updating user in Matomo: {response.text}")
                        return None
            else:
                # Create new user in Matomo
                login = user_data.login or f"user_{str(uuid.uuid4())[:8]}"
                password = user_data.password or str(uuid.uuid4())
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{settings.matomo_url}/index.php",
                        params={
                            "module": "API",
                            "method": "UsersManager.addUser",
                            "userLogin": login,
                            "password": password,
                            "email": user_data.email,
                            "token_auth": settings.auth_token,
                            "format": "json"
                        }
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"Error creating user in Matomo: {response.text}")
                        return None
                    
                    # Give access to the site
                    site_response = await client.post(
                        f"{settings.matomo_url}/index.php",
                        params={
                            "module": "API",
                            "method": "UsersManager.setUserAccess",
                            "userLogin": login,
                            "access": user_data.access_level,
                            "idSites": settings.site_id,
                            "token_auth": settings.auth_token,
                            "format": "json"
                        }
                    )
                    
                    if site_response.status_code != 200:
                        logger.error(f"Error setting user access in Matomo: {site_response.text}")
                    
                    # Create user mapping
                    user_mapping = MatomoUserMapping(
                        kaapi_user_id=user_data.kaapi_user_id,
                        matomo_user_id=login,  # Using login as the ID
                        matomo_login=login,
                        access_level=user_data.access_level
                    )
                    self.db.add(user_mapping)
                    self.db.commit()
                    
                    matomo_user_id = login
            
            return {
                "status": "success",
                "matomo_id": matomo_user_id
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error synchronizing user with Matomo: {str(e)}")
            return None
    
    async def sync_all_users(self, users: List[User]) -> str:
        """
        Synchronize all Kaapi users with Matomo.
        Returns a task ID for tracking the background task.
        """
        from app.core.background_tasks import add_task
        
        async def _sync_users_task(users: List[User]):
            for user in users:
                user_data = MatomoUserSync(
                    kaapi_user_id=str(user.id),
                    email=user.email,
                    login=user.username or user.email
                )
                await self.sync_user(user_data)
        
        # Generate a task ID
        task_id = str(uuid.uuid4())
        
        # Add the task to the background tasks queue
        add_task(task_id, _sync_users_task(users))
        
        return task_id
