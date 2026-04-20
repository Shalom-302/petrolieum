# backend/app/codegen.py
import os
import json
from pathlib import Path


# =============================
# Public Generation / Removal Functions
# =============================

def include_model_in_init(resource_name: str, models_init_file: Path):
    """
    Adds an import line like 'from .post import Post' to models/__init__.py 
    if it doesn't already exist.
    """
    resource_name_lower = resource_name.lower()
    class_name = resource_name[0].upper() + resource_name[1:]
    import_line = f"from .{resource_name_lower} import {class_name}"

    # If __init__.py doesn't exist yet, create it
    if not models_init_file.exists():
        models_init_file.write_text(import_line + "\n", encoding="utf-8")
        return

    # Otherwise read its content
    content = models_init_file.read_text(encoding="utf-8")
    # If our import line isn't present, append it
    if import_line not in content:
        content += f"\n{import_line}\n"
        models_init_file.write_text(content, encoding="utf-8")


def generate_model_file(resource_name: str, fields: list, models_dir: Path) -> Path:
    resource_name_lower = resource_name.lower()
    code = build_model_code(resource_name, fields)
    file_path = models_dir / f"{resource_name_lower}.py"
    file_path.write_text(code, encoding="utf-8")

    # Also ensure models/__init__.py has an import
    # e.g. 'from .post import Post'
    models_init_file = models_dir / "__init__.py"
    include_model_in_init(resource_name, models_init_file)

    return file_path

def generate_schemas_file(resource_name: str, fields: list, schemas_dir: Path) -> Path:
    """
    Creates/overwrites a file in 'schemas_dir' for the given resource.
    The file contains the Pydantic Create, Update, and Out schemas.
    Returns the path to the created/updated file.
    """
    resource_name_lower = resource_name.lower()
    code = build_schemas_code(resource_name, fields)  # We'll define build_schemas_code below
    file_path = schemas_dir / f"{resource_name_lower}.py"
    file_path.write_text(code, encoding="utf-8")
    return file_path


def generate_router_file(
    resource_name: str,
    fields: list,
    routers_dir: Path,
    schemas_dir: Path
) -> Path:
    """
    1) Generates the schemas file in 'schemas_dir' for the resource.
    2) Creates/overwrites the router .py file in 'routers_dir',
       referencing the resource's schemas from 'schemas/<resource>.py'.
    Returns the path to the router file.
    """
    resource_name_lower = resource_name.lower()

    # First, generate the schemas
    generate_schemas_file(resource_name, fields, schemas_dir)

    # Now produce the router code that imports from the new schemas file
    router_code = build_router_code(resource_name)
    file_path = routers_dir / f"{resource_name_lower}.py"
    file_path.write_text(router_code, encoding="utf-8")
    return file_path


def include_router_in_main(resource_name: str, main_file: Path):
    """
    Adds import + include_router line to main.py if they don't already exist.
    """
    resource_name_lower = resource_name.lower()
    import_statement = f"from .routers.{resource_name_lower} import router as {resource_name_lower}_router"
    include_statement = f'app.include_router({resource_name_lower}_router, prefix="/{resource_name_lower}", tags=["{resource_name}"])'

    if not main_file.exists():
        return

    content = main_file.read_text(encoding="utf-8")
    if import_statement not in content:
        content = import_statement + "\n" + content
    if include_statement not in content:
        content += f"\n{include_statement}\n"
    main_file.write_text(content, encoding="utf-8")


def remove_router_from_main(resource_name: str, main_file: Path):
    """
    Removes the import statement and the include_router line for resource_name
    from main.py. This is a naive string matching approach.
    """
    resource_name_lower = resource_name.lower()
    import_statement = f"from .routers.{resource_name_lower} import router as {resource_name_lower}_router"
    include_statement = f'app.include_router({resource_name_lower}_router, prefix="/{resource_name_lower}", tags=["{resource_name}"])'

    if not main_file.exists():
        return

    content = main_file.read_text(encoding="utf-8")
    # Remove import_statement line
    content = content.replace(import_statement + "\n", "")
    # Remove include_statement line
    content = content.replace(include_statement + "\n", "")
    main_file.write_text(content, encoding="utf-8")


def remove_files_for_resource(resource_name: str, models_dir: Path, routers_dir: Path, schemas_dir: Path):
    """
    Deletes the .py files for model, router, and schemas if they exist for the given resource.
    """
    resource_name_lower = resource_name.lower()

    model_file = models_dir / f"{resource_name_lower}.py"
    router_file = routers_dir / f"{resource_name_lower}.py"
    schemas_file = schemas_dir / f"{resource_name_lower}.py"

    if model_file.exists():
        model_file.unlink()
    if router_file.exists():
        router_file.unlink()
    if schemas_file.exists():
        schemas_file.unlink()


# =============================
# Internal Code-Building Functions
# =============================

def build_model_code(resource_name: str, fields: list) -> str:
    """
    Returns Python code for an SQLAlchemy model with given fields.
    If a field has foreign_key, we do 'ForeignKey("table.col")'.
    If a field has relationship, we add a separate line for `relationship("ParentResource", back_populates="comments")`.
    """
    class_name = resource_name[0].upper() + resource_name[1:]  # e.g. "comment" => "Comment"
    table_name = resource_name.lower()

    import_section = """from sqlalchemy import Column, Integer, String, Boolean, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.db import Base
"""

    # We'll store the columns definition
    fields_str = ""
    # We'll store relationship lines (like: post = relationship("Post", back_populates="comments"))
    relationship_str = ""

    for f in fields:
        col_type = type_to_sqlalchemy_col(f.type)
        foreign_key_part = ""
        default_part = ""
        if f.foreign_key:
            # e.g. f.foreign_key="post.id"
            foreign_key_part = f", ForeignKey('{f.foreign_key}')"

        if f.default is not None:
            default_part = f", default={parse_default_value(f.default)}"

        # Build the line: e.g. "post_id = Column(Integer, ForeignKey("post.id"), default=... )"
        fields_str += f"    {f.name} = Column({col_type}{foreign_key_part}{default_part})\n"

        # If there's a relationship, we add a separate line
        if f.relationship:
            # e.g. post = relationship("Post", back_populates="comments", uselist=True/False)
            # The parent resource is the class_name for the foreign resource
            parent_class = f.relationship.parent_resource or "Unknown"
            back_pop = f.relationship.back_populates or ""
            uselist_part = "" if f.relationship.uselist else ", uselist=False"
            # relationship name is typically same as parent, or a custom name
            # here let's assume we call it exactly f.relationship.parent_resource.lower() 
            # but user might want a custom name
            rel_name = f.relationship.parent_resource.lower() if f.relationship.parent_resource else f.name

            relationship_str += f"    {rel_name} = relationship(\"{parent_class}\""
            if back_pop:
                relationship_str += f", back_populates=\"{back_pop}\""
            relationship_str += f"{uselist_part})\n"

    model_code = f'''{import_section}

class {class_name}(Base):
    __tablename__ = "{table_name}"
    id = Column(Integer, primary_key=True, index=True)
{fields_str if fields_str else ""}

{relationship_str if relationship_str else ""}
'''
    return model_code



def build_schemas_code(resource_name: str, fields: list) -> str:
    """
    Builds the Python code for Pydantic schemas (Create, Update, Out).
    """
    class_name = resource_name[0].upper() + resource_name[1:]
    return generate_pydantic_schemas(class_name, fields)


def build_router_code(resource_name: str) -> str:
    """
    Generate a FastAPI router using create_crud_router for resource-level + field-level Casbin checks.
    Allows for overriding or extending routes in resource-specific routers.
    
    Parameters:
    - resource_name: Name of the resource (e.g., "book")
    
    Returns:
    - A string containing the router code.
    """
    class_name = resource_name[0].upper() + resource_name[1:]
    lower_name = resource_name.lower()
    schema_out= f"{class_name}Out"

    router_code = f'''from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any
from app.models.{lower_name} import {class_name}
from app.schemas.{lower_name} import {class_name}Create, {class_name}Update, {schema_out}
from app.crud_base import create_crud_router
from app.core.security import get_current_user
from app.casbin_setup import get_casbin_enforcer
from app.core.db import get_db

# Instantiate CRUD router for the '{lower_name}' resource
router = create_crud_router(
    model={class_name},
    schema_create={class_name}Create,
    schema_update={class_name}Update,
    schema_out={schema_out},
    resource_name="{lower_name}",
    exclude_routes=[]  # Exclude routes dynamically, e.g., ["create", "list", "get"]
)

# ---------------------------
# Example: Override the 'create' method for custom behavior
# ---------------------------
# Uncomment and modify the following code if you need custom logic
# # from app.plugins.advanced_audit.models import AuditLog
# @router.post("/", response_model={schema_out}, name="create_{lower_name}")
# async def custom_create_{lower_name}(
#     data: {class_name}Create,
#     db: Session = Depends(get_db),
#     current_user: Any = Depends(get_current_user),
#     enforcer: Any = Depends(get_casbin_enforcer),
# ):
#     # Custom create logic here
#     # Log the audit event for create
#            log_details = f"Created {resource_name} with data: "
#            log_audit_event(db, current_user.id, "create", resource_name, log_details)
#     return {{"message": "Custom create logic for {lower_name}!"}}

# ---------------------------
# Example: Add a custom route
# ---------------------------
# @router.post("/custom-action/{{item_id}}", response_model={schema_out})
# async def custom_action(
#     item_id: int,
#     db: Session = Depends(get_db),
#     current_user: Any = Depends(get_current_user),
#     enforcer: Any = Depends(get_casbin_enforcer),
# ):
#     # Custom action logic here
#     return {{"message": "Custom action executed on {lower_name}!"}}
'''
    return router_code



def generate_pydantic_schemas(resource_name: str, fields: list) -> str:
    """
    Return a string containing three Pydantic schemas:
      - {class_name}Create
      - {class_name}Update
      - {class_name}Out
    where 'fields' is a list of objects that have .name, .type, .default.
    """
    class_name = resource_name[0].upper() + resource_name[1:]
    lines_create = []
    lines_update = []
    lines_out = ["    id: int"]  # 'id' is included in the Out schema by default

    for f in fields:
        py_type = map_type_to_python(f.type)

        # CREATE schema: required unless there's a default
        if f.default is not None:
            lines_create.append(
                f"    {f.name}: {py_type} = '{f.default}'" 
                if py_type == 'str' 
                else f"    {f.name}: {py_type} = {f.default}" 
            )
        else:
            lines_create.append(f"    {f.name}: {py_type}")

        # UPDATE schema: optional
        lines_update.append(f"    {f.name}: {py_type} | None = None")

        # OUT schema
        lines_out.append(f"    {f.name}: {py_type} | None = None")

    schema_code = f"""
from pydantic import BaseModel

class {class_name}Create(BaseModel):
{os.linesep.join(lines_create)}

class {class_name}Update(BaseModel):
{os.linesep.join(lines_update)}

class {class_name}Out(BaseModel):
{os.linesep.join(lines_out)}

    class Config:
            from_attributes = True 
"""
    return schema_code


# =============================
# Helper Functions
# =============================

def type_to_sqlalchemy_col(py_type: str) -> str:
    """
    Map a string-based type (e.g. "str", "bool", "int", "float") to an SQLAlchemy column type.
    For unknown types, default to Text.
    """
    pt = py_type.lower()
    if pt == "str":
        return "String"
    elif pt == "bool":
        return "Boolean"
    elif pt == "int":
        return "Integer"
    elif pt == "float":
        return "Float"
    else:
        return "Text"

def map_type_to_python(py_type: str) -> str:
    """
    Map a string-based type to a Python type used in Pydantic models.
    """
    pt = py_type.lower()
    if pt == "str":
        return "str"
    elif pt == "bool":
        return "bool"
    elif pt == "int":
        return "int"
    elif pt == "float":
        return "float"
    else:
        return "str"

def parse_default_value(default_raw: str) -> str:
    """
    Convert a default value string (e.g. 'True', '42', 'hello') into a Python-friendly expression.
    - 'true' or 'false' -> bool
    - digits -> int
    - otherwise -> string literal
    """
    d = default_raw.strip().lower()
    if d == "true" or d == "false":
        return d.capitalize()  # "true" -> "True", "false" -> "False"
    if d.isdigit():
        return d
    return f"'{default_raw}'"
