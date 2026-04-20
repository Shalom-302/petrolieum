# app/plugins/advanced_audit/__init__.py

from sqlalchemy.orm import Session
from sqlalchemy import func
from .metrics import AUDIT_EVENTS_COUNTER, AUDIT_EVENTS_BY_RESOURCE, AUDIT_EVENTS_BY_ACTION, LAST_AUDIT_EVENT_TIMESTAMP
from .models import AuditLog
import time

def initialize_audit_metrics(db: Session):
    """Initialize Prometheus metrics based on existing audit logs in the database."""
    print(" Initializing Advanced Audit metrics...")
    
    # Reset all gauges
    AUDIT_EVENTS_BY_RESOURCE._metrics.clear()
    AUDIT_EVENTS_BY_ACTION._metrics.clear()
    
    try:
        # Count total events
        total_events = db.query(func.count(AuditLog.id)).scalar() or 0
        print(f" Total audit events found: {total_events}")
    except Exception as e:
        # This is likely due to the table not existing yet, which is expected if migrations haven't been run
        print(f" ⚠️ Could not count audit events: {e}")
        print(" ⚠️ This is normal if migrations have not been run yet.")
        # Continue with default values
        total_events = 0
    
    # Reset counters
    AUDIT_EVENTS_COUNTER._metrics.clear()
    
    try:
        # Count events by resource and action combinations
        resource_action_counts = db.query(
            AuditLog.resource, 
            AuditLog.action, 
            func.count(AuditLog.id)
        ).group_by(AuditLog.resource, AuditLog.action).all()
    except Exception:
        # Si la requête échoue, utilisez une liste vide
        resource_action_counts = []
    
    # Process all resource/action combinations
    for resource, action, count in resource_action_counts:
        print(f" Resource: {resource}, Action: {action}, Count: {count}")
        # Increment counter for each resource/action combination
        AUDIT_EVENTS_COUNTER.labels(resource=resource, action=action).inc(count)
    
    # Recount events by resource after resetting counters
    resource_counts = db.query(AuditLog.resource, func.count(AuditLog.id)).group_by(AuditLog.resource).all()
    for resource, count in resource_counts:
        print(f" Setting resource gauge for {resource}: {count}")
        AUDIT_EVENTS_BY_RESOURCE.labels(resource=resource).set(count)
    
    # Recount events by action after resetting counters
    action_counts = db.query(AuditLog.action, func.count(AuditLog.id)).group_by(AuditLog.action).all()
    for action, count in action_counts:
        print(f" Setting action gauge for {action}: {count}")
        AUDIT_EVENTS_BY_ACTION.labels(action=action).set(count)
    
    # Set last event timestamp
    latest_event = db.query(AuditLog).order_by(AuditLog.created_at.desc()).first()
    if latest_event:
        # Convert datetime to timestamp
        timestamp = latest_event.created_at.timestamp()
        LAST_AUDIT_EVENT_TIMESTAMP.set(timestamp)
    else:
        # If no events, set to current time
        LAST_AUDIT_EVENT_TIMESTAMP.set(time.time())
    
    print(f" Advanced Audit metrics initialized")
