"""
Payment plugin for Kaapi.

This plugin provides comprehensive payment processing functionality, including:
- Multiple payment providers (M-Pesa, Flutterwave, Stripe, PayPal, etc.)
- Support for African payment methods
- Multi-user approval workflows
- Full payment lifecycle support
- Refund functionality (full and partial)
- Recurring payments and subscriptions
- Notification system
"""
import logging
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import Base, engine, get_db
from app.core.config import settings
from app.core.security import get_current_active_user
from app.plugins.advanced_auth.models import User

from .models.payment import PaymentDB, PaymentApprovalStepDB, PaymentTransactionDB, PaymentRefundDB
from .models.payment import PaymentCreate, PaymentResponse
from .routes.payment_routes import router as payments_router
from .routes.webhook_routes import router as webhook_router
from .routes.refund_routes import router as refund_router
from .routes.subscription_routes import router as subscription_router
from .providers.provider_factory import PaymentProviderFactory
from .utils.config import load_payment_config, init_payment_settings
from .tests.test_providers import register_test_routes
from .utils.payment_service import (
    get_payments,
    get_payment_by_id,
    create_payment_service
)
from .workflows.approval_workflow import payment_approval_workflow


# Setup logging
logger = logging.getLogger("kaapi.payment")

def get_router() -> APIRouter:
    """
    Returns the main router for the payment plugin.
    """
    router = APIRouter()
    
    # Créer le routeur principal pour les opérations de base sur les paiements
    main_router = APIRouter()
    
    # Ajouter les endpoints de base au routeur principal
    @main_router.get("/", response_model=List[PaymentResponse])
    async def list_payments(
        skip: int = 0, 
        limit: int = 100,
        status: Optional[str] = None,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
    ):
        """List all payments with optional filtering by status."""
        return get_payments(db, current_user, skip, limit, status)

    @main_router.post("/", response_model=PaymentResponse)
    async def create_payment(
        payment: PaymentCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
    ):
        """Create a new payment."""
        return create_payment_service(db, payment, current_user)

    @main_router.get("/{payment_id}", response_model=PaymentResponse)
    async def get_payment(
        payment_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
    ):
        """Get details of a specific payment."""
        return get_payment_by_id(db, payment_id, current_user)
    
    # Register test routes if in test mode
    test_router = None
    if settings.ENVIRONMENT.lower() in ["test", "development"]:
        test_router = APIRouter(prefix="/test")
        register_test_routes(test_router)
        logger.info("Registered payment test routes")

    # Organiser les sous-routeurs avec des préfixes et tags clairs
    # 1. Inclure les opérations de base dans le routeur principal
    router.include_router(main_router)
    
    # 2. Inclure les autres sous-routeurs avec préfixes pour éviter les doublons
    router.include_router(
        payments_router, 
        prefix="/operations"
    )
    
    router.include_router(
        webhook_router, 
        prefix="/webhooks",
    )
    
    router.include_router(
        refund_router, 
        prefix="/refunds",
    )
    
    router.include_router(
        subscription_router, 
        prefix="/subscriptions",
    )
    
    # 3. Ajouter les routes de test si nécessaire
    if test_router:
        router.include_router(test_router)

    return router

# Initialize the router
payment_router = get_router()