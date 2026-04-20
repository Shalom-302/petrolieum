"""
API routes for the offline synchronization plugin.
"""

from .operations import get_operations_router
from .batches import get_batches_router
from .config import get_config_router
