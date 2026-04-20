"""
Formatting utilities for business alerts.

This module contains formatting-related utility functions for the
business alerts plugin, ensuring consistent message formats and data
sanitization across the application.
"""

import logging
import re
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

logger = logging.getLogger(__name__)


def format_alert_message(
    template: str, 
    data: Dict[str, Any],
    max_length: int = 500
) -> str:
    """
    Format an alert message template with data.
    
    This function takes a message template with placeholders and fills
    them with values from the provided data dictionary, ensuring the
    result is properly sanitized and length-limited.
    
    Args:
        template: Message template with {placeholders}
        data: Data to use for template placeholders
        max_length: Maximum length for the resulting message
        
    Returns:
        str: Formatted message
    """
    try:
        # First, sanitize the input data
        sanitized_data = {k: sanitize_string(v) if isinstance(v, str) else v 
                          for k, v in data.items()}
        
        # Format the template with the sanitized data
        formatted_message = template.format(**sanitized_data)
        
        # Truncate if necessary
        if len(formatted_message) > max_length:
            formatted_message = formatted_message[:max_length-3] + "..."
            
        # Log formatting action with standardized approach
        logger.debug(f"Formatted alert message from template (length: {len(formatted_message)})")
        return formatted_message
        
    except KeyError as e:
        # Handle missing template keys
        logger.warning(f"Missing key in alert template: {e}")
        return template.replace("{" + str(e).strip("'") + "}", "[missing]")
        
    except Exception as e:
        # Log error with standardized approach
        logger.error(f"Error formatting alert message: {str(e)}")
        return template


def sanitize_string(value: str) -> str:
    """
    Sanitize a string value for safe display.
    
    Args:
        value: String value to sanitize
        
    Returns:
        str: Sanitized string
    """
    if not value:
        return ""
        
    # Remove any potential HTML/script tags
    sanitized = re.sub(r'<[^>]*>', '', value)
    
    # Remove any control characters
    sanitized = re.sub(r'[\x00-\x1F\x7F]', '', sanitized)
    
    return sanitized


def sanitize_alert_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize alert data for safe storage and display.
    
    This function recursively sanitizes all string values in the
    provided data dictionary, ensuring it can be safely stored
    and displayed without security issues.
    
    Args:
        data: Alert data to sanitize
        
    Returns:
        Dict[str, Any]: Sanitized data
    """
    if not isinstance(data, dict):
        logger.warning(f"Expected dict for sanitize_alert_data, got {type(data)}")
        return {}
        
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = sanitize_string(value)
        elif isinstance(value, dict):
            result[key] = sanitize_alert_data(value)
        elif isinstance(value, list):
            result[key] = [
                sanitize_alert_data(v) if isinstance(v, dict) else
                sanitize_string(v) if isinstance(v, str) else v
                for v in value
            ]
        else:
            result[key] = value
            
    return result


def format_timestamp(timestamp: Union[datetime, str, None], format_str: str = "%Y-%m-%d %H:%M:%S") -> Optional[str]:
    """
    Format a timestamp for display.
    
    Args:
        timestamp: Timestamp to format (datetime, ISO string, or None)
        format_str: Format string for the output
        
    Returns:
        Optional[str]: Formatted timestamp or None if input is None
    """
    if timestamp is None:
        return None
        
    try:
        if isinstance(timestamp, str):
            # Try to parse as ISO format
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime(format_str)
        elif isinstance(timestamp, datetime):
            return timestamp.strftime(format_str)
        else:
            logger.warning(f"Unsupported timestamp type: {type(timestamp)}")
            return str(timestamp)
    except Exception as e:
        logger.error(f"Error formatting timestamp: {str(e)}")
        return str(timestamp)


def format_alert_for_export(
    alert: Dict[str, Any], 
    include_details: bool = False,
    format_timestamps: bool = True
) -> Dict[str, Any]:
    """
    Format an alert for export (e.g., to CSV or JSON).
    
    Args:
        alert: Alert data to format
        include_details: Whether to include detailed information
        format_timestamps: Whether to format timestamps as strings
        
    Returns:
        Dict[str, Any]: Formatted alert data
    """
    result = {
        "id": alert.get("id"),
        "entity_type": alert.get("entity_type"),
        "entity_id": alert.get("entity_id"),
        "alert_type": alert.get("alert_type"),
        "severity": alert.get("severity"),
        "message": alert.get("message"),
        "status": alert.get("status")
    }
    
    # Handle timestamps
    if format_timestamps:
        for ts_field in ["created_at", "updated_at", "resolved_at", "acknowledged_at"]:
            if ts_field in alert:
                result[ts_field] = format_timestamp(alert.get(ts_field))
    else:
        for ts_field in ["created_at", "updated_at", "resolved_at", "acknowledged_at"]:
            if ts_field in alert:
                result[ts_field] = alert.get(ts_field)
                
    # Include details if requested
    if include_details and "details" in alert:
        try:
            if isinstance(alert["details"], str):
                # Try to parse JSON string
                details = json.loads(alert["details"])
                result["details"] = sanitize_alert_data(details)
            elif isinstance(alert["details"], dict):
                result["details"] = sanitize_alert_data(alert["details"])
        except Exception as e:
            logger.error(f"Error parsing alert details: {str(e)}")
            
    return result
