# API Gateway Plugin

A secure plugin for exposing and managing APIs with authentication, authorization, rate limiting, and comprehensive documentation.

## Features

- **API Key Authentication** - Protect APIs with secure API keys
- **Permission-based Authorization** - Granular access control for each route
- **Rate Limiting** - Protection against abuse and DoS attacks
- **Audit Logging** - Comprehensive tracking of API requests with sanitized data
- **Automatic OpenAPI Documentation** - Generation of interactive documentation via Swagger UI and ReDoc
- **IP and Origin Restrictions** - Access control based on IP address and request origin
- **Administration Interface** - Management of API keys, monitoring of logs and rate limits
- **Simple Integration** - Fluent API for exposing existing routes through the gateway

## Installation

The plugin is included in the Kaapi framework by default. No additional installation is required.

## Usage

### Plugin Initialization

```python
from fastapi import FastAPI
from app.plugins.api_gateway.main import plugin as api_gateway

app = FastAPI()

# Initialize the plugin with optional configurations
api_gateway.initialize(
    app,
    api_title="My API",
    api_description="Secure API for my application",
    api_version="1.0.0"
)
```

### Exposing an Existing Router via the API Gateway

```python
from fastapi import APIRouter, Depends
from app.plugins.api_gateway.main import plugin as api_gateway

# Create a normal FastAPI router
my_router = APIRouter()

@my_router.get("/items")
def get_items():
    return {"items": ["item1", "item2"]}

# Register the router with the API Gateway
api_gateway.register_api(
    router=my_router,
    namespace="items",
    version="v1",
    requires_api_key=True,
    permissions=["items:read"],
    tags=["Items"]
)
```

### Requiring an API Key for a Route

```python
from fastapi import APIRouter, Depends
from app.plugins.api_gateway.main import plugin as api_gateway

router = APIRouter()

# Route requiring an API key with specific permissions
@router.post("/items")
def create_item(
    item_data: dict,
    api_key = Depends(api_gateway.require_api_key(permissions=["items:write"]))
):
    return {"result": "Item created", "api_key_id": api_key.id}
```

### Documentation Generation

Documentation is automatically generated and available at the following endpoints:

- `/api/docs` - Swagger UI interface
- `/api/redoc` - ReDoc interface
- `/api/openapi.json` - OpenAPI schema in JSON format

## Administration

### Creating an API Key

```python
from app.plugins.api_gateway.models.api_key import ApiKeyDB
from sqlalchemy.orm import Session

def create_api_key(db: Session, name: str, permissions: list[str]):
    # Create an API key
    api_key, plain_key = ApiKeyDB.create_key(
        db=db,
        name=name,
        permissions=permissions,
        rate_limit="100/minute"
    )
    db.commit()
    
    # The plain text key is only available at this moment
    print(f"API Key: {plain_key}")
    
    return api_key
```

### Accessing the Administration Interface

The administration interface is available at `/admin/api-gateway` and allows you to:

- Manage API keys (create, modify, delete)
- View audit logs
- Monitor and reset rate limits
- Configure global plugin settings

## Configuration

Here are the main configuration options available:

```python
from app.plugins.api_gateway.config import ApiGatewayConfig

config = ApiGatewayConfig(
    # Documentation
    api_title="My API",
    api_description="Secure API for my application", 
    api_version="1.0.0",
    
    # Security
    api_key_header_name="X-API-Key",
    api_key_query_param="api_key",
    default_key_expiry_days=365,
    
    # Rate limiting
    enable_rate_limiting=True,
    default_rate_limit="100/minute",
    
    # Audit logging
    enable_audit_logging=True,
    sensitive_headers=["Authorization", "Cookie", "X-API-Key"],
    sensitive_body_fields=["password", "token", "secret"],
    
    # CORS
    cors_allow_origins=["*"],
    cors_allow_methods=["GET", "POST", "PUT", "DELETE"]
)

# Use this configuration during initialization
api_gateway.initialize(app, **config.dict())
```

## Security

The plugin implements security best practices:

- API keys are hashed before being stored in the database
- Audit logs are sanitized to prevent sensitive information leakage
- Rate limiting protects against abuse and denial of service attacks
- IP and origin restrictions provide an additional layer of security
- Permission verification is performed for each request

## Complete Example

A complete integration example with the payment plugin is available in `examples/payment_api.py`.

## Plugin Structure

```
api_gateway/
├── admin/           # Admin routes and functionality
├── docs/            # OpenAPI documentation generation
├── examples/        # Usage examples
├── models/          # Data models (SQLAlchemy)
├── routes/          # API route management
├── schemas/         # Pydantic schemas for validation
├── security/        # Authentication and authorization
├── config.py        # Plugin configuration
├── main.py          # Plugin entry point
├── router.py        # Main router with middleware
└── README.md        # This documentation
```

## License

This plugin is part of the Kaapi framework and is subject to the same license as the main project.
