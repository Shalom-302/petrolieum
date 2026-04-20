# app/plugins/advanced_audit/audit_table.py

from typing import List, Optional, Dict, Any, Type, Callable
from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import DeclarativeMeta
from .models import AuditLog
from .schemas import AuditLogCreate
import json

class TableAuditor:
    """
    Utility class to facilitate auditing of table modifications.
    It allows automatically tracing CREATE, UPDATE and DELETE operations on configured tables.
    """
    
    def __init__(self, db_session_factory: Callable[[], Session]):
        """
        Initialize the table auditor with a function to create database session.
        
        Args:
            db_session_factory: Callable that returns a new database session
        """
        self.db_session_factory = db_session_factory
        self.registered_models = {}
        
    def register_model(self, model: Type[DeclarativeMeta], primary_key: str = 'id', 
                      excluded_columns: List[str] = None, included_columns: List[str] = None,
                      resource_name: str = None):
        """
        Register a model for auditing.
        
        Args:
            model: The SQLAlchemy model to audit
            primary_key: The name of the primary key column (default 'id')
            excluded_columns: Columns to exclude from the audit
            included_columns: If provided, only these columns will be audited
            resource_name: Custom name for the resource in audit logs
        """
        if excluded_columns is None:
            excluded_columns = []
            
        # Exclude sensitive columns by default
        for col in ['password', 'password_hash', 'token', 'secret', 'key']:
            if col not in excluded_columns:
                excluded_columns.append(col)
                
        model_name = resource_name or model.__tablename__
        
        self.registered_models[model.__name__] = {
            'model': model,
            'primary_key': primary_key,
            'excluded_columns': excluded_columns,
            'included_columns': included_columns,
            'resource_name': model_name
        }
        
        # Register SQLAlchemy events for this model
        self._register_events(model)
        
        print(f"Audit enabled for model: {model.__name__} as resource '{model_name}'")
        
    def _register_events(self, model: Type[DeclarativeMeta]):
        """
        Register SQLAlchemy events for a model.
        """
        # Event after insertion (CREATE)
        event.listen(model, 'after_insert', self._after_insert)
        
        # Event after update (UPDATE)
        event.listen(model, 'after_update', self._after_update)
        
        # Event after deletion (DELETE)
        event.listen(model, 'after_delete', self._after_delete)
        
    def _create_audit_log(self, action: str, resource: str, details: Optional[str] = None,
                         user_id: Optional[int] = None):
        """
        Create an audit log entry.
        """
        try:
            # Create a new session
            db = self.db_session_factory()
            
            # Create audit log entry
            audit_data = AuditLogCreate(
                user_id=user_id,
                action=action,
                resource=resource,
                details=details
            )
            
            log = AuditLog(
                user_id=audit_data.user_id,
                action=audit_data.action,
                resource=audit_data.resource,
                details=audit_data.details
            )
            
            db.add(log)
            db.commit()
            
        except Exception as e:
            print(f"Error creating audit log: {str(e)}")
            if db:
                db.rollback()
        finally:
            if db:
                db.close()
    
    def _get_model_config(self, model_instance):
        """
        Get the audit configuration for a model instance.
        """
        model_name = model_instance.__class__.__name__
        return self.registered_models.get(model_name)
    
    def _get_object_data(self, obj, config: Dict):
        """
        Extract relevant object data based on the configuration.
        """
        data = {}
        
        # If included_columns is specified, only include these columns
        include_list = config.get('included_columns')
        exclude_list = config.get('excluded_columns', [])
        
        for column in obj.__table__.columns:
            column_name = column.name
            
            # Check if the column should be included
            if include_list is not None and column_name not in include_list:
                continue
                
            # Check if the column should be excluded
            if column_name in exclude_list:
                continue
                
            # Add the value to the data object
            try:
                value = getattr(obj, column_name)
                
                # Convert complex types to strings
                if hasattr(value, '__dict__'):
                    data[column_name] = str(value)
                else:
                    data[column_name] = value
            except:
                data[column_name] = "ERROR: Could not retrieve value"
        
        return data
    
    def _after_insert(self, mapper, connection, target):
        """
        Event handler after insertion.
        """
        config = self._get_model_config(target)
        if not config:
            return
            
        # Extract the object ID
        primary_key = config['primary_key']
        object_id = getattr(target, primary_key)
        
        # Get the object data
        data = self._get_object_data(target, config)
        
        # Create the audit log details
        details = json.dumps({
            'id': object_id,
            'data': data
        })
        
        # Create the audit log
        self._create_audit_log(
            action='CREATE',
            resource=config['resource_name'],
            details=details
        )
    
    def _after_update(self, mapper, connection, target):
        """
        Event handler after update.
        """
        config = self._get_model_config(target)
        if not config:
            return
            
        # Extract the object ID
        primary_key = config['primary_key']
        object_id = getattr(target, primary_key)
        
        # Get the object changes (if available via SQLAlchemy history)
        changes = {}
        for attr in target.__mapper__.attrs:
            if hasattr(attr.history, 'has_changes') and attr.history.has_changes():
                changes[attr.key] = {
                    'old': attr.history.deleted[0] if attr.history.deleted else None,
                    'new': attr.history.added[0] if attr.history.added else None
                }
        
        # If no changes are detected, get all object data
        if not changes:
            changes = self._get_object_data(target, config)
        
        # Create the audit log details
        details = json.dumps({
            'id': object_id,
            'changes': changes
        })
        
        # Create the audit log
        self._create_audit_log(
            action='UPDATE',
            resource=config['resource_name'],
            details=details
        )
    
    def _after_delete(self, mapper, connection, target):
        """
        Event handler after deletion.
        """
        config = self._get_model_config(target)
        if not config:
            return
            
        # Extract the object ID
        primary_key = config['primary_key']
        object_id = getattr(target, primary_key)
        
        # Get the object data before deletion
        data = self._get_object_data(target, config)
        
        # Create the audit log details
        details = json.dumps({
            'id': object_id,
            'data': data
        })
        
        # Create the audit log
        self._create_audit_log(
            action='DELETE',
            resource=config['resource_name'],
            details=details
        )
        
    def manually_log(self, action: str, resource: str, object_id: Any, data: Dict = None, 
                    user_id: Optional[int] = None):
        """
        Utility function to manually create an audit log.
        
        Args:
            action: Action performed (e.g., 'VIEW', 'EXPORT', 'CUSTOM_ACTION')
            resource: Resource type (e.g., 'user', 'file')
            object_id: ID of the object concerned
            data: Additional data to log
            user_id: ID of the user who performed the action
        """
        details = json.dumps({
            'id': object_id,
            'data': data or {}
        })
        
        self._create_audit_log(
            action=action,
            resource=resource,
            details=details,
            user_id=user_id
        )
