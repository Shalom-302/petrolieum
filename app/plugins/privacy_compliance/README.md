# Privacy Compliance Plugin for Kaapi

This plugin adds GDPR (General Data Protection Regulation) compliance features to your Kaapi application, allowing you to easily adhere to European and international data protection regulations.

## Features

### Cookie Consent Management

The cookie consent management feature provides a customizable banner for obtaining user consent for cookies. Features include:

- Custom styling with modern glassmorphism effects
- Support for multiple cookie categories (necessary, preferences, statistics, marketing)
- Customizable text and colors
- Automatic banner display
- Optional "powered by" attribution

### Access and Deletion Requests

The GDPR requires that users can access or delete their personal data. This plugin provides:

- Request submission forms for data access or deletion
- Admin interface for managing requests
- Email verification for request authenticity
- Timestamped audit trail of request processing

### Data Anonymization

For compliance with the right to be forgotten, the plugin includes:

- Data pseudonymization tools
- Field-specific anonymization methods
- Anonymization logs for audit purposes
- Support for multiple anonymization strategies (hashing, generalization, etc.)

### Privacy Policy Management

Maintain and version your privacy policy:

- Create and update privacy policy content
- Track policy versions
- Record acceptance by users
- Historical policy access

## Installation

Add this plugin to your Kaapi application:

```python
# In your kaapi_plugins.py
PLUGINS = [
    # ... other plugins
    "app.plugins.privacy_compliance"
]
```

## Usage

### 1. Cookie Consent Banner

The cookie consent banner is automatically injected into your application. You can customize its appearance and behavior through the admin interface at `/admin/privacy/cookie-consent`.

Include this script in the `<head>` section of your HTML to activate the banner:

```html
<script src="/privacy/cookie-consent.js"></script>
```

#### Customization via API

```python
from app.plugins.privacy_compliance.services import update_cookie_banner_settings

# In your route handler
@app.put("/admin/privacy/cookie-banner")
async def update_cookie_banner(
    settings: CookieBannerSettings,
    db: Session = Depends(get_db)
):
    update_cookie_banner_settings(db, settings)
    return {"success": True}
```

### 2. Access and Deletion Request Management

To create a page allowing users to submit GDPR requests:

```python
from app.plugins.privacy_compliance.schemas import DataRequestCreate
from app.plugins.privacy_compliance.services import create_data_request

@app.post("/privacy/data-request")
async def submit_data_request(
    request: DataRequestCreate,
    db: Session = Depends(get_db)
):
    request_id = create_data_request(db, request)
    return {"success": True, "request_id": request_id}
```

Process access and deletion requests through the admin interface at `/admin/privacy/data-requests`.

### 3. Data Anonymization

Use the anonymization tools in your code:

```python
from app.plugins.privacy_compliance.anonymization import anonymize_data

# Example of user data anonymization
anonymized_data = anonymize_data(
    data=user_data,
    fields_to_anonymize=["email", "phone", "address"],
    anonymization_method="pseudonymize"  # or "hash", "redact", "generalize"
)
```

### 4. Customizable Privacy Policy

A dynamic privacy policy is generated at `/privacy-policy`. You can customize it through the admin interface at `/admin/privacy/policy`.

## Configuration

The plugin stores its configuration in the database using the following models:

- `CookieConsentSettings`
- `DataRequest`
- `DataProcessingRecord`
- `PrivacyPolicy`
- `ConsentLog`

## Modern User Interface

The plugin's user interface uses modern design elements:

- Glassmorphism effect for cards and banners
- Blue/indigo color gradients
- Subtle geometric background shapes
- Hover effects on buttons and controls

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/privacy/cookie-categories` | Retrieves all cookie categories |
| PUT | `/privacy/cookie-consent` | Saves a user's cookie preferences |
| POST | `/privacy/data-request` | Submits an access or deletion request |
| GET | `/privacy/data-request/{request_id}` | Checks the status of a request |
| GET | `/privacy-policy` | Displays the privacy policy |
| GET | `/privacy/cookie-consent.js` | Serves the cookie banner script |

## Requirements

This plugin requires the following packages:
cryptography>=3.4.0
anonymizedata>=1.0.0

## Additional Resources

- [Official GDPR Guide](https://gdpr.eu/what-is-gdpr/)
- [Information Commissioner's Office (ICO) - Cookies](https://ico.org.uk/for-organisations/guide-to-pecr/cookies-and-similar-technologies/)
- [ePrivacy Directive](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:32002L0058)
