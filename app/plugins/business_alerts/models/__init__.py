"""
Business alerts models.

This module contains the database models for the business alerts plugin.
"""

from .alert import BusinessAlertDB
from .alert_rule import AlertRuleDB

__all__ = ["BusinessAlertDB", "AlertRuleDB"]
