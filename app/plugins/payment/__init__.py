"""
Payment Plugin for Kaapi

This plugin provides comprehensive payment integration with multiple payment providers
worldwide, including specialized solutions for African markets. It supports complex
payment workflows with multi-user approval processes.
"""

from .main import payment_router

__all__ = ["payment_router"]
