# KYC Plugin for Kaapi

This plugin provides Know Your Customer (KYC) user identity verification functionality, with special support for regions with low infrastructure through simplified KYC processes.

## Main Features

- **Standard Verification**: Complete KYC process with document verification
- **Simplified Verification**: Alternative KYC process for regions with low infrastructure, based on trusted references
- **User Profiles**: Management of users' personal information
- **Region-based Configuration**: Customized KYC requirements by region
- **Administrative Dashboard**: Monitoring and management of KYC verifications
- **Enhanced Security**: Encryption of sensitive data and security event logging

## Architecture

### Data Models

- `KycVerificationDB`: KYC verification records
- `KycUserProfileDB`: User profiles for KYC processes
- `KycRegionDB`: Regional configurations affecting KYC requirements

### Schemas

- Pydantic schemas for data validation and serialization
- Support for different verification types (standard, simplified, enhanced)
- Validation of documents and references

### Utilities

- `security.py`: Encryption of sensitive data and security logging
- `validation.py`: KYC data validation and risk assessment
- `region_detector.py`: Region detection based on user information
- `kyc_manager.py`: Centralized management of KYC operations

### API Routes

- `/kyc/verifications`: KYC verification management
- `/kyc/profiles`: User profile management
- `/kyc/regions`: Region configuration
- `/kyc/simplified`: Simplified KYC process
- `/kyc/admin/dashboard`: Administrative dashboard

## Simplified KYC Process

The plugin specifically supports regions with low infrastructure through a simplified KYC process:

1. The user provides basic personal information
2. The user indicates trusted references (people or institutions)
3. The system evaluates risk based on the provided information
4. Verification is approved automatically or manually depending on the risk level

This process can be configured by region, allowing KYC requirements to be adapted to the local context.

## Security

Security is a priority in this KYC plugin:

- **Encryption**: Sensitive personal data is encrypted
- **Logging**: All security events are recorded
- **Validation**: Strict validation of incoming data
- **Risk Assessment**: Automatic detection of high-risk profiles
- **Access Control**: Protection of administrative routes

The plugin uses the common security infrastructure defined in the base class for encryption, credential storage, and logging.

## Installation

The KYC plugin integrates into the Kaapi application and is automatically loaded when the application starts.

```python
# In your configuration file
INSTALLED_PLUGINS = [
    # ...
    "app.plugins.kyc",
    # ...
]
```

## Configuration

Plugin parameters can be configured in the application configuration file:

```python
# KYC Configuration
KYC_ENCRYPTION_KEY = os.getenv("KYC_ENCRYPTION_KEY")
KYC_DEFAULT_EXPIRY_DAYS = 365
KYC_ENABLE_SIMPLIFIED = True
```

## Usage

### Create a User Profile

```python
from app.plugins.kyc.utils.kyc_manager import KycManager

# Initialize the KYC manager
kyc_manager = KycManager(db_session=db)

# Create a user profile
profile, result = kyc_manager.create_user_profile(
    user_id="user123",
    profile_data={
        "full_name": "John Smith",
        "date_of_birth": "1980-01-01",
        "nationality": "US",
        # ...
    }
)
```

### Submit a Simplified KYC Verification

```python
# Create a simplified verification
verification, result = kyc_manager.create_verification(
    user_id="user123",
    verification_type="simplified",
    submitted_data=profile_data,
    third_party_references=[
        {
            "reference_type": "trusted_person",
            "reference_name": "Mary Johnson",
            "reference_contact": "+1234567890",
            "relationship": "family_member"
        }
    ]
)
```

## Administrative Dashboard

The plugin includes an administrative dashboard accessible via:

- `/kyc/admin/dashboard/statistics/overview`: Overview of KYC statistics
- `/kyc/admin/dashboard/statistics/by-region`: Statistics by region
- `/kyc/admin/dashboard/pending-verifications`: List of pending verifications
- `/kyc/admin/dashboard/risk-assessment`: Risk assessment

## License

This plugin is distributed under the same license as the main Kaapi application.
