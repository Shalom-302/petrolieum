"""
KYC (Know Your Customer) Plugin for Kaapi.

Provides verification and identity management capabilities with adaptable approaches
for regions with different infrastructure levels.
"""

from .main import kyc_admin_router, kyc_api_router

__all__ = ["kyc_admin_router", "kyc_api_router"]
