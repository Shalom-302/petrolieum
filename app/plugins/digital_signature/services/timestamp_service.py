"""
Timestamp service.

This module provides services for creating and verifying secure timestamps
that certify the existence of data at a specific point in time.
"""

import logging
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List

from sqlalchemy.orm import Session

from app.plugins.digital_signature.models.timestamp import TimestampDB
from app.plugins.digital_signature.utils.security import (
    create_timestamp,
    verify_timestamp,
    encrypt_signature_data
)
from app.core.security import create_default_encryption

logger = logging.getLogger(__name__)


class TimestampService:
    """
    Service for handling secure timestamp operations.
    
    This service provides methods for creating and verifying cryptographic
    timestamps that can be used to prove the existence of data at a specific
    point in time.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the timestamp service.
        
        Args:
            db: Database session
        """
        self.db = db
        self._encryption_handler = create_default_encryption()
        
    def create_timestamp(
        self,
        data: bytes,
        data_source: Optional[str],
        user_id: str,
        description: Optional[str] = None
    ) -> TimestampDB:
        """
        Create a secure timestamp for data.
        
        Args:
            data: Data to timestamp
            data_source: Source of the data (e.g., file name)
            user_id: ID of the user creating the timestamp
            description: Optional description of the timestamp
            
        Returns:
            TimestampDB: Created timestamp
        """
        try:
            # Hash the data
            data_hash = hashlib.sha256(data).hexdigest()
            
            # Create timestamp using the security service
            timestamp_info = create_timestamp(data)
            
            # Store the timestamp token as JSON
            timestamp_token = json.dumps(timestamp_info)
            
            # Create timestamp record
            timestamp = TimestampDB(
                data_hash=data_hash,
                data_source=data_source,
                timestamp=datetime.fromisoformat(timestamp_info["timestamp"]),
                timestamp_token=timestamp_token,
                user_id=user_id,
                description=description,
                certificate_id="timestamping"  # Using the default certificate
            )
            
            # Save to database
            self.db.add(timestamp)
            self.db.commit()
            self.db.refresh(timestamp)
            
            logger.info(f"Created timestamp with ID {timestamp.id}")
            return timestamp
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating timestamp: {e}")
            raise
            
    def verify_timestamp(
        self,
        timestamp_id: str,
        verification_data: bytes
    ) -> Dict[str, Any]:
        """
        Verify that data matches a timestamp.
        
        Args:
            timestamp_id: ID of the timestamp to verify against
            verification_data: Data to verify
            
        Returns:
            Dict[str, Any]: Verification result
        """
        try:
            # Get the timestamp from database
            timestamp = self.get_timestamp(timestamp_id)
            if not timestamp:
                return {
                    "verified": False,
                    "error": "Timestamp not found"
                }
            
            # Check if the timestamp is valid
            if not timestamp.is_valid:
                return {
                    "verified": False,
                    "error": "Timestamp is no longer valid"
                }
            
            # Hash the verification data
            verification_hash = hashlib.sha256(verification_data).hexdigest()
            
            # Check if the hash matches
            if verification_hash != timestamp.data_hash:
                return {
                    "verified": False,
                    "error": "Data hash mismatch"
                }
            
            # Parse the timestamp token
            timestamp_token = json.loads(timestamp.timestamp_token)
            
            # Verify the timestamp with the security service
            is_valid = verify_timestamp(verification_data, timestamp_token)
            
            if is_valid:
                # Update verification count and last verified timestamp
                timestamp.verification_count += 1
                timestamp.last_verified_at = datetime.utcnow()
                self.db.commit()
                
                return {
                    "verified": True
                }
            else:
                return {
                    "verified": False,
                    "error": "Invalid timestamp signature"
                }
        except Exception as e:
            logger.error(f"Error verifying timestamp: {e}")
            return {
                "verified": False,
                "error": f"Error verifying timestamp: {str(e)}"
            }
            
    def get_timestamp(self, timestamp_id: str) -> Optional[TimestampDB]:
        """
        Get a timestamp by ID.
        
        Args:
            timestamp_id: ID of the timestamp
            
        Returns:
            Optional[TimestampDB]: Timestamp if found, None otherwise
        """
        return self.db.query(TimestampDB).filter(TimestampDB.id == timestamp_id).first()
    
    def get_user_timestamps(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[TimestampDB]:
        """
        Get timestamps for a user.
        
        Args:
            user_id: ID of the user
            limit: Maximum number of timestamps to return
            offset: Offset for pagination
            
        Returns:
            List[TimestampDB]: List of timestamps
        """
        return self.db.query(TimestampDB).filter(
            TimestampDB.user_id == user_id
        ).order_by(
            TimestampDB.created_at.desc()
        ).limit(limit).offset(offset).all()
    
    def delete_timestamp(self, timestamp_id: str, user_id: str) -> bool:
        """
        Delete a timestamp.
        
        Args:
            timestamp_id: ID of the timestamp to delete
            user_id: ID of the user requesting deletion
            
        Returns:
            bool: Whether the deletion was successful
        """
        try:
            timestamp = self.get_timestamp(timestamp_id)
            if not timestamp:
                return False
                
            # Check if the user has permission to delete this timestamp
            if timestamp.user_id != user_id:
                logger.warning(f"User {user_id} attempted to delete timestamp {timestamp_id} owned by {timestamp.user_id}")
                return False
                
            self.db.delete(timestamp)
            self.db.commit()
            logger.info(f"Deleted timestamp {timestamp_id}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting timestamp: {e}")
            return False
