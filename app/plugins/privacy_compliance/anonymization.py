"""
Data anonymization service for the GDPR compliance plugin
"""

import hashlib
import re
import secrets
import string
import logging
import json
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from .models import AnonymizationLog


logger = logging.getLogger("privacy")


def generate_pseudonym(original: str, salt: Optional[str] = None) -> str:
    """
    Generates a pseudonym based on the original text.
    
    Args:
        original: The original text to pseudonymize
        salt: An optional salt to strengthen the pseudonymization
        
    Returns:
        A pseudonymized string of the same length as the original
    """
    if not original:
        return ""
    
    # Use a random salt if none is provided
    if not salt:
        salt = secrets.token_hex(8)
    
    # Create a hash of the original text
    hash_obj = hashlib.sha256(f"{original}{salt}".encode()).hexdigest()
    
    # Generate a pseudonym of the same length as the original
    chars = string.ascii_letters + string.digits
    pseudonym = ""
    
    # Use the hash to generate a pseudonym of the same length
    for i in range(len(original)):
        # Use the hash characters as indices to select from chars
        index = int(hash_obj[i % len(hash_obj)], 16) % len(chars)
        pseudonym += chars[index]
    
    return pseudonym


def hash_data(data: str, salt: Optional[str] = None) -> str:
    """
    Hashes a string.
    
    Args:
        data: The data to hash
        salt: An optional salt to strengthen the hash
        
    Returns:
        A hashed version of the data
    """
    if not data:
        return ""
    
    if not salt:
        salt = secrets.token_hex(8)
    
    return hashlib.sha256(f"{data}{salt}".encode()).hexdigest()


def redact_data(data: str, placeholder: str = "***") -> str:
    """
    Completely masks the data.
    
    Args:
        data: The data to mask
        placeholder: The replacement text
        
    Returns:
        The masked data
    """
    if not data:
        return ""
    
    return placeholder


def generalize_data(data: str, data_type: str) -> str:
    """
    Generalizes data according to its type.
    
    Args:
        data: The data to generalize
        data_type: The type of data (email, phone, address, date, age)
        
    Returns:
        A generalized version of the data
    """
    if not data:
        return ""
    
    if data_type == "email":
        # Keep only the domain
        if "@" in data:
            return f"user@{data.split('@')[1]}"
        return "user@example.com"
    
    elif data_type == "phone":
        # Replace all digits except the last 2 with X
        return re.sub(r'\d(?=\d{2})', 'X', data)
    
    elif data_type == "address":
        # Keep only the city and postal code
        parts = data.split(',')
        if len(parts) > 1:
            return parts[-1].strip()
        return "Geographic area"
    
    elif data_type == "date":
        # Keep only the month and year
        try:
            date_obj = datetime.strptime(data, "%Y-%m-%d")
            return date_obj.strftime("%m/%Y")
        except:
            return "01/2000"
    
    elif data_type == "age":
        # Round to the higher ten
        try:
            age = int(data)
            return str(((age + 9) // 10) * 10)
        except:
            return "30-40"
    
    # By default, return a generalized version
    return f"{data[:1]}..." if data else ""


def anonymize_data(
    data: Dict[str, Any], 
    fields_to_anonymize: List[str], 
    anonymization_method: str = "pseudonymize",
    data_types: Optional[Dict[str, str]] = None,
    salt: Optional[str] = None
) -> Dict[str, Any]:
    """
    Anonymizes specified data according to the chosen method.
    
    Args:
        data: Dictionary containing the data to anonymize
        fields_to_anonymize: List of field names to anonymize
        anonymization_method: Method to use (pseudonymize, hash, redact, generalize)
        data_types: Dictionary mapping field names to their data types (for generalization)
        salt: Optional salt to strengthen anonymization
        
    Returns:
        Dictionary with anonymized data
    """
    if not data:
        return {}
    
    result = data.copy()
    data_types = data_types or {}
    
    for field in fields_to_anonymize:
        if field in result and result[field]:
            value = str(result[field])
            
            if anonymization_method == "pseudonymize":
                result[field] = generate_pseudonym(value, salt)
            elif anonymization_method == "hash":
                result[field] = hash_data(value, salt)
            elif anonymization_method == "redact":
                result[field] = redact_data(value)
            elif anonymization_method == "generalize":
                data_type = data_types.get(field, "generic")
                result[field] = generalize_data(value, data_type)
    
    return result


def anonymize_entity(
    db: Session, 
    entity_type: str, 
    entity_id: int, 
    fields: List[str],
    method: str = "pseudonymize",
    reason: Optional[str] = None,
    performed_by: Optional[int] = None
) -> bool:
    """
    Anonymizes a database entity and logs the operation.
    
    Args:
        db: SQLAlchemy database session
        entity_type: Type of entity to anonymize (e.g., "user", "order")
        entity_id: ID of the entity
        fields: List of fields to anonymize
        method: Anonymization method
        reason: Reason for anonymization
        performed_by: ID of the user performing the anonymization
        
    Returns:
        True if anonymization succeeded, False otherwise
    """
    
    try:
        # Get the entity model based on entity_type
        if entity_type == "user":
            from app.models import User
            entity = db.query(User).filter(User.id == entity_id).first()
        else:
            # Add other entity types as needed
            logger.error(f"Unknown entity type: {entity_type}")
            return False
        
        if not entity:
            logger.error(f"Entity {entity_type} with ID {entity_id} not found")
            return False
        
        # Get current data
        entity_dict = {c.name: getattr(entity, c.name) for c in entity.__table__.columns}
        
        # Anonymize only the specified fields
        valid_fields = [f for f in fields if f in entity_dict]
        anonymized_data = anonymize_data(
            entity_dict, 
            valid_fields, 
            anonymization_method=method
        )
        
        # Update entity with anonymized data
        for field, value in anonymized_data.items():
            if field in valid_fields:
                setattr(entity, field, value)
        
        # Log the anonymization
        log = AnonymizationLog(
            entity_type=entity_type,
            entity_id=entity_id,
            fields_anonymized=valid_fields,
            anonymization_method=method,
            reason=reason,
            performed_by=performed_by
        )
        db.add(log)
        db.commit()
        
        return True
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error anonymizing {entity_type} {entity_id}: {str(e)}")
        return False


# Utility functions for common use cases

def anonymize_user_data(
    db: Session, 
    user_id: int, 
    fields: Optional[List[str]] = None,
    method: str = "pseudonymize",
    reason: str = "User request",
    performed_by: Optional[int] = None
) -> bool:
    """
    Anonymizes user data.
    
    Args:
        db: SQLAlchemy database session
        user_id: User ID
        fields: List of fields to anonymize (defaults to email, name, phone, address)
        method: Anonymization method
        reason: Reason for anonymization
        performed_by: ID of the user performing the anonymization
        
    Returns:
        True if anonymization succeeded, False otherwise
    """
    
    if fields is None:
        # Default fields to anonymize for users
        fields = ["email", "first_name", "last_name", "phone", "address"]
    
    return anonymize_entity(
        db=db,
        entity_type="user",
        entity_id=user_id,
        fields=fields,
        method=method,
        reason=reason,
        performed_by=performed_by
    )
