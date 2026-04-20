"""
Webhook routes for the payment plugin.

This module contains routes for handling webhooks from payment providers.
"""
import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, Request, Body
from sqlalchemy.orm import Session

from app.core.db import get_db
from ..utils.webhook_handler import handle_webhook

logger = logging.getLogger("kaapi.payment.webhook_routes")

# Create router - no authentication for webhooks
router = APIRouter()

@router.post("/{provider}", response_model=Dict[str, Any])
async def payment_webhook(
    provider: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle webhooks from payment providers.
    
    This endpoint accepts webhooks from various payment providers
    and processes them according to the provider's format.
    
    It is generally unauthenticated, but webhook signatures are validated
    based on provider-specific methods.
    """
    return await handle_webhook(db, provider, request)
