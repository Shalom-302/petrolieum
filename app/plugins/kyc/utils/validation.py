"""
Validation utilities for the KYC plugin.

This module provides validation functions for KYC data and processes,
with special handling for simplified KYC in low-infrastructure regions.
"""

import logging
import re
from datetime import datetime, date
from typing import Dict, Any, Optional, List, Union, Tuple

from ..models.region import InfrastructureLevel
from .security import kyc_security

logger = logging.getLogger(__name__)


class KycValidator:
    """Validator for KYC data and processes."""
    
    @staticmethod
    def validate_personal_info(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate personal information.
        
        Args:
            data: Personal information to validate
            
        Returns:
            Tuple of (valid, error_message)
        """
        if not data:
            return False, "No data provided"
        
        # Basic required fields
        if 'full_name' not in data or not data['full_name']:
            return False, "Full name is required"
        
        # Email validation if provided
        if 'email' in data and data['email']:
            email = data['email']
            email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(email_pattern, email):
                return False, "Invalid email format"
        
        # Phone validation if provided
        if 'phone_number' in data and data['phone_number']:
            phone = data['phone_number']
            # Basic phone validation - can be enhanced for different regions
            if not phone.startswith('+') or len(phone) < 8:
                return False, "Phone number must start with + and have at least 8 digits"
        
        # Date of birth validation if provided
        if 'date_of_birth' in data and data['date_of_birth']:
            dob = data['date_of_birth']
            try:
                dob_date = datetime.strptime(dob, "%Y-%m-%d").date()
                today = date.today()
                age = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))
                if age < 18:
                    return False, "User must be at least 18 years old"
                if age > 120:
                    return False, "Invalid date of birth"
            except ValueError:
                return False, "Date of birth must be in format YYYY-MM-DD"
        
        # Address validation if provided
        if 'address' in data and data['address']:
            address = data['address']
            if 'country' not in address or not address['country']:
                return False, "Country is required in address"
            
            # Country code validation
            if len(address['country']) != 2 or not address['country'].isalpha():
                return False, "Country must be a 2-letter ISO code"
        
        # All validations passed
        return True, None
    
    @staticmethod
    def validate_document(
        document_type: str, 
        document_data: Dict[str, Any],
        current_date: Optional[date] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate identity document.
        
        Args:
            document_type: Type of document
            document_data: Document data to validate
            current_date: Current date for expiry checking, defaults to today
            
        Returns:
            Tuple of (valid, error_message)
        """
        if not document_data:
            return False, "No document data provided"
        
        if current_date is None:
            current_date = date.today()
        
        # Expiry date validation for documents that have expiry
        if 'expiry_date' in document_data and document_data['expiry_date']:
            try:
                expiry_date = datetime.strptime(document_data['expiry_date'], "%Y-%m-%d").date()
                if expiry_date < current_date:
                    return False, f"{document_type.replace('_', ' ').title()} is expired"
            except ValueError:
                return False, "Expiry date must be in format YYYY-MM-DD"
        
        # Document-specific validations
        if document_type == "passport":
            if 'passport_number' not in document_data or not document_data['passport_number']:
                return False, "Passport number is required"
            if 'issuing_country' not in document_data or not document_data['issuing_country']:
                return False, "Issuing country is required for passport"
                
        elif document_type == "national_id":
            if 'id_number' not in document_data or not document_data['id_number']:
                return False, "ID number is required"
                
        elif document_type == "drivers_license":
            if 'license_number' not in document_data or not document_data['license_number']:
                return False, "License number is required"
                
        elif document_type == "third_party_reference":
            if 'reference_name' not in document_data or not document_data['reference_name']:
                return False, "Reference name is required"
            if 'contact_information' not in document_data or not document_data['contact_information']:
                return False, "Contact information is required for reference"
            if 'relationship' not in document_data or not document_data['relationship']:
                return False, "Relationship to reference is required"
        
        # All validations passed
        return True, None
    
    @staticmethod
    def calculate_risk_score(
        user_data: Dict[str, Any],
        verification_data: Dict[str, Any],
        region_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate risk score for a user.
        
        Args:
            user_data: User profile data
            verification_data: Verification data
            region_data: Optional region-specific data
            
        Returns:
            Dictionary with risk score and factors
        """
        base_score = 50  # Medium risk by default
        risk_factors = []
        
        # Infrastructure level affects base risk
        if region_data and 'infrastructure_level' in region_data:
            infrastructure_level = region_data['infrastructure_level']
            if infrastructure_level == InfrastructureLevel.HIGH:
                base_score -= 10  # Lower risk in high infrastructure regions
            elif infrastructure_level == InfrastructureLevel.LOW:
                base_score += 10  # Higher risk in low infrastructure regions
            elif infrastructure_level == InfrastructureLevel.VERY_LOW:
                base_score += 20  # Much higher risk in very low infrastructure regions
        
        # Document factors
        if 'documents_provided' in verification_data and verification_data['documents_provided']:
            # More documents lower risk
            doc_count = len(verification_data['documents_provided'])
            if doc_count >= 3:
                base_score -= 15
                risk_factors.append("Multiple documents provided")
            elif doc_count == 2:
                base_score -= 10
                risk_factors.append("Two documents provided")
        else:
            # No documents increase risk
            base_score += 20
            risk_factors.append("No documents provided")
        
        # Simplified KYC factors
        if verification_data.get('verification_type') == 'simplified':
            base_score += 15
            risk_factors.append("Simplified KYC process used")
            
            # References can mitigate risk in simplified KYC
            if 'third_party_references' in verification_data and verification_data['third_party_references']:
                ref_count = len(verification_data['third_party_references'])
                base_score -= (5 * ref_count)  # Each reference reduces risk
                risk_factors.append(f"{ref_count} trusted references provided")
        
        # PEP status increases risk
        if user_data.get('politically_exposed'):
            base_score += 30
            risk_factors.append("Politically exposed person")
        
        # Determine risk level from score
        risk_level = "medium"  # Default
        if base_score < 30:
            risk_level = "low"
        elif 30 <= base_score < 60:
            risk_level = "medium"
        elif 60 <= base_score < 80:
            risk_level = "high"
        else:
            risk_level = "critical"
        
        return {
            "risk_score": base_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors
        }


def validate_simplified_kyc(
    user_data: Dict[str, Any],
    references: List[Dict[str, Any]],
    region_config: Dict[str, Any]
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Validate a simplified KYC submission.
    
    Simplified KYC is designed for regions with low infrastructure,
    relying more on trusted references than traditional document verification.
    
    Args:
        user_data: Basic user information
        references: List of third-party references
        region_config: Configuration for the region
        
    Returns:
        Tuple of (valid, error_message, result_data)
    """
    if not region_config.get('simplified_kyc_enabled', False):
        return False, "Simplified KYC not enabled for this region", {}
    
    # Log the validation attempt with masked data
    masked_data = kyc_security.mask_sensitive_data(user_data)
    logger.info(f"Validating simplified KYC: {masked_data}")
    
    # Get simplified requirements
    simplified_req = region_config.get('simplified_requirements', {})
    min_references = simplified_req.get('required_references', 1)
    accepted_types = simplified_req.get('accepted_referee_types', [])
    
    # Validate basic personal info
    valid, error = KycValidator.validate_personal_info(user_data)
    if not valid:
        return False, error, {}
    
    # Check minimum references
    if len(references) < min_references:
        return False, f"At least {min_references} trusted references required", {}
    
    # Validate each reference
    valid_references = []
    for ref in references:
        # Check reference type
        ref_type = ref.get('reference_type')
        if ref_type not in accepted_types:
            return False, f"Reference type '{ref_type}' not accepted in this region", {}
        
        # Basic reference validation
        if not ref.get('full_name'):
            return False, "Reference must have a name", {}
        if not ref.get('contact_info'):
            return False, "Reference must have contact information", {}
        if not ref.get('relationship'):
            return False, "Relationship to reference must be specified", {}
        
        valid_references.append(ref)
    
    # Calculate risk for the simplified KYC
    risk_data = KycValidator.calculate_risk_score(
        user_data,
        {"verification_type": "simplified", "third_party_references": valid_references},
        region_config
    )
    
    # Generate result data
    result_data = {
        "valid": True,
        "validation_method": "simplified_kyc",
        "reference_count": len(valid_references),
        "risk_assessment": risk_data,
        "verification_notes": f"Simplified KYC approved with {len(valid_references)} references"
    }
    
    return True, None, result_data
