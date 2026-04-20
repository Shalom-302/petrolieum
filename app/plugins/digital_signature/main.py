"""
Digital Signature and Timestamping plugin main module.

This module serves as the entry point for the digital signature plugin,
providing initialization and configuration functionality for secure
document signing and timestamping.
"""

import logging
from fastapi import FastAPI, APIRouter

from app.plugins.digital_signature.routes.signature import get_signature_router
from app.plugins.digital_signature.routes.timestamp import get_timestamp_router
from app.plugins.digital_signature.routes.verification import get_verification_router
from app.plugins.digital_signature.utils.security import initialize_signature_security

logger = logging.getLogger(__name__)


def get_router():
    """
    Get the Digital Signature and Timestamping router.
    
    Returns:
        APIRouter: Configured router for the digital signature plugin
    """
    router = APIRouter()
    
    # Add sub-routers
    signature_router = get_signature_router()
    timestamp_router = get_timestamp_router()
    verification_router = get_verification_router()
    
    router.include_router(
        signature_router,
        prefix="/sign"
    )
    
    router.include_router(
        timestamp_router,
        prefix="/timestamp"
    )
    
    router.include_router(
        verification_router,
        prefix="/verify"
    )
    
    return router


def init_app(app: FastAPI):
    """
    Initialize the digital signature plugin with the FastAPI application.
    
    Args:
        app: FastAPI application
    
    Returns:
        dict: Plugin metadata
    """
    # Initialize security components
    initialize_signature_security()
    
    # Include the router in the main app
    app.include_router(get_router(), prefix="/digital-signature")
    
    logger.info("Digital signature plugin initialized")
    
    return {
        "name": "digital_signature",
        "description": "Digital Signature and Timestamping",
        "version": "1.0.0"
    }


# Create router instance
router = get_router()

# Export the router
digital_signature_router = router