# Advanced Authentication Plugin

A comprehensive authentication system with support for multiple authentication providers (email, GitHub, Google), secure session management, and advanced security features.

## Features

- **Multiple Authentication Providers**
  - Email/Password
  - GitHub OAuth
  - Google OAuth
  - Extensible architecture for adding more providers

- **User Management**
  - UUID for user identification
  - Role-based permissions
  - Group-based authorization
  - User profile management

- **Security Features**
  - Password hashing with bcrypt
  - JWT tokens for authentication
  - Refresh tokens for maintaining sessions
  - Account locking after failed login attempts
  - Password strength requirements
  - Email verification
  - Password reset

- **Multi-Factor Authentication (MFA)**
  - Time-based One-Time Passwords (TOTP)
  - SMS verification
  - Email verification codes
  - Recovery codes

- **Session Management**
  - Active session tracking
  - Session termination
  - Device management

## Installation

This plugin is included by default in the Kaapi backend template. No additional installation steps are required.

## Configuration

The plugin can be configured using environment variables:

```bash
# JWT token settings
AUTH_SECRET_KEY=your-secret-key-here
AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=30
AUTH_REFRESH_TOKEN_EXPIRE_DAYS=30
AUTH_TOKEN_ALGORITHM=HS256

# Password settings
AUTH_PASSWORD_MIN_LENGTH=8
AUTH_PASSWORD_REQUIRE_UPPERCASE=true
AUTH_PASSWORD_REQUIRE_LOWERCASE=true
AUTH_PASSWORD_REQUIRE_DIGIT=true
AUTH_PASSWORD_REQUIRE_SPECIAL=true

# Account security
AUTH_MAX_FAILED_LOGIN_ATTEMPTS=5
AUTH_ACCOUNT_LOCKOUT_MINUTES=15

# Admin user
AUTH_ADMIN_EMAIL=admin@example.com
AUTH_ADMIN_PASSWORD=

# OAuth providers
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

## Usage

### API Endpoints

The plugin provides the following API endpoints:

#### Authentication

- `POST /api/auth/register`: Register a new user
- `POST /api/auth/login`: Login with email and password
- `POST /api/auth/token/refresh`: Refresh an access token
- `POST /api/auth/logout`: Logout the current user

#### OAuth Authentication

- `POST /api/auth/oauth/init`: Initialize OAuth flow
- `POST /api/auth/oauth/callback`: Handle OAuth callback

#### User Management

- `GET /api/auth/me`: Get current user info
- `PUT /api/auth/me`: Update current user
- `POST /api/auth/me/change-password`: Change password

#### Email Verification and Password Reset

- `POST /api/auth/password-reset/request`: Request password reset
- `POST /api/auth/password-reset/verify`: Verify password reset token
- `POST /api/auth/email-verification/request`: Request email verification
- `POST /api/auth/email-verification/verify`: Verify email

#### Multi-Factor Authentication

- `POST /api/auth/mfa/setup`: Set up MFA
- `POST /api/auth/mfa/verify`: Verify MFA code

#### Admin Routes

- `GET /api/auth/users`: Get all users (admin only)
- `GET /api/auth/users/{user_id}`: Get a user by ID (admin only)
- `PUT /api/auth/users/{user_id}`: Update a user (admin only)
- `DELETE /api/auth/users/{user_id}`: Delete a user (admin only)

### Example: Register a New User

```python
import requests

response = requests.post(
    "http://localhost:8000/api/auth/register",
    json={
        "email": "user@example.com",
        "username": "user123",
        "password": "StrongPassword123!",
        "first_name": "John",
        "last_name": "Doe"
    }
)
print(response.json())
```

### Example: Login

```python
import requests

response = requests.post(
    "http://localhost:8000/api/auth/login",
    data={
        "username": "user@example.com",  # Email is used as username
        "password": "StrongPassword123!"
    }
)
tokens = response.json()
access_token = tokens["token"]["access_token"]
refresh_token = tokens["token"]["refresh_token"]
```

### Example: Get Current User

```python
import requests

response = requests.get(
    "http://localhost:8000/api/auth/me",
    headers={"Authorization": f"Bearer {access_token}"}
)
user_info = response.json()
```

## Database Initialization

The plugin automatically initializes the database with the following:

1. Default roles: Admin, User, Guest
2. Default permissions for each role
3. A default admin user (if none exists)
4. MFA method types

### Initializing Authentication Components

Kaapi provides CLI commands to initialize authentication components:

```bash
# Standard initialization (initializes auth providers, creates test user, and sets up admin role)
./kaapi auth init

# Simplified initialization (more robust version that handles database constraints directly)
./kaapi auth init-simple
```

After running these commands, you'll have:

- A test user with email `test@example.com` and password `Passw0rd!`
- OAuth providers configured with placeholder values (replace with real values for production)
- An admin role assigned to the test user

> **Note:** For production use, you should change the default password and update OAuth provider credentials.

## Documentation

Comprehensive documentation is available in the `docs` directory:

- [API Reference](docs/api_reference.md): Detailed documentation of all API endpoints
- [Integration Guide](docs/integration_guide.md): Step-by-step guide for integrating the plugin
- [Security Guide](docs/security_guide.md): Best practices for securing your authentication system
- [Migration Guide](docs/migration_guide.md): Instructions for migrating from a basic auth system

## Development

### Adding a New Provider

To add a new authentication provider:

1. Create a new provider class in the `providers` directory, inheriting from `AuthProvider`
2. Implement the required methods:
   - `get_authorization_url`
   - `exchange_code_for_token`
   - `get_user_info`
3. Register the provider in `providers/__init__.py`

### Creating Migrations

To create a new migration:

```bash
alembic revision --autogenerate -m "Add new field to User model"
```

To run migrations:

```bash
alembic upgrade head
```

### Testing

Comprehensive tests are available in the `tests` directory. Run them with:

```bash
pytest app/plugins/advanced_auth/tests/
```

### Examples

Check the `examples` directory for usage examples and OAuth setup guides.

## License

This plugin is licensed under the terms of the MIT license.
