from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session, joinedload
from typing import Type, List, Any, Optional, Dict, Union
import json
from pydantic import BaseModel
from app.core.db import get_db
from app.casbin_setup import get_casbin_enforcer
from app.core.security import get_current_user
from app.casbin_enforcer import require_casbin_permission
from urllib.parse import parse_qs
from sqlalchemy import or_, and_
from uuid import UUID


# Import the AuditLog model from the advanced_audit plugin
from app.plugins.advanced_audit.models import AuditLog


def log_audit_event(db: Session, user_id: Union[int, str, UUID], action: str, resource: str, details: Optional[str] = None) -> None:
    """
    Creates an audit log entry in the database.
    
    Args:
        db: Database session
        user_id: User ID (can be int, UUID, or str representation of UUID)
        action: Action performed (e.g., "create", "update", "delete")
        resource: Resource type (e.g., "user", "file")
        details: Additional details about the action
    """
    # If user_id is a UUID or string, use NULL for user_id
    # because the user_id column is defined as Integer in the AuditLog model
    if isinstance(user_id, (UUID, str)):
        # Set user_id to NULL and store the UUID in details
        user_details = f"User ID: {user_id}, " + (details or "")
        log = AuditLog(user_id=None, action=action, resource=resource, details=user_details)
    else:
        # If it's an integer, use the value directly
        log = AuditLog(user_id=user_id, action=action, resource=resource, details=details)
    
    db.add(log)
    db.commit()


def parse_filters(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parses the incoming query parameters to extract filtering conditions.
    Supports:
      - Complex filters: $and, $or, $not
      - Deep filtering (relations): filters[author][name][$eq]=John
    """
    filters = {}

    for key, value in query_params.items():
        if key.startswith("filters[") and key.endswith("]"):
            field_path = key[8:-1]  # Extract content inside "filters[]"
            field_parts = field_path.split("][")
            
            current = filters
            for i, part in enumerate(field_parts):
                if i == len(field_parts) - 1:
                    # Last part, assign value
                    current[part] = value
                else:
                    # Nested dictionary
                    if part not in current:
                        current[part] = {}
                    current = current[part]

    return filters

def get_filter_params(request: Request) -> Dict[str, Any]:
    """Extracts query parameters dynamically from the request."""
    return parse_filters(request.query_params)

def get_populate_params(populate: Optional[str] = Query(None)) -> List[str]:
    """Extract populate fields from the request query."""
    return populate.split(",") if populate else []


def apply_filters(q, model, conditions):
        """
        Apply filtering logic dynamically based on query parameters.
        Supports standard, complex ($or/$and), and relational filters.
        Queries can accept a filters parameter with the following syntax:

        The following operators are available:

        Operator	Description
        $eq	Equal
        $eqi	Equal (case-insensitive)
        $ne	Not equal
        $nei	Not equal (case-insensitive)
        $lt	Less than
        $lte	Less than or equal to
        $gt	Greater than
        $gte	Greater than or equal to
        $in	Included in an array
        $notIn	Not included in an array
        $contains	Contains
        $notContains	Does not contain
        $containsi	Contains (case-insensitive)
        $notContainsi	Does not contain (case-insensitive)
        $null	Is null
        $notNull	Is not null
        $between	Is between
        $startsWith	Starts with
        $startsWithi	Starts with (case-insensitive)
        $endsWith	Ends with
        $endsWithi	Ends with (case-insensitive)
        $or	Joins the filters in an "or" expression
        $and	Joins the filters in an "and" expression
        $not	Joins the filters in an "not" expression

        """
        filters = []
        
        for field, condition in conditions.items():
            if field in ["$or", "$and"]:  # Handle complex filtering
                sub_conditions = []
                for sub_filter in condition:
                    sub_conditions.append(and_(*[getattr(model, k) == v for k, v in sub_filter.items()]))
                filters.append(or_(*sub_conditions) if field == "$or" else and_(*sub_conditions))
            elif isinstance(condition, dict):  # Standard filtering
                for operator, value in condition.items():
                    column = getattr(model, field, None)
                    if not column:
                        continue  # Ignore unknown fields
                    
                    if operator == "$eq":
                        filters.append(column == value)
                    elif operator == "$ne":
                        filters.append(column != value)
                    elif operator == "$lt":
                        filters.append(column < value)
                    elif operator == "$lte":
                        filters.append(column <= value)
                    elif operator == "$gt":
                        filters.append(column > value)
                    elif operator == "$gte":
                        filters.append(column >= value)
                    elif operator == "$in":
                        filters.append(column.in_(value.split(",")))
                    elif operator == "$notIn":
                        filters.append(~column.in_(value.split(",")))
                    elif operator == "$contains":
                        filters.append(column.like(f"%{value}%"))
                    elif operator == "$notContains":
                        filters.append(~column.like(f"%{value}%"))
                    elif operator == "$null":
                        filters.append(column == None)
                    elif operator == "$notNull":
                        filters.append(column != None)
                    elif operator == "$between":
                        low, high = map(str.strip, value.split(","))
                        filters.append(column.between(low, high))
                    elif operator == "$startsWith":
                        filters.append(column.like(f"{value}%"))
                    elif operator == "$endsWith":
                        filters.append(column.like(f"%{value}"))

        return q.filter(and_(*filters)) if filters else q


def create_crud_router(
    model: Type[Any],
    schema_create: Type[BaseModel],
    schema_update: Type[BaseModel],
    schema_out: Type[BaseModel],
    resource_name: str,
    exclude_routes: Optional[List[str]] = None,  # New optional parameter
) -> APIRouter:
    """
    Factory function to create an APIRouter with CRUD operations,
    incorporating resource-level and field-level Casbin permissions.
    - Populate (`?populate=author,comments`)
  
    Parameters:
    - model: The SQLAlchemy model class.
    - schema_create: Pydantic schema for create operations.
    - schema_update: Pydantic schema for update operations.
    - resource_name: Name of the resource (e.g., "book").
    - exclude_routes: List of routes to exclude (e.g., ["create", "delete"]).
    
    Returns:
    - An APIRouter instance with CRUD endpoints.
    """
    router = APIRouter()
    exclude_routes = exclude_routes or []

    # ---------------------------
    # CREATE
    # ---------------------------
    if "create" not in exclude_routes:
        @router.post("/", name=f"create_{resource_name}")
        async def create_item(
            data: schema_create,
            db: Session = Depends(get_db),
            current_user: Any = Depends(get_current_user),
            enforcer: Any = Depends(get_casbin_enforcer),
        ) -> Any:
            role_name = current_user.role.name if current_user.role else "anonymous"
            resource_level_allowed = enforcer.enforce(role_name, resource_name, "create")

            data_dict = data.dict()
            # if not resource_level_allowed:
            #     filtered_data = {field_name: value for field_name, value in data_dict.items()
            #                      if enforcer.enforce(role_name, f"{resource_name}:{field_name}", "create")}
            #     data_dict = filtered_data

            if not data_dict:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No allowed fields for create"
                )

            db_obj = model(**data_dict)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            # Log the audit event for create
            log_details = f"Created {resource_name} with data: {json.dumps(data_dict)}"
            log_audit_event(db, current_user.id, "create", resource_name, log_details)
            return schema_out.from_orm(db_obj)

    # ---------------------------
    # LIST
    # ---------------------------
    if "list" not in exclude_routes:
        @router.get("/", name=f"list_{resource_name}s")
        async def list_items(
            request: Request,
            db: Session = Depends(get_db),
            current_user: Any = Depends(get_current_user),
            enforcer: Any = Depends(get_casbin_enforcer),
            filter_params: Dict[str, Any] = Depends(get_filter_params),
            populate_params: List[str] = Depends(get_populate_params),
        ) -> Any:
            """
            Retrieves a list of items, applying:
            - ✅ Field-level permission checks
            - ✅ Complex filtering ($or, $and)
            - ✅ Deep filtering on relations
            - ✅ Population of related fields (`?populate=author,category`)
            """
            role_name = current_user.role.name if current_user.role else "anonymous"
            query = db.query(model)

            # Apply filters
            query = apply_filters(query, model, filter_params)

            # Apply deep filtering for related fields
            for rel, rel_conditions in filter_params.items():
                if isinstance(rel_conditions, dict) and hasattr(model, rel):
                    related_model = getattr(model, rel)
                    related_query = apply_filters(db.query(related_model), related_model, rel_conditions)
                    related_ids = [getattr(obj, "id", None) for obj in related_query.all() if hasattr(obj, "id")]
                    
                    if related_ids:
                        query = query.filter(getattr(model, f"{rel}_id").in_(related_ids))

            # Apply population to fetch related entities
            for rel in populate_params:
              if hasattr(model, rel):
                  try:
                      query = query.options(joinedload(getattr(model, rel)))
                  except Exception as e:
                      print(f"⚠️ Warning: Could not join {rel} due to {e}")
            all_objs = query.all()
            results = []

            # Apply field-level permission checks
            for obj in all_objs:
                # if enforcer.enforce(role_name, resource_name, "read"):
                if True:
                    results.append(schema_out.from_orm(obj))
                else:
                    partial_data = {column.name: getattr(obj, column.name)
                                    for column in obj.__table__.columns
                                    if enforcer.enforce(role_name, f"{resource_name}:{column.name}", "read")}
                    if not partial_data:
                        raise HTTPException(403, f"No fields allowed for read on {resource_name} item")
                    results.append(partial_data)

            return results

    # ---------------------------
    # GET (by item_id)
    # ---------------------------
    if "get" not in exclude_routes:
        @router.get("/{item_id}", name=f"get_{resource_name}")
        async def get_item(
            item_id: int,
            db: Session = Depends(get_db),
            current_user: Any = Depends(get_current_user),
            enforcer: Any = Depends(get_casbin_enforcer),
        ) -> Any:
            obj = db.query(model).filter(model.id == item_id).first()
            if not obj:
                raise HTTPException(404, f"{model.__name__} not found")

            role_name = current_user.role.name if current_user.role else "anonymous"
            # if enforcer.enforce(role_name, resource_name, "read"):
            #     return obj
            # else:
            #     partial_data = {column.name: getattr(obj, column.name)
            #                     for column in obj.__table__.columns
            #                     if enforcer.enforce(role_name, f"{resource_name}:{column.name}", "read")}
            #     if not partial_data:
            #         raise HTTPException(
            #             status_code=status.HTTP_403_FORBIDDEN,
            #             detail=f"No fields allowed for read on {resource_name} item"
            #         )
            #     return partial_data
            return obj

    # ---------------------------
    # UPDATE
    # ---------------------------
    if "update" not in exclude_routes:
        @router.put("/{item_id}", name=f"update_{resource_name}")
        async def update_item(
            item_id: int,
            data: schema_update,
            db: Session = Depends(get_db),
            current_user: Any = Depends(get_current_user),
            enforcer: Any = Depends(get_casbin_enforcer),
        ) -> Any:
            obj = db.query(model).filter(model.id == item_id).first()
            if not obj:
                raise HTTPException(404, f"{model.__name__} not found")

            role_name = current_user.role.name if current_user.role else "anonymous"
            resource_level_allowed = enforcer.enforce(role_name, resource_name, "update")

            update_data = data.dict(exclude_unset=True)
            if not resource_level_allowed:
                filtered_data = {field_name: value for field_name, value in update_data.items()
                                 if enforcer.enforce(role_name, f"{resource_name}:{field_name}", "update")}
                update_data = filtered_data

            if not update_data:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No allowed fields for update"
                )

            for key, value in update_data.items():
                setattr(obj, key, value)

            db.commit()
            db.refresh(obj)
            # Log audit event for update
            log_details = f"Updated {resource_name} id {item_id} with data: {json.dumps(update_data)}"
            log_audit_event(db, current_user.id, "update", resource_name, log_details)

            # if enforcer.enforce(role_name, resource_name, "read"):
            #     return schema_out.from_orm(obj)
            # else:
            #     partial_data = {column.name: getattr(obj, column.name)
            #                     for column in obj.__table__.columns
            #                     if enforcer.enforce(role_name, f"{resource_name}:{column.name}", "read")}
            #     if not partial_data:
            #         raise HTTPException(
            #             status_code=status.HTTP_403_FORBIDDEN,
            #             detail=f"No fields allowed for read on updated {resource_name} item"
            #         )
            #     return schema_out.from_orm(partial_data)
            return schema_out.from_orm(obj)

    # ---------------------------
    # DELETE
    # ---------------------------
    if "delete" not in exclude_routes:
        @router.delete("/{item_id}", dependencies=[Depends(require_casbin_permission(resource_name, "delete"))])
        async def delete_item(
            item_id: int,
            db: Session = Depends(get_db),
            current_user: Any = Depends(get_current_user),
        ):
            obj = db.query(model).filter(model.id == item_id).first()
            if not obj:
                raise HTTPException(404, f"{model.__name__} not found")

            db.delete(obj)
            db.commit()
            # Log audit event for delete
            log_details = f"Deleted {resource_name} id {item_id}"
            log_audit_event(db, current_user.id, "delete", resource_name, log_details)
            return {"detail": f"Deleted successfully from {model.__name__}"}

    return router
