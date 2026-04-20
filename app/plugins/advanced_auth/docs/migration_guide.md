# Migration Guide: Basic Auth to Advanced Auth

This guide helps you migrate from a basic authentication system to the Advanced Authentication plugin. It provides step-by-step instructions for transitioning your users, roles, and permissions while minimizing disruption.

## Prerequisites

Before starting the migration:

1. **Backup your database**: Create a complete backup of your existing database
2. **Plan for downtime**: Schedule maintenance window if needed
3. **Test in staging**: Always test the migration in a staging environment first

## Migration Steps

### 1. Install the Advanced Auth Plugin

Ensure the plugin is installed in your project structure:

```plaintext
app/
  plugins/
    advanced_auth/
      ...
```

### 2. Create a Migration Plan

#### Analyze your existing auth system

- Identify all user tables and related schemas
- Document current authentication flows
- List all places in code that interact with authentication
- Identify existing roles and permissions

#### Map existing data to new schema

| Existing System | Advanced Auth Plugin |
|-----------------|----------------------|
| users           | users                |
| user_roles      | user_roles           |
| roles           | roles                |
| permissions     | permissions          |
| sessions        | sessions             |

### 3. Create a Database Migration Script

Create a custom Alembic migration script to migrate your data:

```python
"""Migrate data from basic auth to advanced auth.

Revision ID: migrate_basic_to_advanced
Create Date: 2025-03-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'migrate_basic_to_advanced'
down_revision = '001'  # Your most recent migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Migrate data from old auth tables to new auth tables."""
    connection = op.get_bind()
    
    # Step 1: Migrate roles
    old_roles = connection.execute("SELECT id, name, description FROM old_roles").fetchall()
    for old_role in old_roles:
        connection.execute(
            "INSERT INTO roles (id, name, description, is_system_role, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                str(uuid.uuid4()), 
                old_role.name, 
                old_role.description, 
                False,
                datetime.utcnow(),
                datetime.utcnow()
            )
        )
    
    # Step 2: Migrate permissions
    old_permissions = connection.execute(
        "SELECT id, name, description FROM old_permissions"
    ).fetchall()
    for old_perm in old_permissions:
        connection.execute(
            "INSERT INTO permissions (id, name, description, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (
                str(uuid.uuid4()),
                old_perm.name,
                old_perm.description,
                datetime.utcnow(),
                datetime.utcnow()
            )
        )
    
    # Step 3: Migrate users
    # Note: You'll need to adapt this to your specific schema
    old_users = connection.execute(
        "SELECT id, username, email, password, first_name, last_name, " 
        "is_active, created_at, updated_at FROM old_users"
    ).fetchall()
    
    for old_user in old_users:
        # Get role ID for this user
        user_role = connection.execute(
            "SELECT role_id FROM old_user_roles WHERE user_id = %s", 
            (old_user.id,)
        ).fetchone()
        
        role_id = None
        if user_role:
            # Map old role ID to new role ID
            role_name = connection.execute(
                "SELECT name FROM old_roles WHERE id = %s",
                (user_role.role_id,)
            ).fetchone().name
            
            new_role = connection.execute(
                "SELECT id FROM roles WHERE name = %s",
                (role_name,)
            ).fetchone()
            
            if new_role:
                role_id = new_role.id
        
        # Insert user into new table
        connection.execute(
            "INSERT INTO users (id, username, email, hashed_password, first_name, "
            "last_name, is_active, is_verified, is_superuser, role_id, created_at, "
            "updated_at, primary_auth_provider) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                str(uuid.uuid4()),
                old_user.username,
                old_user.email,
                old_user.password,  # Assuming the hashing algorithm is compatible
                old_user.first_name,
                old_user.last_name,
                old_user.is_active,
                True,  # Assuming all existing users are verified
                False,  # Set superuser status as needed
                role_id,
                old_user.created_at or datetime.utcnow(),
                old_user.updated_at or datetime.utcnow(),
                "email"
            )
        )


def downgrade() -> None:
    """Revert the migration (if possible)."""
    # This is often not possible without data loss
    # but you can implement a best-effort downgrade if needed
    pass
```

### 4. Create a Custom Migration Script

For more complex migrations, create a standalone script:

```python
#!/usr/bin/env python
"""
Migration script for advanced authentication plugin.

This script migrates users, roles, and permissions from a legacy authentication system
to the advanced authentication plugin.
"""
import logging
import argparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define command line arguments
parser = argparse.ArgumentParser(description='Migrate from legacy auth to advanced auth')
parser.add_argument('--source-db', required=True, help='Source database connection string')
parser.add_argument('--target-db', required=True, help='Target database connection string')
parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without making changes')
args = parser.parse_args()

# Connect to databases
source_engine = create_engine(args.source_db)
target_engine = create_engine(args.target_db)

SourceSession = sessionmaker(bind=source_engine)
TargetSession = sessionmaker(bind=target_engine)

source_db = SourceSession()
target_db = TargetSession()

try:
    if args.dry_run:
        logger.info("Performing dry run...")
    
    # Start migration
    logger.info("Starting migration from legacy auth to advanced auth...")
    
    # 1. Migrate roles
    logger.info("Migrating roles...")
    role_mapping = {}  # Map old role IDs to new role IDs
    
    old_roles = source_db.execute("SELECT id, name, description FROM roles").fetchall()
    logger.info(f"Found {len(old_roles)} roles to migrate")
    
    for old_role in old_roles:
        if not args.dry_run:
            new_id = uuid.uuid4()
            role_mapping[old_role.id] = new_id
            
            target_db.execute(
                "INSERT INTO roles (id, name, description, is_system_role, created_at, updated_at) "
                "VALUES (:id, :name, :desc, :is_system, :created, :updated)",
                {
                    "id": new_id,
                    "name": old_role.name,
                    "desc": old_role.description or "",
                    "is_system": False,
                    "created": datetime.utcnow(),
                    "updated": datetime.utcnow()
                }
            )
        
        logger.info(f"Migrated role: {old_role.name}")
    
    if not args.dry_run:
        target_db.commit()
    
    # 2. Migrate permissions
    # (Similar pattern as roles migration)
    
    # 3. Migrate users
    logger.info("Migrating users...")
    user_count = 0
    
    old_users = source_db.execute(
        "SELECT id, username, email, password, first_name, last_name, is_active "
        "FROM users"
    ).fetchall()
    
    for old_user in old_users:
        if not args.dry_run:
            # Get user's role
            user_role_query = source_db.execute(
                "SELECT role_id FROM user_roles WHERE user_id = :user_id",
                {"user_id": old_user.id}
            ).fetchone()
            
            role_id = None
            if user_role_query and user_role_query.role_id in role_mapping:
                role_id = role_mapping[user_role_query.role_id]
            
            # Insert user
            new_user_id = uuid.uuid4()
            target_db.execute(
                "INSERT INTO users (id, username, email, hashed_password, first_name, "
                "last_name, is_active, is_verified, is_superuser, role_id, created_at, "
                "updated_at, primary_auth_provider) VALUES ("
                ":id, :username, :email, :password, :first_name, :last_name, :is_active, "
                ":is_verified, :is_superuser, :role_id, :created, :updated, :auth_provider)",
                {
                    "id": new_user_id,
                    "username": old_user.username,
                    "email": old_user.email,
                    "password": old_user.password,  # Assuming compatible hashing
                    "first_name": old_user.first_name or "",
                    "last_name": old_user.last_name or "",
                    "is_active": old_user.is_active,
                    "is_verified": True,
                    "is_superuser": False,
                    "role_id": role_id,
                    "created": datetime.utcnow(),
                    "updated": datetime.utcnow(),
                    "auth_provider": "email"
                }
            )
            
            user_count += 1
            
            if user_count % 100 == 0:
                target_db.commit()
                logger.info(f"Migrated {user_count} users...")
    
    if not args.dry_run:
        target_db.commit()
    
    logger.info(f"Successfully migrated {user_count} users")
    logger.info("Migration completed successfully")

except Exception as e:
    logger.error(f"Error during migration: {str(e)}")
    if not args.dry_run:
        target_db.rollback()
    raise

finally:
    source_db.close()
    target_db.close()
```

### 5. Update Your Code

#### Update imports and dependencies:

```python
# Old imports
from app.auth import get_current_user, authenticate_user

# New imports
from app.plugins.advanced_auth.utils.security import get_current_user
from app.plugins.advanced_auth.service import AuthService
```

#### Update authentication endpoints:

```python
# Old login endpoint
@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(user.id)
    return {"access_token": access_token, "token_type": "bearer"}

# New login endpoint
@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    service = AuthService(db)
    try:
        user = service.authenticate_user(form_data.username, form_data.password)
        tokens = service.create_tokens(user)
        return {"user": user, "token": tokens}
    except AuthException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
```

### 6. Test Authentication Flows

1. **Test user login**: Ensure existing users can log in with their credentials
2. **Test role-based access**: Verify that permissions work correctly
3. **Test token refresh**: Validate that token refresh works as expected
4. **Test password reset**: Confirm that users can reset their passwords

### 7. Rollout Strategy

#### Option 1: Direct Migration

- Schedule downtime
- Run migration scripts
- Deploy the updated application
- Monitor for any issues

#### Option 2: Parallel Systems

- Run both auth systems in parallel
- Gradually migrate users to the new system
- Use a flag in the user table to determine which system to use
- Once all users are migrated, remove the old system

#### Option 3: New Users Only

- Use the advanced auth for new users only
- Keep existing users on the old system
- Provide a way for existing users to upgrade to the new system

### 8. Post-Migration Tasks

1. **Update documentation**: Ensure all documentation reflects the new auth system
2. **Train support staff**: Make sure support understands the new auth flows
3. **Monitor performance**: Watch for any performance issues with the new system
4. **Audit security**: Conduct security audit of the new implementation
5. **Clean up old tables**: Once migration is verified, remove or archive old auth tables

## Troubleshooting

### Common Migration Issues

1. **Password Hashing Incompatibility**:
   - If the old system uses a different hashing algorithm, you may need to re-hash passwords
   - Example fix: Add a flag to force password reset on next login

2. **Missing User Data**:
   - If the new schema requires fields that don't exist in the old system
   - Solution: Set default values and allow users to update later

3. **Role Mapping Issues**:
   - When roles don't map 1:1 between systems
   - Solution: Create a mapping table and potentially merge or split roles

4. **Session Invalidation**:
   - Users may be logged out during migration
   - Solution: Implement a smooth transition with new tokens

5. **Integration Points**:
   - Third-party systems might rely on the old auth system
   - Solution: Create compatibility layers or update integrations

### Rollback Plan

If critical issues are discovered:

1. Restore the database backup
2. Revert code changes
3. Return to the old authentication system
4. Analyze what went wrong and adjust the migration plan

## Conclusion

Migrating from a basic authentication system to the Advanced Authentication plugin requires careful planning and execution. By following this guide, you can minimize disruption and ensure a smooth transition for your users.

Remember that authentication is a critical security component, so take all necessary precautions and thoroughly test each step of the migration process.
