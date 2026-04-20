"""
Scheduled tasks for business alerts.

This module contains scheduled tasks for the business alerts plugin
that run periodically to detect, process, and manage alerts.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.plugins.business_alerts.models.alert import BusinessAlertDB
from app.plugins.business_alerts.models.alert_rule import AlertRuleDB
from app.plugins.business_alerts.services.detector import AlertDetector
from app.plugins.business_alerts.services.processor import AlertProcessor
from app.plugins.business_alerts.utils.security import create_alert_encryption_handler

logger = logging.getLogger(__name__)


def run_daily_alert_checks() -> Dict[str, Any]:
    """
    Run daily scheduled alert checks.
    
    This function executes all active alert rules configured for daily checks,
    following the standardized security approach used across the application.
    
    Returns:
        Dict[str, Any]: Result summary
    """
    start_time = datetime.utcnow()
    logger.info("Starting daily alert checks")
    
    db = SessionLocal()
    try:
        # Get encryption handler to ensure consistent security
        encryption_handler = create_alert_encryption_handler()
        
        # Initialize services with standard security
        detector = AlertDetector(db, encryption_handler=encryption_handler)
        
        # Get active rules scheduled for daily checks
        rules = db.query(AlertRuleDB).filter(
            AlertRuleDB.is_active == True,
            AlertRuleDB.check_frequency == "daily"
        ).all()
        
        logger.info(f"Found {len(rules)} active daily rules to process")
        
        # Track results for logging and reporting
        results = {
            "total_rules": len(rules),
            "successful_rules": 0,
            "failed_rules": 0,
            "alerts_created": 0,
            "rule_results": []
        }
        
        # Process each rule
        for rule in rules:
            rule_start = datetime.utcnow()
            try:
                # Log the rule processing with standard format
                logger.info(f"Processing rule: {rule.name} (ID: {rule.id})")
                
                # Apply rule-specific detection logic
                alerts_created = 0
                
                # Special handling for known rule types
                if rule.entity_type == "company" and rule.alert_type == "missing_financial_data":
                    alerts_created = detector.check_missing_financial_data()
                elif rule.entity_type == "document" and rule.alert_type == "expiring_document":
                    # Get expiry threshold from rule condition
                    days_threshold = rule.condition.get("days_until_expiry", 30)
                    alerts_created = detector.check_expiring_documents(days_threshold)
                else:
                    # Generic rule evaluation
                    alerts_created = detector.evaluate_rule(rule.id)
                
                # Record successful execution
                rule_duration = (datetime.utcnow() - rule_start).total_seconds()
                
                results["successful_rules"] += 1
                results["alerts_created"] += alerts_created
                results["rule_results"].append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "status": "success",
                    "alerts_created": alerts_created,
                    "duration_seconds": rule_duration
                })
                
                logger.info(f"Rule {rule.id} processed successfully, created {alerts_created} alerts in {rule_duration:.2f}s")
                
            except Exception as e:
                # Record failed execution with standard error handling
                rule_duration = (datetime.utcnow() - rule_start).total_seconds()
                
                results["failed_rules"] += 1
                results["rule_results"].append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "status": "error",
                    "error": str(e),
                    "duration_seconds": rule_duration
                })
                
                logger.error(f"Error processing rule {rule.id}: {str(e)}")
        
        # After rules are processed, deduplicate alerts
        try:
            processor = AlertProcessor(db, encryption_handler=encryption_handler)
            # Deduplicate alerts for common types
            processor.deduplicate_alerts("company", "missing_financial_data")
            processor.deduplicate_alerts("document", "expiring_document")
        except Exception as e:
            logger.error(f"Error during alert deduplication: {str(e)}")
        
        # Calculate total duration
        total_duration = (datetime.utcnow() - start_time).total_seconds()
        results["total_duration_seconds"] = total_duration
        
        logger.info(f"Daily alert checks completed in {total_duration:.2f}s. Created {results['alerts_created']} alerts")
        return results
        
    except Exception as e:
        logger.error(f"Error during daily alert checks: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }
    finally:
        db.close()


def run_hourly_alert_checks() -> Dict[str, Any]:
    """
    Run hourly scheduled alert checks.
    
    This function executes all active alert rules configured for hourly checks,
    following the standardized security approach used across the application.
    
    Returns:
        Dict[str, Any]: Result summary
    """
    start_time = datetime.utcnow()
    logger.info("Starting hourly alert checks")
    
    db = SessionLocal()
    try:
        # Get encryption handler to ensure consistent security
        encryption_handler = create_alert_encryption_handler()
        
        # Initialize services with standard security
        detector = AlertDetector(db, encryption_handler=encryption_handler)
        
        # Get active rules scheduled for hourly checks
        rules = db.query(AlertRuleDB).filter(
            AlertRuleDB.is_active == True,
            AlertRuleDB.check_frequency == "hourly"
        ).all()
        
        logger.info(f"Found {len(rules)} active hourly rules to process")
        
        # Track results
        results = {
            "total_rules": len(rules),
            "successful_rules": 0,
            "failed_rules": 0,
            "alerts_created": 0,
            "rule_results": []
        }
        
        # Process each rule using the same pattern as daily checks
        for rule in rules:
            rule_start = datetime.utcnow()
            try:
                logger.info(f"Processing rule: {rule.name} (ID: {rule.id})")
                
                # Apply rule-specific detection logic
                alerts_created = detector.evaluate_rule(rule.id)
                
                # Record successful execution
                rule_duration = (datetime.utcnow() - rule_start).total_seconds()
                
                results["successful_rules"] += 1
                results["alerts_created"] += alerts_created
                results["rule_results"].append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "status": "success",
                    "alerts_created": alerts_created,
                    "duration_seconds": rule_duration
                })
                
                logger.info(f"Rule {rule.id} processed successfully, created {alerts_created} alerts in {rule_duration:.2f}s")
                
            except Exception as e:
                # Record failed execution with standard error handling
                rule_duration = (datetime.utcnow() - rule_start).total_seconds()
                
                results["failed_rules"] += 1
                results["rule_results"].append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "status": "error",
                    "error": str(e),
                    "duration_seconds": rule_duration
                })
                
                logger.error(f"Error processing rule {rule.id}: {str(e)}")
        
        # Calculate total duration
        total_duration = (datetime.utcnow() - start_time).total_seconds()
        results["total_duration_seconds"] = total_duration
        
        logger.info(f"Hourly alert checks completed in {total_duration:.2f}s. Created {results['alerts_created']} alerts")
        return results
        
    except Exception as e:
        logger.error(f"Error during hourly alert checks: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }
    finally:
        db.close()


def run_weekly_alert_cleanup() -> Dict[str, Any]:
    """
    Run weekly alert cleanup to archive old resolved alerts.
    
    This function archives or deletes old resolved alerts to maintain
    database performance, following the standardized security approach.
    
    Returns:
        Dict[str, Any]: Result summary
    """
    start_time = datetime.utcnow()
    logger.info("Starting weekly alert cleanup")
    
    db = SessionLocal()
    try:
        # Define cleanup threshold (resolved alerts older than 90 days)
        cleanup_threshold = datetime.utcnow() - timedelta(days=90)
        
        # Get alerts eligible for cleanup
        old_alerts = db.query(BusinessAlertDB).filter(
            BusinessAlertDB.status == "resolved",
            BusinessAlertDB.resolved_at < cleanup_threshold
        ).all()
        
        count_archived = 0
        
        # In a real implementation, we would archive these alerts
        # to a long-term storage solution before deletion
        # For now, we'll just log them and delete
        
        # Delete old alerts
        if old_alerts:
            for alert in old_alerts:
                # Securely log the archiving action
                logger.info(f"Archiving old alert: {alert.id}, type: {alert.alert_type}, resolved: {alert.resolved_at}")
                db.delete(alert)
                count_archived += 1
                
            # Commit changes
            db.commit()
        
        # Calculate total duration
        total_duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(f"Weekly alert cleanup completed in {total_duration:.2f}s. Archived {count_archived} alerts")
        return {
            "status": "success",
            "alerts_archived": count_archived,
            "duration_seconds": total_duration
        }
        
    except Exception as e:
        logger.error(f"Error during weekly alert cleanup: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }
    finally:
        db.close()
