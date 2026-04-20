"""
Database models for the API Gateway plugin.
"""

# Import the models to ensure they are registered with SQLAlchemy
from .api_key import ApiKeyDB, ApiPermissionDB
from .rate_limit import RateLimitDB
from .audit import ApiAuditLogDB
