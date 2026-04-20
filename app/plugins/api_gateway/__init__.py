"""
API Gateway Plugin.

This plugin facilitates secure API exposure and documentation generation
for integrating with external applications.
"""

from .main import api_gateway_router

__all__ = ["api_gateway_router"]
