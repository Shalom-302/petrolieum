"""
Secure timestamp routes.

This module provides API endpoints for creating and verifying cryptographic
timestamps that certify the existence of data at a specific point in time.
"""

import logging
from typing import List, Optional, Dict, Any
import base64
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user_id
from app.core.rate_limit import rate_limit
from app.plugins.digital_signature.utils.security import create_timestamp, verify_timestamp
from app.plugins.digital_signature.models.timestamp import TimestampDB
from app.plugins.digital_signature.schemas.timestamp import (
    TimestampResponse,
    TimestampVerify,
    TimestampCreate
)
from app.plugins.digital_signature.services.timestamp_service import TimestampService

logger = logging.getLogger(__name__)


def get_timestamp_router():
    """
    Create and return a router for timestamp endpoints.
    
    This function initializes an APIRouter with various endpoints for
    handling secure timestamps, including creation and verification.
    
    Returns:
        APIRouter: FastAPI router with timestamp endpoints
    """
    router = APIRouter()
    
    @router.post(
        "/create",
        response_model=TimestampResponse,
        summary="Create a secure timestamp",
        description="Create a cryptographically secure timestamp for data"
    )
    @rate_limit(limit_per_minute=30)
    async def create_secure_timestamp(
        file: UploadFile = File(None),
        hash_value: str = Form(None),
        description: str = Form(None),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """
        Create a cryptographically secure timestamp for data.
        
        This endpoint creates a timestamp that proves the existence of data
        at a specific point in time. The timestamp is digitally signed and
        can be verified later.
        
        Args:
            file: File to timestamp (optional)
            hash_value: Hash value to timestamp (optional)
            description: Description of the timestamp
            db: Database session
            current_user_id: ID of the current user
            
        Returns:
            TimestampResponse: Information about the created timestamp
            
        Note:
            Either file or hash_value must be provided.
        """
        try:
            # Validate input
            if file is None and hash_value is None:
                raise HTTPException(
                    status_code=400, 
                    detail="Either file or hash_value must be provided"
                )
            
            # If file is provided, read its content
            data = None
            data_source = None
            if file:
                data = await file.read()
                data_source = file.filename
            else:
                # If hash value is provided, use it directly
                try:
                    data = bytes.fromhex(hash_value)
                    data_source = f"Hash value: {hash_value}"
                except ValueError:
                    raise HTTPException(
                        status_code=400, 
                        detail="Invalid hash value format. Expected hex string."
                    )
            
            # Create timestamp using the security service
            timestamp_service = TimestampService(db)
            timestamp = timestamp_service.create_timestamp(
                data=data,
                data_source=data_source,
                description=description,
                user_id=current_user_id
            )
            
            return TimestampResponse(
                id=timestamp.id,
                timestamp=timestamp.timestamp,
                data_source=timestamp.data_source,
                data_hash=timestamp.data_hash,
                description=timestamp.description,
                status="completed"
            )
        except Exception as e:
            logger.error(f"Error creating timestamp: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error creating timestamp: {str(e)}"
            )
    
    @router.post(
        "/verify",
        summary="Verify a timestamp",
        description="Verify the authenticity of a cryptographic timestamp"
    )
    @rate_limit(limit_per_minute=50)
    async def verify_secure_timestamp(
        verify_request: TimestampVerify,
        db: Session = Depends(get_db)
    ):
        """
        Verify the authenticity of a cryptographic timestamp.
        
        This endpoint checks if a timestamp is valid and was issued by
        the trusted timestamp authority.
        
        Args:
            verify_request: Timestamp verification request
            db: Database session
            
        Returns:
            dict: Verification result with timestamp details
        """
        try:
            timestamp_service = TimestampService(db)
            
            # Get the timestamp from database
            timestamp = timestamp_service.get_timestamp(verify_request.timestamp_id)
            if not timestamp:
                return {
                    "verified": False,
                    "error": "Timestamp not found"
                }
            
            # If data is provided, verify that it matches the timestamp
            if verify_request.data:
                try:
                    data = base64.b64decode(verify_request.data)
                except ValueError:
                    return {
                        "verified": False,
                        "error": "Invalid data format"
                    }
                
                # Verify the timestamp
                verification_result = timestamp_service.verify_timestamp(
                    timestamp_id=verify_request.timestamp_id,
                    verification_data=data
                )
                
                if verification_result["verified"]:
                    return {
                        "verified": True,
                        "timestamp": timestamp.timestamp,
                        "data_hash": timestamp.data_hash,
                        "issuer": "KAAPI Timestamping Authority"
                    }
                else:
                    return {
                        "verified": False,
                        "error": verification_result["error"]
                    }
            else:
                # Just confirm the timestamp exists and is valid
                return {
                    "verified": True,
                    "timestamp": timestamp.timestamp,
                    "data_hash": timestamp.data_hash,
                    "issuer": "KAAPI Timestamping Authority",
                    "note": "No data provided for content verification"
                }
        except Exception as e:
            logger.error(f"Error verifying timestamp: {e}")
            return {
                "verified": False,
                "error": f"Error verifying timestamp: {str(e)}"
            }
    
    @router.get(
        "/status/{timestamp_id}",
        response_model=TimestampResponse,
        summary="Get timestamp status",
        description="Get the status and details of a timestamp"
    )
    async def get_timestamp_status(
        timestamp_id: str,
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """
        Get the status and details of a timestamp.
        
        Args:
            timestamp_id: ID of the timestamp
            db: Database session
            current_user_id: ID of the current user
            
        Returns:
            TimestampResponse: Information about the timestamp
        """
        try:
            timestamp_service = TimestampService(db)
            timestamp = timestamp_service.get_timestamp(timestamp_id)
            
            if not timestamp:
                raise HTTPException(
                    status_code=404, 
                    detail="Timestamp not found"
                )
            
            # Check if the user has access to this timestamp
            if timestamp.user_id != current_user_id:
                logger.warning(f"Unauthorized access attempt to timestamp {timestamp_id} by user {current_user_id}")
                raise HTTPException(
                    status_code=403, 
                    detail="You don't have permission to access this timestamp"
                )
            
            return TimestampResponse(
                id=timestamp.id,
                timestamp=timestamp.timestamp,
                data_source=timestamp.data_source,
                data_hash=timestamp.data_hash,
                description=timestamp.description,
                status="completed"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting timestamp status: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error getting timestamp status: {str(e)}"
            )
            
    return router
