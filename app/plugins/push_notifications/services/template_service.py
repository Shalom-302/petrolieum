"""
Template Service for Push Notifications

This module provides the template management service for the push notifications plugin,
implementing the standardized security approach.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.plugins.push_notifications.models.database import NotificationTemplate, NotificationCategory
from app.plugins.push_notifications.schemas.notification import (
    NotificationTemplateCreate, NotificationTemplateUpdate, 
    NotificationCategoryCreate, NotificationCategoryUpdate
)
from app.plugins.push_notifications.handlers.security_handler import SecurityHandler
from app.plugins.push_notifications.handlers.redis_handler import RedisHandler

logger = logging.getLogger(__name__)

class TemplateService:
    """
    Service for managing notification templates,
    implementing the standardized security approach.
    """
    
    def __init__(self, db: Session, security_handler: SecurityHandler,
                redis_handler: Optional[RedisHandler] = None):
        """
        Initialize the template service.
        
        Args:
            db: Database session
            security_handler: Security handler for encryption and validation
            redis_handler: Redis handler for caching and rate limiting
        """
        self.db = db
        self.security_handler = security_handler
        self.redis_handler = redis_handler
        logger.info("Template service initialized")
    
    def create_template(self, template_data: NotificationTemplateCreate) -> NotificationTemplate:
        """
        Create a new notification template.
        
        Args:
            template_data: Template data
            
        Returns:
            NotificationTemplate: Created template
        """
        try:
            # Validate the template data
            if not template_data.title_template or not template_data.body_template:
                raise ValueError("Title and body templates are required")
            
            # Check if category exists if provided
            if template_data.category_id:
                category = self.db.query(NotificationCategory).filter(
                    NotificationCategory.id == template_data.category_id
                ).first()
                
                if not category:
                    raise ValueError(f"Category not found: {template_data.category_id}")
            
            # Create template record
            template_id = str(uuid.uuid4())
            
            # Encrypt sensitive metadata if provided
            encrypted_metadata = None
            if template_data.metadata:
                encrypted_metadata = self.security_handler.encrypt_data(template_data.metadata)
            
            new_template = NotificationTemplate(
                id=template_id,
                name=template_data.name,
                title_template=template_data.title_template,
                body_template=template_data.body_template,
                data_template=template_data.data_template,
                category_id=template_data.category_id,
                metadata=encrypted_metadata,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                created_by=template_data.created_by,
                is_active=True
            )
            
            self.db.add(new_template)
            self.db.commit()
            
            # Log template creation with secure audit trail
            logger.info(f"Notification template created: {template_id}")
            
            # Cache template in Redis if available
            if self.redis_handler:
                cache_key = f"template:{template_id}"
                template_dict = {
                    "id": template_id,
                    "name": new_template.name,
                    "title_template": new_template.title_template,
                    "body_template": new_template.body_template,
                    "data_template": new_template.data_template,
                    "category_id": new_template.category_id,
                    "is_active": new_template.is_active
                }
                self.redis_handler.set_cache(key=cache_key, value=template_dict, ttl=3600)
            
            return new_template
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating template: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create template: {str(e)}")
    
    def update_template(self, template_id: str, 
                      template_data: NotificationTemplateUpdate) -> NotificationTemplate:
        """
        Update an existing notification template.
        
        Args:
            template_id: Template ID
            template_data: Updated template data
            
        Returns:
            NotificationTemplate: Updated template
        """
        try:
            template = self.db.query(NotificationTemplate).filter(
                NotificationTemplate.id == template_id
            ).first()
            
            if not template:
                raise HTTPException(status_code=404, detail="Template not found")
            
            # Update fields if provided
            if template_data.name is not None:
                template.name = template_data.name
            
            if template_data.title_template is not None:
                template.title_template = template_data.title_template
            
            if template_data.body_template is not None:
                template.body_template = template_data.body_template
            
            if template_data.data_template is not None:
                template.data_template = template_data.data_template
            
            if template_data.category_id is not None:
                # Check if category exists
                if template_data.category_id:
                    category = self.db.query(NotificationCategory).filter(
                        NotificationCategory.id == template_data.category_id
                    ).first()
                    
                    if not category:
                        raise ValueError(f"Category not found: {template_data.category_id}")
                
                template.category_id = template_data.category_id
            
            if template_data.is_active is not None:
                template.is_active = template_data.is_active
            
            # Update metadata securely if provided
            if template_data.metadata is not None:
                encrypted_metadata = self.security_handler.encrypt_data(template_data.metadata)
                template.metadata = encrypted_metadata
            
            template.updated_at = datetime.utcnow()
            
            if template_data.updated_by:
                template.updated_by = template_data.updated_by
            
            self.db.commit()
            
            # Log template update with secure audit trail
            logger.info(f"Notification template updated: {template_id}")
            
            # Update Redis cache if available
            if self.redis_handler:
                cache_key = f"template:{template_id}"
                template_dict = {
                    "id": template.id,
                    "name": template.name,
                    "title_template": template.title_template,
                    "body_template": template.body_template,
                    "data_template": template.data_template,
                    "category_id": template.category_id,
                    "is_active": template.is_active
                }
                self.redis_handler.set_cache(key=cache_key, value=template_dict, ttl=3600)
            
            return template
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating template: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to update template: {str(e)}")
    
    def delete_template(self, template_id: str) -> bool:
        """
        Delete a notification template.
        
        Args:
            template_id: Template ID
            
        Returns:
            bool: Success status
        """
        try:
            template = self.db.query(NotificationTemplate).filter(
                NotificationTemplate.id == template_id
            ).first()
            
            if not template:
                raise HTTPException(status_code=404, detail="Template not found")
            
            self.db.delete(template)
            self.db.commit()
            
            # Log template deletion with secure audit trail
            logger.info(f"Notification template deleted: {template_id}")
            
            # Remove from Redis cache if available
            if self.redis_handler:
                cache_key = f"template:{template_id}"
                self.redis_handler.delete_cache(cache_key)
            
            return True
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting template: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to delete template: {str(e)}")
    
    def get_template_by_id(self, template_id: str) -> Optional[NotificationTemplate]:
        """
        Get a notification template by ID.
        
        Args:
            template_id: Template ID
            
        Returns:
            NotificationTemplate: Template or None
        """
        # Try to get from Redis cache first
        if self.redis_handler:
            cache_key = f"template:{template_id}"
            cached_template = self.redis_handler.get_cache(cache_key)
            
            if cached_template and "id" in cached_template:
                # Convert cached template to NotificationTemplate
                return NotificationTemplate(**cached_template)
        
        # Get from database
        template = self.db.query(NotificationTemplate).filter(
            NotificationTemplate.id == template_id
        ).first()
        
        # If template has encrypted metadata, decrypt it
        if template and template.metadata:
            try:
                decrypted_metadata = self.security_handler.decrypt_data(template.metadata)
                template.metadata = decrypted_metadata
            except Exception as e:
                logger.error(f"Error decrypting template metadata: {str(e)}")
                # Don't fail if decryption fails, just return the encrypted data
        
        # Cache in Redis if available
        if template and self.redis_handler:
            cache_key = f"template:{template_id}"
            template_dict = {
                "id": template.id,
                "name": template.name,
                "title_template": template.title_template,
                "body_template": template.body_template,
                "data_template": template.data_template,
                "category_id": template.category_id,
                "is_active": template.is_active,
                "created_at": template.created_at.isoformat() if template.created_at else None,
                "updated_at": template.updated_at.isoformat() if template.updated_at else None,
                "created_by": template.created_by,
                "updated_by": template.updated_by
            }
            self.redis_handler.set_cache(key=cache_key, value=template_dict, ttl=3600)
        
        return template
    
    def get_templates(self, category_id: Optional[str] = None, active_only: bool = False,
                    limit: int = 50, offset: int = 0) -> List[NotificationTemplate]:
        """
        Get notification templates with optional filters.
        
        Args:
            category_id: Optional category ID filter
            active_only: Whether to return only active templates
            limit: Maximum number of results
            offset: Result offset
            
        Returns:
            List[NotificationTemplate]: List of templates
        """
        query = self.db.query(NotificationTemplate)
        
        # Apply filters
        if category_id:
            query = query.filter(NotificationTemplate.category_id == category_id)
        
        if active_only:
            query = query.filter(NotificationTemplate.is_active == True)
        
        # Apply pagination
        templates = query.order_by(NotificationTemplate.created_at.desc()).offset(offset).limit(limit).all()
        
        # Decrypt metadata for all templates
        for template in templates:
            if template.metadata:
                try:
                    decrypted_metadata = self.security_handler.decrypt_data(template.metadata)
                    template.metadata = decrypted_metadata
                except Exception as e:
                    logger.error(f"Error decrypting template metadata: {str(e)}")
                    # Don't fail if decryption fails, just return the encrypted data
        
        return templates
    
    def create_category(self, category_data: NotificationCategoryCreate) -> NotificationCategory:
        """
        Create a new notification category.
        
        Args:
            category_data: Category data
            
        Returns:
            NotificationCategory: Created category
        """
        try:
            # Check if category with same name exists
            existing_category = self.db.query(NotificationCategory).filter(
                NotificationCategory.name == category_data.name
            ).first()
            
            if existing_category:
                raise ValueError(f"Category with name '{category_data.name}' already exists")
            
            # Create category record
            category_id = str(uuid.uuid4())
            
            new_category = NotificationCategory(
                id=category_id,
                name=category_data.name,
                description=category_data.description,
                created_at=datetime.utcnow(),
                created_by=category_data.created_by
            )
            
            self.db.add(new_category)
            self.db.commit()
            
            # Log category creation with secure audit trail
            logger.info(f"Notification category created: {category_id}")
            
            # Cache category in Redis if available
            if self.redis_handler:
                cache_key = f"category:{category_id}"
                category_dict = {
                    "id": category_id,
                    "name": new_category.name,
                    "description": new_category.description
                }
                self.redis_handler.set_cache(key=cache_key, value=category_dict, ttl=3600)
            
            return new_category
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating category: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create category: {str(e)}")
    
    def update_category(self, category_id: str, 
                      category_data: NotificationCategoryUpdate) -> NotificationCategory:
        """
        Update an existing notification category.
        
        Args:
            category_id: Category ID
            category_data: Updated category data
            
        Returns:
            NotificationCategory: Updated category
        """
        try:
            category = self.db.query(NotificationCategory).filter(
                NotificationCategory.id == category_id
            ).first()
            
            if not category:
                raise HTTPException(status_code=404, detail="Category not found")
            
            # Check for name conflict if name is being updated
            if category_data.name and category_data.name != category.name:
                existing_category = self.db.query(NotificationCategory).filter(
                    NotificationCategory.name == category_data.name,
                    NotificationCategory.id != category_id
                ).first()
                
                if existing_category:
                    raise ValueError(f"Category with name '{category_data.name}' already exists")
            
            # Update fields if provided
            if category_data.name is not None:
                category.name = category_data.name
            
            if category_data.description is not None:
                category.description = category_data.description
            
            category.updated_at = datetime.utcnow()
            
            if category_data.updated_by:
                category.updated_by = category_data.updated_by
            
            self.db.commit()
            
            # Log category update with secure audit trail
            logger.info(f"Notification category updated: {category_id}")
            
            # Update Redis cache if available
            if self.redis_handler:
                cache_key = f"category:{category_id}"
                category_dict = {
                    "id": category.id,
                    "name": category.name,
                    "description": category.description
                }
                self.redis_handler.set_cache(key=cache_key, value=category_dict, ttl=3600)
            
            return category
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating category: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to update category: {str(e)}")
    
    def delete_category(self, category_id: str) -> bool:
        """
        Delete a notification category.
        
        Args:
            category_id: Category ID
            
        Returns:
            bool: Success status
        """
        try:
            category = self.db.query(NotificationCategory).filter(
                NotificationCategory.id == category_id
            ).first()
            
            if not category:
                raise HTTPException(status_code=404, detail="Category not found")
            
            # Check if templates are using this category
            templates_count = self.db.query(NotificationTemplate).filter(
                NotificationTemplate.category_id == category_id
            ).count()
            
            if templates_count > 0:
                raise ValueError(f"Cannot delete category: {templates_count} templates are using this category")
            
            self.db.delete(category)
            self.db.commit()
            
            # Log category deletion with secure audit trail
            logger.info(f"Notification category deleted: {category_id}")
            
            # Remove from Redis cache if available
            if self.redis_handler:
                cache_key = f"category:{category_id}"
                self.redis_handler.delete_cache(cache_key)
            
            return True
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting category: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to delete category: {str(e)}")
    
    def get_category_by_id(self, category_id: str) -> Optional[NotificationCategory]:
        """
        Get a notification category by ID.
        
        Args:
            category_id: Category ID
            
        Returns:
            NotificationCategory: Category or None
        """
        # Try to get from Redis cache first
        if self.redis_handler:
            cache_key = f"category:{category_id}"
            cached_category = self.redis_handler.get_cache(cache_key)
            
            if cached_category and "id" in cached_category:
                # Convert cached category to NotificationCategory
                return NotificationCategory(**cached_category)
        
        # Get from database
        category = self.db.query(NotificationCategory).filter(
            NotificationCategory.id == category_id
        ).first()
        
        # Cache in Redis if available
        if category and self.redis_handler:
            cache_key = f"category:{category_id}"
            category_dict = {
                "id": category.id,
                "name": category.name,
                "description": category.description,
                "created_at": category.created_at.isoformat() if category.created_at else None,
                "updated_at": category.updated_at.isoformat() if category.updated_at else None,
                "created_by": category.created_by,
                "updated_by": category.updated_by
            }
            self.redis_handler.set_cache(key=cache_key, value=category_dict, ttl=3600)
        
        return category
    
    def get_categories(self, limit: int = 50, offset: int = 0) -> List[NotificationCategory]:
        """
        Get notification categories with pagination.
        
        Args:
            limit: Maximum number of results
            offset: Result offset
            
        Returns:
            List[NotificationCategory]: List of categories
        """
        categories = self.db.query(NotificationCategory).order_by(
            NotificationCategory.name
        ).offset(offset).limit(limit).all()
        
        return categories
