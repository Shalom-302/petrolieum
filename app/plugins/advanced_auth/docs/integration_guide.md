# Advanced Authentication Plugin Integration Guide

This guide provides detailed instructions for integrating the Advanced Authentication plugin into your FastAPI application.

## Installation

1. Ensure the plugin is installed in your project structure:

   ```plaintext
   app/
     plugins/
       advanced_auth/
         ...
   ```

2. Install the required dependencies:

   ```bash
   pip install fastapi sqlalchemy pydantic python-jose[cryptography] passlib[bcrypt] alembic psycopg2-binary python-multipart httpx
   ```

## Basic Integration

### 1. Update your main application

Modify your `main.py` file to include the plugin:

```python
from fastapi import FastAPI
from app.core.config import settings
from app.plugins.advanced_auth import register_auth_plugin

app = FastAPI(title=settings.PROJECT_NAME)

# Register the authentication plugin
register_auth_plugin(app)

# ... rest of your application code
```

### 2. Configure Environment Variables

Set the following environment variables or add them to your `.env` file:

```
# JWT Settings
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Database Settings
SQLALCHEMY_DATABASE_URL=postgresql://username:password@localhost/dbname

# Password Policy
MIN_PASSWORD_LENGTH=8
REQUIRE_SPECIAL_CHARS=true
PASSWORD_EXPIRY_DAYS=90

# Account Security
MAX_LOGIN_ATTEMPTS=5
ACCOUNT_LOCKOUT_MINUTES=30

# Default Admin User (for first-time setup)
DEFAULT_ADMIN_EMAIL=admin@example.com
DEFAULT_ADMIN_PASSWORD=change-me-immediately
DEFAULT_ADMIN_USERNAME=admin

# OAuth Providers (if using)
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

### 3. Initialize the Database

Run the database initialization script:

```bash
python -m app.plugins.advanced_auth.scripts.seed_database
```

## Advanced Integration

### Using Authentication in Your Routes

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.plugins.advanced_auth.utils.security import (
    get_current_user, get_current_active_user, require_role, require_superuser
)
from app.plugins.advanced_auth.models import User

router = APIRouter()

@router.get("/public")
def public_route():
    """This route is accessible to everyone."""
    return {"message": "This is a public endpoint"}

@router.get("/protected")
def protected_route(current_user: User = Depends(get_current_user)):
    """This route requires authentication."""
    return {"message": f"Hello, {current_user.username}!"}

@router.get("/admin-only")
def admin_route(current_user: User = Depends(require_role("Admin"))):
    """This route requires Admin role."""
    return {"message": "Welcome, Admin!"}

@router.get("/superuser-only")
def superuser_route(current_user: User = Depends(require_superuser)):
    """This route requires superuser status."""
    return {"message": "Welcome, Superuser!"}
```

### Using the Authentication Service Programmatically

```python
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.plugins.advanced_auth.service import AuthService
from app.plugins.advanced_auth.schemas import UserCreate

def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Register a new user."""
    service = AuthService(db)
    user = service.register_user(user_data)
    return user
```

## OAuth Integration

### 1. Configure OAuth Providers

Use the configuration script to set up OAuth providers:

```bash
python -m app.plugins.advanced_auth.scripts.configure_oauth --provider github
```

### 2. Add OAuth Login Buttons to Your Frontend

Example HTML:

```html
<div class="oauth-buttons">
    <a href="/api/auth/oauth/github/login" class="oauth-button github">
        <i class="fab fa-github"></i> Login with GitHub
    </a>
    
    <a href="/api/auth/oauth/google/login" class="oauth-button google">
        <i class="fab fa-google"></i> Login with Google
    </a>
</div>
```

### 3. Handle OAuth Callback in Your Frontend

When a user is redirected back to your application after OAuth authentication, you'll need to handle the authorization code. Typically, your frontend would:

1. Extract the code from the URL query parameters
2. Send it to your backend
3. Process the login with the appropriate provider

## Multi-Factor Authentication (MFA)

### 1. Enable MFA for a User

```python
from app.plugins.advanced_auth.service import AuthService

async def setup_mfa(user_id: str, mfa_type: str = "totp"):
    """Set up MFA for a user."""
    service = AuthService(db)
    setup_data = await service.setup_mfa(user_id, mfa_type)
    return setup_data
```

### 2. Verify MFA During Login

When MFA is enabled, the login process will return a `mfa_required` flag. Your frontend should then:

1. Show the MFA verification screen
2. Collect the MFA code from the user
3. Send it to verify the login

```python
from app.plugins.advanced_auth.service import AuthService

async def verify_mfa(user_id: str, mfa_code: str):
    """Verify an MFA code during login."""
    service = AuthService(db)
    result = await service.verify_mfa(user_id, mfa_code)
    return result
```

## Customization

### Custom User Fields

To add custom fields to the User model:

1. Create a subclass of the User model:

```python
from app.plugins.advanced_auth.models import User as BaseUser
from sqlalchemy import Column, String

class User(BaseUser):
    """Extended user model with custom fields."""
    
    # Add custom fields
    phone_number = Column(String, nullable=True)
    company = Column(String, nullable=True)
```

1. Update your schemas:

```python
from app.plugins.advanced_auth.schemas import UserCreate as BaseUserCreate
from pydantic import BaseModel

class UserCreate(BaseUserCreate):
    """Extended user creation schema."""
    
    phone_number: Optional[str] = None
    company: Optional[str] = None
```

1. Extend the AuthService:

```python
from app.plugins.advanced_auth.service import AuthService as BaseAuthService

class AuthService(BaseAuthService):
    """Extended authentication service."""
    
    def register_user(self, user_data: UserCreate):
        """Register a user with custom fields."""
        # Call the parent method to create the base user
        user = super().register_user(user_data)
        
        # Set custom fields
        user.phone_number = user_data.phone_number
        user.company = user_data.company
        
        # Save the changes
        self.db.commit()
        self.db.refresh(user)
        
        return user
```

## Security Best Practices

1. **Rotate JWT Secret Keys**: Regularly change your `SECRET_KEY` used for JWT tokens
2. **Set Appropriate Token Expiration**: Keep access tokens short-lived and refresh tokens longer
3. **Implement Rate Limiting**: The plugin includes rate limiting middleware, use it to prevent brute force attacks
4. **Enable HTTPS**: Always use HTTPS in production to secure tokens and credentials
5. **Store Passwords Securely**: The plugin uses bcrypt for password hashing by default
6. **Use Environment Variables**: Never hardcode secrets in your code
7. **Audit Authentication Events**: Enable logging for authentication events
8. **Monitor Failed Login Attempts**: Set up alerts for unusual patterns of failed logins

## Troubleshooting

### Common Issues

1. **Token Validation Errors**:
   - Check that your `SECRET_KEY` is consistent across all instances
   - Verify the token expiration settings

2. **Database Connection Issues**:
   - Verify your database connection string
   - Check that required migrations have been applied

3. **OAuth Authentication Failures**:
   - Confirm that redirect URIs exactly match those in provider settings
   - Verify client ID and secret are correct
   - Check that required scopes are configured

4. **Password Validation Errors**:
   - Ensure passwords meet the configured complexity requirements
   - Check if the user account is locked due to too many failed attempts

### Debugging

Enable detailed logging for authentication issues:

```python
import logging

# Set up detailed logging for auth module
logging.getLogger("app.plugins.advanced_auth").setLevel(logging.DEBUG)
```

## Support and Contributing

For issues, suggestions, or contributions, please:

1. Check the existing issues in the repository
2. Open a detailed issue if your problem isn't already reported
3. Submit a pull request with a clear description of changes

We welcome contributions to improve the Advanced Authentication plugin!
