"""
Alert detector service.

This module contains the AlertDetector service responsible for identifying
business situations that should generate alerts, based on defined rules.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import create_default_encryption
from app.plugins.business_alerts.models.alert import BusinessAlertDB
from app.plugins.business_alerts.models.alert_rule import AlertRuleDB

logger = logging.getLogger(__name__)


class AlertDetector:
    """
    Service for detecting conditions that should trigger business alerts.
    
    This service is responsible for checking various business conditions
    and generating alerts when those conditions are met. It encapsulates
    the logic for evaluating alert rules against the database.
    """
    
    def __init__(self, db: Session, encryption_handler=None):
        """
        Initialize the alert detector service.
        
        Args:
            db: Database session
            encryption_handler: Optional encryption handler for sensitive data
        """
        self.db = db
        self.encryption_handler = encryption_handler or create_default_encryption()
        self.logger = logging.getLogger(__name__)
    
    def check_missing_financial_data(self, year: int = None) -> int:
        """
        Detect companies with missing financial data for a specific year.
        
        Args:
            year: Year to check for missing financial data (defaults to current year)
            
        Returns:
            int: Number of alerts created
            
        Raises:
            Exception: If an error occurs during detection
        """
        current_year = year or datetime.now().year
        
        # Log the detection process initiation
        self.logger.info(f"Checking for missing financial data for year {current_year}")
        
        # Execute the detection logic with secure error handling
        try:
            # SQL query to find companies without financial data for the specified year
            # This is an example query - would need to be adapted to actual schema
            companies_query = """
            SELECT c.id, c.name FROM companies c 
            LEFT JOIN financial_data f ON c.id = f.company_id AND f.year = :year
            WHERE c.status = 'active' AND f.id IS NULL
            """
            
            # Execute the query with proper parameter binding for security
            companies = self.db.execute(
                text(companies_query), 
                {"year": current_year}
            ).fetchall()
            
            # Create alerts for companies with missing data
            self._create_alerts_for_entities(
                companies, 
                "company", 
                "missing_financial_data", 
                f"Financial data for {current_year} not provided",
                "warning"
            )
            
            # Log the completion of the check
            self.logger.info(f"Completed financial data check: identified {len(companies)} companies with missing data")
            return len(companies)
            
        except Exception as e:
            # Log and re-raise the exception
            self.logger.error(f"Error detecting missing financial data: {str(e)}")
            raise
    
    def check_expiring_documents(self, days_until_expiry: int = 30) -> int:
        """
        Detect entities with documents that will expire soon.
        
        Args:
            days_until_expiry: Number of days ahead to check for expiring documents
            
        Returns:
            int: Number of alerts created
            
        Raises:
            Exception: If an error occurs during detection
        """
        # Log the detection process initiation
        self.logger.info(f"Checking for documents expiring within {days_until_expiry} days")
        
        try:
            # Example query to find expiring documents
            # This would need to be adapted to actual schema
            expiring_query = """
            SELECT d.id, d.entity_id, d.entity_type, e.name, d.document_type, d.expiry_date 
            FROM documents d
            JOIN entities e ON d.entity_id = e.id AND d.entity_type = e.type
            WHERE d.status = 'active' 
            AND d.expiry_date IS NOT NULL
            AND d.expiry_date BETWEEN CURRENT_DATE AND (CURRENT_DATE + INTERVAL :days DAY)
            """
            
            # Execute the query with proper parameter binding
            expiring_docs = self.db.execute(
                text(expiring_query),
                {"days": days_until_expiry}
            ).fetchall()
            
            # Process each expiring document
            alert_count = 0
            for doc in expiring_docs:
                # Determine alert severity based on expiry timeframe
                expiry_delta = (doc.expiry_date - datetime.now().date()).days
                severity = "critical" if expiry_delta <= 7 else "warning"
                
                # Create alert with encrypted details
                alert = BusinessAlertDB(
                    entity_id=doc.entity_id,
                    entity_type=doc.entity_type,
                    alert_type="expiring_document",
                    severity=severity,
                    message=f"{doc.document_type} expires in {expiry_delta} days",
                    details=self.encryption_handler.encrypt_data({
                        "entity_name": doc.name,
                        "document_id": doc.id,
                        "document_type": doc.document_type,
                        "expiry_date": doc.expiry_date.isoformat(),
                        "days_remaining": expiry_delta
                    })
                )
                self.db.add(alert)
                alert_count += 1
            
            # Commit all changes at once for efficiency
            self.db.commit()
            
            # Log the completion of the check
            self.logger.info(f"Completed expiring documents check: identified {alert_count} expiring documents")
            return alert_count
            
        except Exception as e:
            # Log and re-raise the exception
            self.logger.error(f"Error detecting expiring documents: {str(e)}")
            raise
    
    def evaluate_rule(self, rule_id: str) -> int:
        """
        Evaluate a specific alert rule and generate alerts.
        
        Args:
            rule_id: ID of the rule to evaluate
            
        Returns:
            int: Number of alerts created
            
        Raises:
            Exception: If an error occurs during rule evaluation
        """
        # Get the rule from the database
        rule = self.db.query(AlertRuleDB).filter(AlertRuleDB.id == rule_id).first()
        if not rule:
            self.logger.warning(f"Rule {rule_id} not found")
            return 0
            
        if not rule.is_active:
            self.logger.info(f"Rule {rule_id} is inactive, skipping evaluation")
            return 0
            
        self.logger.info(f"Evaluating rule: {rule.name} (ID: {rule.id})")
        
        try:
            # Determine rule type and execute appropriate evaluation method
            if rule.is_sql_condition:
                return self._evaluate_sql_rule(rule)
            elif rule.is_python_condition:
                return self._evaluate_python_rule(rule)
            else:
                self.logger.warning(f"Unsupported rule condition type for rule {rule.id}")
                return 0
                
        except Exception as e:
            # Log the error but don't halt the entire detection process
            self.logger.error(f"Error evaluating rule {rule.id}: {str(e)}")
            return 0
            
    def _evaluate_sql_rule(self, rule: AlertRuleDB) -> int:
        """
        Evaluate a rule with a SQL condition.
        
        Args:
            rule: The rule to evaluate
            
        Returns:
            int: Number of alerts created
        """
        # Extract the SQL query from the rule condition
        sql_query = rule.condition.get("query", "")
        if not sql_query:
            self.logger.warning(f"Rule {rule.id} has empty SQL query")
            return 0
            
        # Execute the query with proper security measures
        try:
            params = rule.condition.get("parameters", {})
            results = self.db.execute(text(sql_query), params).fetchall()
            
            # Create alerts for the results
            alerts_created = 0
            for result in results:
                # Extract entity information
                entity_id = getattr(result, "entity_id", None)
                entity_name = getattr(result, "entity_name", "Unknown entity")
                
                if not entity_id:
                    continue
                
                # Format message using template and result data
                message = self._format_message(rule.message_template, result)
                
                # Create the alert
                alert = BusinessAlertDB(
                    entity_id=entity_id,
                    entity_type=rule.entity_type,
                    alert_type=rule.alert_type,
                    severity=rule.severity,
                    message=message,
                    details=self.encryption_handler.encrypt_data({
                        "entity_name": entity_name,
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "detected_at": datetime.utcnow().isoformat(),
                        "result_data": {k: getattr(result, k, None) for k in result.keys()}
                    })
                )
                self.db.add(alert)
                alerts_created += 1
                
            self.db.commit()
            self.logger.info(f"SQL rule {rule.id} evaluation created {alerts_created} alerts")
            return alerts_created
            
        except Exception as e:
            self.logger.error(f"Error executing SQL for rule {rule.id}: {str(e)}")
            self.db.rollback()
            raise
            
    def _evaluate_python_rule(self, rule: AlertRuleDB) -> int:
        """
        Evaluate a rule with a Python code condition.
        
        Args:
            rule: The rule to evaluate
            
        Returns:
            int: Number of alerts created
            
        Note:
            This is a simplified implementation. In a production environment,
            executing arbitrary Python code would require robust sandboxing.
        """
        self.logger.info(f"Python rule evaluation not fully implemented for rule {rule.id}")
        return 0
    
    def _create_alerts_for_entities(self, entities, entity_type, alert_type, message, severity):
        """
        Create alerts for a list of entities.
        
        Args:
            entities: List of entities to create alerts for
            entity_type: Type of entity (company, user, etc.)
            alert_type: Type of alert (missing_financial_data, etc.)
            message: Alert message
            severity: Alert severity (critical, warning, info)
        """
        alerts_created = 0
        for entity in entities:
            # Check if an active alert of the same type already exists
            existing = self.db.query(BusinessAlertDB).filter(
                BusinessAlertDB.entity_id == entity.id,
                BusinessAlertDB.entity_type == entity_type,
                BusinessAlertDB.alert_type == alert_type,
                BusinessAlertDB.status != "resolved"
            ).first()
            
            if not existing:
                # Create a new alert with encrypted details
                alert = BusinessAlertDB(
                    entity_id=entity.id,
                    entity_type=entity_type,
                    alert_type=alert_type,
                    severity=severity,
                    message=message,
                    details=self.encryption_handler.encrypt_data({
                        "entity_name": entity.name,
                        "detected_at": datetime.utcnow().isoformat(),
                        "context": f"Annual check for {alert_type}"
                    })
                )
                self.db.add(alert)
                alerts_created += 1
                
        # Commit all changes at once for efficiency
        if alerts_created > 0:
            self.db.commit()
            self.logger.info(f"Created {alerts_created} alerts for {alert_type}")
            
        return alerts_created
        
    def _format_message(self, template: str, data) -> str:
        """
        Format a message template with data.
        
        Args:
            template: Message template with placeholders
            data: Data to format the template with
            
        Returns:
            str: Formatted message
        """
        try:
            # For named tuple or object-like data
            if hasattr(data, "_asdict"):
                return template.format(**data._asdict())
                
            # For SQLAlchemy result rows
            if hasattr(data, "keys"):
                return template.format(**{k: getattr(data, k) for k in data.keys()})
                
            # For dictionary data
            if isinstance(data, dict):
                return template.format(**data)
                
            # Default case
            return template
            
        except Exception as e:
            self.logger.error(f"Error formatting message: {str(e)}")
            return template
