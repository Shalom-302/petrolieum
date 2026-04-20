"""
Utility functions for validating data during import and export operations.
"""

import re
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional

from app.plugins.data_exchange.models import ValidationRule
from app.plugins.data_exchange.schemas import DataValidationError


def validate_data(
    data: Dict[str, Any],
    validation_rules: Dict[str, List[Dict[str, Any]]],
    entity_name: str,
    row_index: Optional[int] = None
) -> List[DataValidationError]:
    """
    Validate a data row against validation rules.
    
    Args:
        data: Dictionary with data to validate
        validation_rules: Dictionary mapping field names to lists of validation rules
        entity_name: Name of the entity being validated
        row_index: Optional index of the row being validated
        
    Returns:
        List of validation errors
    """
    errors = []
    
    # Check each field with validation rules
    for field_name, rules in validation_rules.items():
        field_value = data.get(field_name)
        
        for rule in rules:
            is_valid, error_message = apply_validation_rule(
                field_value, rule, field_name
            )
            
            if not is_valid:
                errors.append(
                    DataValidationError(
                        field_name=field_name,
                        rule_type=rule.get('rule_type'),
                        error_message=error_message,
                        row_index=row_index,
                        value=field_value
                    )
                )
    
    return errors


def validate_with_rule(
    data: Dict[str, Any],
    rule: ValidationRule
) -> Tuple[bool, Optional[str]]:
    """
    Validate data with a ValidationRule object.
    
    Args:
        data: Dictionary with data to validate
        rule: ValidationRule object
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    field_value = data.get(rule.field_name)
    
    rule_data = {
        'rule_type': rule.rule_type,
        'configuration': rule.configuration
    }
    
    return apply_validation_rule(field_value, rule_data, rule.field_name)


def validate_with_config(
    data: Dict[str, Any],
    rule_config: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Validate data with a rule configuration.
    
    Args:
        data: Dictionary with data to validate
        rule_config: Rule configuration with rule_type and configuration
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    field_name = rule_config.get('field_name')
    if not field_name:
        return False, "Field name not specified in rule configuration"
    
    field_value = data.get(field_name)
    
    return apply_validation_rule(field_value, rule_config, field_name)


def apply_validation_rule(
    value: Any,
    rule: Dict[str, Any],
    field_name: str
) -> Tuple[bool, Optional[str]]:
    """
    Apply a validation rule to a value.
    
    Args:
        value: Value to validate
        rule: Dictionary with rule_type and configuration
        field_name: Name of the field being validated
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    rule_type = rule.get('rule_type')
    config = rule.get('configuration', {})
    
    # Get default error message
    default_error = f"Validation failed for field '{field_name}'"
    error_message = config.get('error_message', default_error)
    
    # Apply rule based on type
    if rule_type == "required":
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return False, error_message or f"Field '{field_name}' is required"
        return True, None
    
    # If value is None and rule is not 'required', validation passes
    if value is None:
        return True, None
    
    if rule_type == "regex":
        pattern = config.get('pattern', '')
        if not pattern or not isinstance(value, str):
            return False, f"Invalid regex pattern or value for field '{field_name}'"
        
        try:
            if not re.match(pattern, value):
                return False, error_message or f"Field '{field_name}' does not match pattern"
        except Exception as e:
            return False, f"Error applying regex: {str(e)}"
        
        return True, None
    
    elif rule_type == "range":
        try:
            num_value = float(value)
            min_val = config.get('min')
            max_val = config.get('max')
            
            if min_val is not None and num_value < float(min_val):
                return False, error_message or f"Field '{field_name}' is below minimum value {min_val}"
            
            if max_val is not None and num_value > float(max_val):
                return False, error_message or f"Field '{field_name}' is above maximum value {max_val}"
            
        except (ValueError, TypeError):
            return False, f"Field '{field_name}' is not a valid number"
        
        return True, None
    
    elif rule_type == "enum":
        allowed_values = config.get('values', [])
        case_sensitive = config.get('case_sensitive', False)
        
        if not allowed_values:
            return False, f"No allowed values specified for field '{field_name}'"
        
        # Convert value to string for comparison
        str_value = str(value)
        
        if not case_sensitive and isinstance(str_value, str):
            # Case-insensitive comparison
            if str_value.lower() not in [str(v).lower() for v in allowed_values]:
                return False, error_message or f"Field '{field_name}' must be one of: {', '.join(str(v) for v in allowed_values)}"
        else:
            # Case-sensitive comparison
            if str_value not in [str(v) for v in allowed_values]:
                return False, error_message or f"Field '{field_name}' must be one of: {', '.join(str(v) for v in allowed_values)}"
        
        return True, None
    
    elif rule_type == "date":
        format_str = config.get('format', '%Y-%m-%d')
        min_date = config.get('min_date')
        max_date = config.get('max_date')
        
        try:
            # Try to parse the date
            if isinstance(value, str):
                date_value = datetime.strptime(value, format_str)
            elif isinstance(value, datetime):
                date_value = value
            else:
                return False, f"Field '{field_name}' is not a valid date"
            
            # Check min date
            if min_date:
                min_date_obj = datetime.strptime(min_date, format_str) if isinstance(min_date, str) else min_date
                if date_value < min_date_obj:
                    return False, error_message or f"Field '{field_name}' is before minimum date {min_date}"
            
            # Check max date
            if max_date:
                max_date_obj = datetime.strptime(max_date, format_str) if isinstance(max_date, str) else max_date
                if date_value > max_date_obj:
                    return False, error_message or f"Field '{field_name}' is after maximum date {max_date}"
            
        except ValueError:
            return False, f"Field '{field_name}' is not a valid date in format {format_str}"
        
        return True, None
    
    elif rule_type == "email":
        if not isinstance(value, str):
            return False, f"Field '{field_name}' is not a string"
        
        # Simple email validation regex
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, value):
            return False, error_message or f"Field '{field_name}' is not a valid email address"
        
        return True, None
    
    elif rule_type == "url":
        if not isinstance(value, str):
            return False, f"Field '{field_name}' is not a string"
        
        # Simple URL validation regex
        url_regex = r'^(https?|ftp)://[^\s/$.?#].[^\s]*$'
        if not re.match(url_regex, value):
            return False, error_message or f"Field '{field_name}' is not a valid URL"
        
        return True, None
    
    elif rule_type == "length":
        if not isinstance(value, str):
            return False, f"Field '{field_name}' is not a string"
        
        min_length = config.get('min')
        max_length = config.get('max')
        
        if min_length is not None and len(value) < int(min_length):
            return False, error_message or f"Field '{field_name}' is shorter than minimum length {min_length}"
        
        if max_length is not None and len(value) > int(max_length):
            return False, error_message or f"Field '{field_name}' is longer than maximum length {max_length}"
        
        return True, None
    
    elif rule_type == "unique":
        # This would require checking against existing data in the database
        # For now, we'll just pass this validation
        return True, None
    
    elif rule_type == "custom":
        # Custom validation code
        code = config.get('code')
        if not code:
            return False, "No custom validation code provided"
        
        try:
            # WARNING: This is potentially unsafe and should be used with caution
            # In a production environment, consider using a safer evaluation method
            validation_result = eval(code, {"value": value, "field_name": field_name})
            
            if not validation_result:
                return False, error_message or f"Custom validation failed for field '{field_name}'"
            
        except Exception as e:
            return False, f"Error in custom validation: {str(e)}"
        
        return True, None
    
    # Unknown rule type
    return False, f"Unknown validation rule type: {rule_type}"
