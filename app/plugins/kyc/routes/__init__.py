"""
API routes for the KYC plugin.
"""

from .verification import get_verification_router
from .profile import get_profile_router
from .region import get_region_router
from .simplified import get_simplified_kyc_router
from .dashboard import get_dashboard_router
