"""
Integration module for the API versioning plugin.

This module provides functions to integrate the API versioning plugin
with the main FastAPI application. It focuses on tracking API changes
for changelog purposes rather than managing multiple active versions.
"""

from fastapi import FastAPI, Depends, Request, Response
from sqlalchemy.orm import Session
from typing import Callable, Dict, Any, Optional

from app.core.db import get_db
from .models import APIVersion
from .utils.database import get_current_version


def register_with_main_app(app: FastAPI):
    """
    Registers the API versioning plugin with the main application.
    
    This function sets up the necessary middleware and event handlers
    to track API changes for changelog purposes.
    
    Args:
        app: The FastAPI application to register with
    """
    # Add middleware to ensure we have the current API version info
    @app.middleware("http")
    async def api_version_middleware(request: Request, call_next: Callable) -> Response:
        """
        Middleware that adds current API version info to the request state.
        
        This middleware adds the current API version information to the request state
        for use in generating documentation and changelogs.
        
        Args:
            request: The incoming request
            call_next: The next middleware handler
            
        Returns:
            The response from the next middleware handler
        """
        # Get the current API version from the database
        db = next(get_db())
        try:
            current_version = get_current_version(db)
            # Add the current version to the request state for use in handlers
            request.state.api_version = current_version
        except Exception as e:
            # If we can't get the current version, just continue without it
            request.state.api_version = None
        finally:
            db.close()
        
        # Call the next middleware and return the response
        response = await call_next(request)
        return response


def register_endpoint(
    app: FastAPI,
    path: str,
    method: str,
    handler_module: str,
    handler_function: str,
    parameters: Optional[Dict[str, Any]] = None,
    response_model: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None
):
    """
    Register an API endpoint in the current version.
    
    This function adds a record of an API endpoint to the current version,
    allowing the system to track changes when new versions are created.
    
    Args:
        app: The FastAPI application
        path: The endpoint path
        method: The HTTP method (GET, POST, etc.)
        handler_module: The module containing the handler function
        handler_function: The name of the handler function
        parameters: Optional parameters schema
        response_model: Optional response model schema
        db: Optional database session (if not provided, one will be created)
    """
    if db is None:
        db = next(get_db())
        close_db = True
    else:
        close_db = False
    
    try:
        # Get the current API version
        current_version = get_current_version(db)
        
        # Add the endpoint to the database
        if current_version:
            from .crud import create_api_endpoint
            create_api_endpoint(
                db,
                path=path,
                method=method,
                version_id=current_version.id,
                description=f"{method} {path}",
                handler_module=handler_module,
                handler_function=handler_function,
                parameters=parameters,
                response_model=response_model
            )
    finally:
        if close_db:
            db.close()


def register_change(
    previous_version_id: int,
    new_version_id: int,
    endpoint_path: str,
    change_type: str,
    description: str,
    details: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None
):
    """
    Register a change between API versions.
    
    This function adds a record of a change to an API endpoint between versions,
    which can be used to generate changelogs.
    
    Args:
        previous_version_id: The ID of the previous API version
        new_version_id: The ID of the new API version
        endpoint_path: The path of the affected endpoint
        change_type: The type of change ('added', 'modified', 'removed')
        description: A human-readable description of the change
        details: Optional detailed information about the change
        db: Optional database session (if not provided, one will be created)
    """
    if db is None:
        db = next(get_db())
        close_db = True
    else:
        close_db = False
    
    try:
        from .crud import create_api_change
        create_api_change(
            db,
            previous_version_id=previous_version_id,
            new_version_id=new_version_id,
            endpoint_path=endpoint_path,
            change_type=change_type,
            description=description,
            details=details
        )
    finally:
        if close_db:
            db.close()


def generate_changelog(version_id: Optional[int] = None, db: Optional[Session] = None):
    """
    Generate a changelog for the specified version or all versions.
    
    This function generates a changelog based on the recorded changes
    between API versions.
    
    Args:
        version_id: Optional ID of the version to generate changelog for
                   (if None, generates for all versions)
        db: Optional database session (if not provided, one will be created)
        
    Returns:
        A dictionary containing the changelog information
    """
    if db is None:
        db = next(get_db())
        close_db = True
    else:
        close_db = False
    
    try:
        from .crud import get_api_changes
        if version_id:
            changes = get_api_changes(db, new_version_id=version_id)
            # TODO: Format changes into a changelog
            return {"version_id": version_id, "changes": changes}
        else:
            # Get all versions and their changes
            # TODO: Format changes into a complete changelog
            return {"message": "Full changelog generation not yet implemented"}
    finally:
        if close_db:
            db.close()
