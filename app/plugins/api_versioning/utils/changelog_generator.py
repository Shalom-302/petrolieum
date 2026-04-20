"""
Utility functions for generating changelogs between API versions.

This module provides functions to generate human-readable changelogs that 
describe changes between different API versions.
"""

import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.plugins.api_versioning.models import APIVersion, APIEndpoint, APIChange


logger = logging.getLogger(__name__)


def generate_changelog(
    from_version_id: int,
    to_version_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    Generate a changelog between two API versions.
    
    Args:
        from_version_id: ID of the previous version
        to_version_id: ID of the new version
        db: Database session
        
    Returns:
        Changelog as a dictionary
    """
    # Get version information
    from_version = db.query(APIVersion).filter(APIVersion.id == from_version_id).first()
    to_version = db.query(APIVersion).filter(APIVersion.id == to_version_id).first()
    
    if not from_version or not to_version:
        logger.error(f"One or both versions not found: {from_version_id}, {to_version_id}")
        return {
            "error": "One or both versions not found",
            "from_version_id": from_version_id,
            "to_version_id": to_version_id
        }
    
    # Get all changes between these versions
    changes = db.query(APIChange).filter(
        APIChange.previous_version_id == from_version_id,
        APIChange.new_version_id == to_version_id
    ).all()
    
    # Organize changes by type
    added = []
    modified = []
    removed = []
    
    for change in changes:
        if change.change_type == "added":
            added.append({
                "path": change.endpoint_path,
                "description": change.description
            })
        elif change.change_type == "modified":
            modified.append({
                "path": change.endpoint_path,
                "description": change.description
            })
        elif change.change_type == "removed":
            removed.append({
                "path": change.endpoint_path,
                "description": change.description
            })
    
    # If there are no explicit changes, try to infer changes by comparing endpoints
    if not changes:
        added, modified, removed = infer_changes_from_endpoints(from_version_id, to_version_id, db)
    
    # Build changelog
    changelog = {
        "from_version": from_version.version,
        "to_version": to_version.version,
        "summary": f"Changes from {from_version.version} to {to_version.version}",
        "added": added,
        "modified": modified,
        "removed": removed
    }
    
    return changelog


def infer_changes_from_endpoints(
    from_version_id: int,
    to_version_id: int,
    db: Session
) -> tuple:
    """
    Infer changes between versions by comparing endpoints.
    
    Args:
        from_version_id: ID of the previous version
        to_version_id: ID of the new version
        db: Database session
        
    Returns:
        Tuple of (added, modified, removed) lists of endpoints
    """
    # Get all endpoints for the previous version
    prev_endpoints = db.query(APIEndpoint).filter(
        APIEndpoint.version_id == from_version_id
    ).all()
    
    # Get all endpoints for the new version
    new_endpoints = db.query(APIEndpoint).filter(
        APIEndpoint.version_id == to_version_id
    ).all()
    
    # Create dictionaries for easier comparison
    prev_dict = {f"{ep.method} {ep.path}": ep for ep in prev_endpoints}
    new_dict = {f"{ep.method} {ep.path}": ep for ep in new_endpoints}
    
    # Find added endpoints
    added = []
    for key, endpoint in new_dict.items():
        if key not in prev_dict:
            added.append({
                "path": endpoint.path,
                "method": endpoint.method,
                "description": "New endpoint"
            })
    
    # Find removed endpoints
    removed = []
    for key, endpoint in prev_dict.items():
        if key not in new_dict:
            removed.append({
                "path": endpoint.path,
                "method": endpoint.method,
                "description": "Endpoint removed"
            })
    
    # Find potentially modified endpoints
    modified = []
    for key, new_ep in new_dict.items():
        if key in prev_dict:
            prev_ep = prev_dict[key]
            # Very basic comparison - in reality, you would need to do more sophisticated 
            # comparison of parameters, response models, etc.
            if new_ep.handler_module != prev_ep.handler_module or \
               new_ep.handler_function != prev_ep.handler_function or \
               new_ep.parameters != prev_ep.parameters:
                modified.append({
                    "path": new_ep.path,
                    "method": new_ep.method,
                    "description": "Endpoint implementation changed"
                })
    
    return added, modified, removed


def get_detailed_endpoint_changes(
    endpoint_path: str,
    from_version_id: int,
    to_version_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    Get detailed changes for a specific endpoint between versions.
    
    Args:
        endpoint_path: Path of the endpoint
        from_version_id: ID of the previous version
        to_version_id: ID of the new version
        db: Database session
        
    Returns:
        Detailed changes as a dictionary
    """
    # Get versions
    from_version = db.query(APIVersion).filter(APIVersion.id == from_version_id).first()
    to_version = db.query(APIVersion).filter(APIVersion.id == to_version_id).first()
    
    if not from_version or not to_version:
        return {"error": "One or both versions not found"}
    
    # Find the endpoint in both versions (assuming method is part of the path)
    parts = endpoint_path.split(' ', 1)
    method = parts[0] if len(parts) > 1 else None
    path = parts[1] if len(parts) > 1 else endpoint_path
    
    # Query for the endpoint in both versions
    prev_endpoint = None
    new_endpoint = None
    
    if method:
        prev_endpoint = db.query(APIEndpoint).filter(
            APIEndpoint.version_id == from_version_id,
            APIEndpoint.path == path,
            APIEndpoint.method == method
        ).first()
        
        new_endpoint = db.query(APIEndpoint).filter(
            APIEndpoint.version_id == to_version_id,
            APIEndpoint.path == path,
            APIEndpoint.method == method
        ).first()
    else:
        # Try to find any endpoint with this path
        prev_endpoint = db.query(APIEndpoint).filter(
            APIEndpoint.version_id == from_version_id,
            APIEndpoint.path == path
        ).first()
        
        new_endpoint = db.query(APIEndpoint).filter(
            APIEndpoint.version_id == to_version_id,
            APIEndpoint.path == path
        ).first()
    
    # Determine change type
    change_type = "unknown"
    description = ""
    
    if prev_endpoint and new_endpoint:
        change_type = "modified"
        changes = []
        
        # Compare fields
        if prev_endpoint.handler_module != new_endpoint.handler_module or \
           prev_endpoint.handler_function != new_endpoint.handler_function:
            changes.append("Implementation changed")
        
        if prev_endpoint.parameters != new_endpoint.parameters:
            changes.append("Parameters changed")
        
        if prev_endpoint.is_active != new_endpoint.is_active:
            changes.append(f"Status changed: {'active' if new_endpoint.is_active else 'inactive'}")
        
        description = ", ".join(changes) or "No significant changes detected"
    
    elif not prev_endpoint and new_endpoint:
        change_type = "added"
        description = "New endpoint added"
    
    elif prev_endpoint and not new_endpoint:
        change_type = "removed"
        description = "Endpoint removed"
    
    # Get any explicit change records
    changes = db.query(APIChange).filter(
        APIChange.previous_version_id == from_version_id,
        APIChange.new_version_id == to_version_id,
        APIChange.endpoint_path == endpoint_path
    ).all()
    
    # Build response
    result = {
        "endpoint": endpoint_path,
        "from_version": from_version.version,
        "to_version": to_version.version,
        "change_type": change_type,
        "description": description,
        "recorded_changes": [
            {
                "type": change.change_type,
                "description": change.description
            }
            for change in changes
        ]
    }
    
    # Add endpoint details if available
    if prev_endpoint:
        result["previous_endpoint"] = {
            "path": prev_endpoint.path,
            "method": prev_endpoint.method,
            "handler": f"{prev_endpoint.handler_module}.{prev_endpoint.handler_function}",
            "is_active": prev_endpoint.is_active,
            "parameters": prev_endpoint.parameters
        }
    
    if new_endpoint:
        result["new_endpoint"] = {
            "path": new_endpoint.path,
            "method": new_endpoint.method,
            "handler": f"{new_endpoint.handler_module}.{new_endpoint.handler_function}",
            "is_active": new_endpoint.is_active,
            "parameters": new_endpoint.parameters
        }
    
    return result
