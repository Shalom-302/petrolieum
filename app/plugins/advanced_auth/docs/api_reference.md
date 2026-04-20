# Advanced Authentication API Reference

This document provides detailed information about the API endpoints provided by the Advanced Authentication plugin.

## Base URL

All endpoints are relative to the API base URL:

```plaintext
/api/auth
```

## Authentication

Most endpoints require authentication using a JWT token. To authenticate requests, include the token in the `Authorization` header:

```http
Authorization: Bearer {your_token}
```

## Endpoints

### User Registration and Account Management

#### Register a new user

```
POST /register
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "username": "username",
  "password": "SecurePassword123!",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "username": "username",
  "first_name": "John",
  "last_name": "Doe",
  "is_active": true,
  "is_verified": false,
  "created_at": "2025-03-17T12:34:56Z"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid data or user already exists
- `422 Unprocessable Entity`: Validation error

---

#### Verify Email

```
POST /verify-email
```

**Request Body:**
```json
{
  "token": "verification_token_sent_to_email"
}
```

**Response (200 OK):**
```json
{
  "message": "Email verified successfully"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid or expired token

---

#### Login

```
POST /login
```

**Request Body (Form Data):**
```
username: user@example.com
password: SecurePassword123!
```

**Response (200 OK):**
```json
{
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "username": "username",
    "first_name": "John",
    "last_name": "Doe",
    "is_active": true,
    "is_verified": true
  },
  "token": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

**MFA Required Response (403 Forbidden):**
```json
{
  "detail": "Multi-factor authentication required",
  "error_code": "MFA_REQUIRED",
  "error_details": {
    "mfa_methods": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "type": "totp",
        "name": "Authenticator App"
      }
    ]
  }
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid credentials
- `403 Forbidden`: MFA required or account locked

---

#### Verify MFA

```
POST /verify-mfa
```

**Request Body:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "mfa_code": "123456",
  "mfa_method_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (200 OK):**
```json
{
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "username": "username"
  },
  "token": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

**Error Responses:**
- `400 Bad Request`: Invalid MFA code
- `404 Not Found`: MFA method not found

---

#### Refresh Token

```
POST /refresh-token
```

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid or expired refresh token

---

#### Logout

```
POST /logout
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "message": "Successfully logged out"
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid token

---

#### Request Password Reset

```
POST /forgot-password
```

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response (200 OK):**
```json
{
  "message": "Password reset email sent"
}
```

**Error Responses:**
- `404 Not Found`: Email not found (for security, returns 200 OK anyway)

---

#### Reset Password

```
POST /reset-password
```

**Request Body:**
```json
{
  "token": "reset_token_from_email",
  "password": "NewSecurePassword123!"
}
```

**Response (200 OK):**
```json
{
  "message": "Password reset successfully"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid or expired token
- `422 Unprocessable Entity`: Password validation failed

---

#### Get Current User

```
GET /me
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "username": "username",
  "first_name": "John",
  "last_name": "Doe",
  "profile_picture": "https://example.com/avatar.jpg",
  "is_active": true,
  "is_verified": true,
  "role": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "User",
    "description": "Standard user role"
  },
  "permissions": [
    "read:profile",
    "update:profile"
  ],
  "created_at": "2025-03-17T12:34:56Z",
  "last_login": "2025-03-17T13:45:00Z"
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid token
- `404 Not Found`: User not found

---

#### Update User Profile

```
PUT /me
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "first_name": "Updated",
  "last_name": "Name",
  "profile_picture": "https://example.com/new-avatar.jpg"
}
```

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "username": "username",
  "first_name": "Updated",
  "last_name": "Name",
  "profile_picture": "https://example.com/new-avatar.jpg",
  "is_active": true,
  "is_verified": true
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid token
- `422 Unprocessable Entity`: Validation error

---

#### Change Password

```
POST /me/change-password
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "current_password": "CurrentPassword123!",
  "new_password": "NewSecurePassword123!"
}
```

**Response (200 OK):**
```json
{
  "message": "Password changed successfully"
}
```

**Error Responses:**
- `400 Bad Request`: Incorrect current password
- `401 Unauthorized`: Invalid token
- `422 Unprocessable Entity`: Password validation failed

---

### OAuth Authentication

#### Initiate OAuth Login

```
GET /oauth/{provider}/login
```

**Path Parameters:**
- `provider`: OAuth provider (github, google, microsoft, etc.)

**Query Parameters:**
- `redirect_uri`: URI to redirect after OAuth (optional, defaults to configured URI)
- `state`: Optional state parameter for additional security

**Response:**
Redirects to the OAuth provider's authorization page

---

#### OAuth Callback

```
GET /oauth/{provider}/callback
```

**Path Parameters:**
- `provider`: OAuth provider (github, google, microsoft, etc.)

**Query Parameters:**
- `code`: Authorization code from the OAuth provider
- `state`: State parameter from the initial request (if provided)

**Response (200 OK with HTML):**
```html
<!DOCTYPE html>
<html>
<head>
  <title>Authentication Successful</title>
  <script>
    // Script to pass token back to the application
    window.opener.postMessage({
      token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      user: { id: "550e8400-e29b-41d4-a716-446655440000", email: "user@example.com" }
    }, "*");
    window.close();
  </script>
</head>
<body>
  <h1>Authentication Successful</h1>
  <p>You can close this window now.</p>
</body>
</html>
```

**Error Response (400 Bad Request with HTML):**
HTML page showing the error and instructions

---

### Multi-Factor Authentication (MFA)

#### List MFA Methods

```
GET /me/mfa-methods
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "methods": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "type": "totp",
      "name": "Authenticator App",
      "is_primary": true,
      "is_enabled": true,
      "created_at": "2025-03-17T12:34:56Z",
      "last_used_at": "2025-03-17T13:45:00Z"
    }
  ]
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid token

---

#### Setup MFA

```
POST /me/mfa-methods
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "type": "totp",
  "name": "My Authenticator App"
}
```

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "totp",
  "name": "My Authenticator App",
  "is_primary": false,
  "is_enabled": false,
  "secret": "JBSWY3DPEHPK3PXP",
  "qr_code_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEU...",
  "created_at": "2025-03-17T12:34:56Z"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid MFA type
- `401 Unauthorized`: Invalid token

---

#### Verify MFA Setup

```
POST /me/mfa-methods/{mfa_id}/verify
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Path Parameters:**
- `mfa_id`: ID of the MFA method

**Request Body:**
```json
{
  "code": "123456"
}
```

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "totp",
  "name": "My Authenticator App",
  "is_primary": false,
  "is_enabled": true,
  "created_at": "2025-03-17T12:34:56Z",
  "last_used_at": "2025-03-17T12:34:56Z"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid code
- `401 Unauthorized`: Invalid token
- `404 Not Found`: MFA method not found

---

#### Set Primary MFA Method

```
PUT /me/mfa-methods/{mfa_id}/primary
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Path Parameters:**
- `mfa_id`: ID of the MFA method

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "totp",
  "name": "My Authenticator App",
  "is_primary": true,
  "is_enabled": true,
  "created_at": "2025-03-17T12:34:56Z",
  "last_used_at": "2025-03-17T12:34:56Z"
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid token
- `404 Not Found`: MFA method not found

---

#### Disable MFA Method

```
PUT /me/mfa-methods/{mfa_id}/disable
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Path Parameters:**
- `mfa_id`: ID of the MFA method

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "totp",
  "name": "My Authenticator App",
  "is_primary": true,
  "is_enabled": false,
  "created_at": "2025-03-17T12:34:56Z",
  "last_used_at": "2025-03-17T12:34:56Z"
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid token
- `404 Not Found`: MFA method not found

---

#### Delete MFA Method

```
DELETE /me/mfa-methods/{mfa_id}
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Path Parameters:**
- `mfa_id`: ID of the MFA method

**Response (204 No Content)**

**Error Responses:**
- `401 Unauthorized`: Invalid token
- `404 Not Found`: MFA method not found

---

### Session Management

#### List Sessions

```
GET /me/sessions
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "sessions": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWeb...",
      "ip_address": "192.168.1.1",
      "device_info": {
        "os": "Windows",
        "browser": "Chrome",
        "device": "Desktop"
      },
      "is_current": true,
      "created_at": "2025-03-17T12:34:56Z",
      "last_activity": "2025-03-17T13:45:00Z",
      "expires_at": "2025-03-24T12:34:56Z"
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440000",
      "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)...",
      "ip_address": "192.168.1.2",
      "device_info": {
        "os": "iOS",
        "browser": "Safari",
        "device": "Mobile"
      },
      "is_current": false,
      "created_at": "2025-03-16T10:20:30Z",
      "last_activity": "2025-03-17T09:10:00Z",
      "expires_at": "2025-03-23T10:20:30Z"
    }
  ]
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid token

---

#### Revoke Session

```
DELETE /me/sessions/{session_id}
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Path Parameters:**
- `session_id`: ID of the session to revoke

**Response (204 No Content)**

**Error Responses:**
- `401 Unauthorized`: Invalid token
- `404 Not Found`: Session not found

---

#### Revoke All Other Sessions

```
DELETE /me/sessions
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (204 No Content)**

**Error Responses:**
- `401 Unauthorized`: Invalid token

---

### Admin Endpoints

These endpoints require admin privileges.

#### List Users

```
GET /admin/users
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Query Parameters:**
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 10)
- `search`: Search term for email, username, or name
- `role`: Filter by role
- `is_active`: Filter by active status
- `is_verified`: Filter by verification status

**Response (200 OK):**
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "user@example.com",
      "username": "username",
      "first_name": "John",
      "last_name": "Doe",
      "is_active": true,
      "is_verified": true,
      "role": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "User"
      },
      "created_at": "2025-03-17T12:34:56Z",
      "last_login": "2025-03-17T13:45:00Z"
    }
  ],
  "total": 100,
  "page": 1,
  "pages": 10,
  "limit": 10
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid token
- `403 Forbidden`: Insufficient permissions

---

#### Get User Details

```
GET /admin/users/{user_id}
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Path Parameters:**
- `user_id`: ID of the user

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "username": "username",
  "first_name": "John",
  "last_name": "Doe",
  "profile_picture": "https://example.com/avatar.jpg",
  "is_active": true,
  "is_verified": true,
  "is_superuser": false,
  "role": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "User",
    "description": "Standard user role"
  },
  "permissions": [
    "read:profile",
    "update:profile"
  ],
  "created_at": "2025-03-17T12:34:56Z",
  "updated_at": "2025-03-17T12:34:56Z",
  "last_login": "2025-03-17T13:45:00Z",
  "failed_login_attempts": 0,
  "primary_auth_provider": "email"
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid token
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: User not found

---

#### Create User (Admin)

```
POST /admin/users
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "email": "newuser@example.com",
  "username": "newuser",
  "password": "SecurePassword123!",
  "first_name": "New",
  "last_name": "User",
  "is_active": true,
  "is_verified": true,
  "role_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "newuser@example.com",
  "username": "newuser",
  "first_name": "New",
  "last_name": "User",
  "is_active": true,
  "is_verified": true,
  "role": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "User"
  },
  "created_at": "2025-03-17T12:34:56Z"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid data or user already exists
- `401 Unauthorized`: Invalid token
- `403 Forbidden`: Insufficient permissions
- `422 Unprocessable Entity`: Validation error

---

#### Update User (Admin)

```
PUT /admin/users/{user_id}
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Path Parameters:**
- `user_id`: ID of the user

**Request Body:**
```json
{
  "email": "updated@example.com",
  "username": "updateduser",
  "first_name": "Updated",
  "last_name": "User",
  "is_active": true,
  "is_verified": true,
  "role_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "updated@example.com",
  "username": "updateduser",
  "first_name": "Updated",
  "last_name": "User",
  "is_active": true,
  "is_verified": true,
  "role": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "User"
  },
  "updated_at": "2025-03-17T12:34:56Z"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid data
- `401 Unauthorized`: Invalid token
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: User not found
- `422 Unprocessable Entity`: Validation error

---

#### Delete User

```
DELETE /admin/users/{user_id}
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Path Parameters:**
- `user_id`: ID of the user

**Response (204 No Content)**

**Error Responses:**
- `401 Unauthorized`: Invalid token
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: User not found

---

#### List Roles

```
GET /admin/roles
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "roles": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Admin",
      "description": "Administrator role",
      "is_system_role": true,
      "permissions": [
        {
          "id": "550e8400-e29b-41d4-a716-446655440000",
          "name": "admin:all"
        }
      ],
      "created_at": "2025-03-17T12:34:56Z"
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440000",
      "name": "User",
      "description": "Standard user role",
      "is_system_role": true,
      "permissions": [
        {
          "id": "770e8400-e29b-41d4-a716-446655440000",
          "name": "read:profile"
        },
        {
          "id": "880e8400-e29b-41d4-a716-446655440000",
          "name": "update:profile"
        }
      ],
      "created_at": "2025-03-17T12:34:56Z"
    }
  ]
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid token
- `403 Forbidden`: Insufficient permissions

## Error Codes

| Error Code             | Description                                     |
|------------------------|-------------------------------------------------|
| INVALID_CREDENTIALS    | Invalid username or password                    |
| ACCOUNT_LOCKED         | Account is temporarily locked                   |
| ACCOUNT_INACTIVE       | Account is disabled                             |
| EMAIL_NOT_VERIFIED     | Email address has not been verified             |
| INVALID_TOKEN          | Token is invalid or malformed                   |
| EXPIRED_TOKEN          | Token has expired                               |
| PERMISSION_DENIED      | User lacks the required permissions             |
| USER_EXISTS            | User with the given email or username exists    |
| INVALID_PASSWORD       | Password does not meet security requirements    |
| MFA_REQUIRED           | Multi-factor authentication is required         |
| INVALID_MFA_CODE       | MFA verification code is invalid                |
| OAUTH_ERROR            | Error during OAuth authentication               |

## Rate Limiting

API endpoints are rate-limited to prevent abuse. Current limits are:

- Authentication endpoints: 5 requests per minute per IP
- Other endpoints: 60 requests per minute per user

When rate limit is exceeded, the API returns:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 60
```
