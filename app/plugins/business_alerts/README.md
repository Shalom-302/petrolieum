# Business Alerts Plugin

This plugin provides advanced alerting capabilities to monitor and notify critical business situations in the KAAPI application, allowing users to quickly respond to important events.

## Key Features

### 1. Business Alert Detection

* Automatic identification of business situations requiring attention
* Configurable rules for different alert types
* Proactive anomaly detection

### 2. Alert Management

* Interface to view, sort, and filter alerts
* Classification by priority and type
* Alert assignment and tracking

### 3. Notifications

* Multiple notification channels (email, SMS, in-app)
* Customizable notifications by alert type
* User-specific notification preferences

## Architecture

The plugin follows KAAPI's standardized architecture with a clear separation of concerns:

* **Routes**: API endpoints for alert management and notifications
* **Services**: Business logic for alert detection and processing
* **Models**: Data structures for storing alerts and their configurations
* **Schemas**: Input and output data validation
* **Utilities**: Utility functions for formatting and security
* **Tasks**: Scheduled tasks for automated alert detection

The plugin utilizes the application's common security infrastructure, particularly for encryption and API rate limiting.

## Integration

To integrate this plugin into your KAAPI application:

1. Add the plugin to your main application file:

```python
from app.plugins.business_alerts.main import business_alerts_plugin

# In the application configuration function
business_alerts_plugin.init_app(app, prefix="/api/business-alerts")
```

1. Run database migrations to create the necessary tables:

```bash
alembic revision --autogenerate -m "Add business alerts tables"
alembic upgrade head
```

## Usage Examples

### Creating an Alert Rule

```python
import requests

# Define a new alert rule
alert_rule = {
    "name": "Expired Documents",
    "description": "Alert when important documents are expired",
    "condition": {
        "type": "expiration",
        "entity": "document",
        "days_before": 7
    },
    "priority": "high",
    "notification_channels": ["email", "in_app"]
}

# Call the API to create the rule
response = requests.post(
    'https://api.example.com/api/business-alerts/alerts/rules',
    json=alert_rule,
    headers={'Authorization': f'Bearer {token}'}
)

rule_id = response.json()['id']
```

### Retrieving Active Alerts

```python
import requests

# Filter parameters
params = {
    'status': 'active',
    'priority': 'high',
    'limit': 20,
    'offset': 0
}

# Call the API to retrieve alerts
response = requests.get(
    'https://api.example.com/api/business-alerts/alerts',
    params=params,
    headers={'Authorization': f'Bearer {token}'}
)

alerts = response.json()['items']
for alert in alerts:
    print(f"Alert: {alert['message']} - Priority: {alert['priority']}")
```

### Configuring Notification Preferences

```python
import requests

# Define notification preferences
notification_preferences = {
    "email": True,
    "sms": False,
    "in_app": True,
    "priority_threshold": "medium"
}

# Call the API to update preferences
response = requests.put(
    'https://api.example.com/api/business-alerts/notifications/preferences',
    json=notification_preferences,
    headers={'Authorization': f'Bearer {token}'}
)

if response.status_code == 200:
    print("Notification preferences updated successfully")
```

## Security

This plugin implements advanced security measures:

* Encryption of sensitive data using the standardized encryption handler
* API rate limiting to prevent abuse
* Detailed logging for auditing
* Strict validation of user inputs

## Default Alert Types

| Alert Type | Description | Default Priority |
|--------------|-------------|-------------------|
| Document Expiration | Alert before important documents expire | High |
| Financial Threshold | Alert when a financial indicator exceeds a threshold | Medium |
| Missing Data | Alert on missing critical data | High |
| Transaction Anomaly | Detection of unusual transactions | Critical |
| System Maintenance | Planned maintenance notifications | Low |

## Technical Implementation

### Technologies Used

* FastAPI for API routes
* SQLAlchemy for data models
* Pydantic for schema validation
* APScheduler for scheduled tasks

### Default Rate Limits

| Endpoint | Limit (per minute) |
|----------|---------------------|
| /alerts | 60 |
| /alerts/rules | 30 |
| /notifications | 120 |
