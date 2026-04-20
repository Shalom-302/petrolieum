# Digital Signature and Timestamp Plugin

This plugin provides advanced digital signature and cryptographic timestamping capabilities for the KAAPI application, enabling certification of document integrity and authenticity.

## Key Features

### 1. Document and Transaction Integrity Certification

- Digital signatures with Public Key Infrastructure (PKI)
- Independent signature verification
- Complete traceability of signed documents

### 1. Cryptographic Validation with PKI

- Robust cryptographic signatures using RSA-PSS
- Certificate and trust chain management
- Signature verification against issued certificates

### 3. Secure Legal Evidence Preservation

- Evidence packages for legal proceedings
- Secure timestamping to prove data existence at a specific point in time
- Long-term signature validation

## Architecture

The plugin follows KAAPI's standardized architecture with a clear separation of concerns:

- **Routes**: API endpoints for signature and timestamping operations
- **Services**: Business logic for signature creation and verification
- **Models**: Data structures for storing signatures and timestamps
- **Schemas**: Input and output data validation
- **Utilities**: Reusable cryptographic security functions

The plugin utilizes the application's common security infrastructure, especially for encryption and logging, ensuring a consistent and standardized approach.

## Integration

To integrate this plugin into your KAAPI application:

1. Add the plugin to your main application file:

```python
from app.plugins.digital_signature.main import digital_signature_plugin

# In the application configuration function
digital_signature_plugin.init_app(app, prefix="/api/digital-signature")
```

1. Run database migrations to create the necessary tables:

```bash
alembic revision --autogenerate -m "Add digital signature tables"
alembic upgrade head
```

## Usage Examples

### Signing a Document

```python
import requests

# Prepare the document to sign
files = {'document': open('contract.pdf', 'rb')}
data = {
    'description': 'Employment Contract',
    'signature_type': 'qualified'
}

# Call the signature API
response = requests.post(
    'https://api.example.com/digital-signature/sign/document',
    files=files,
    data=data,
    headers={'Authorization': f'Bearer {token}'}
)

signature_id = response.json()['id']
```

### Verifying a Signature

```python
import requests

# Prepare the document to verify
files = {'document': open('contract.pdf', 'rb')}
data = {'signature_id': 'signature_id_from_previous_step'}

# Call the verification API
response = requests.post(
    'https://api.example.com/api/digital-signature/verify/signature',
    files=files,
    data=data
)

if response.json()['verified']:
    print("The signature is valid!")
else:
    print(f"The signature is invalid: {response.json()['error']}")
```

### Creating a Timestamp

```python
import requests

# Prepare the document to timestamp
files = {'file': open('financial_report.pdf', 'rb')}
data = {'description': 'Financial Report Q1 2025'}

# Call the timestamp API
response = requests.post(
    'https://api.example.com/api/digital-signature/timestamp/create',
    files=files,
    data=data,
    headers={'Authorization': f'Bearer {token}'}
)

timestamp_id = response.json()['id']
```

## Security

This plugin implements advanced security measures:

- Use of 2048-bit RSA keys for signatures
- Secure cryptographic timestamping
- Rate limiting to prevent API abuse
- Encryption of sensitive data using the standardized encryption handler
- Detailed logging for auditing

## Legal Value

Signatures and timestamps created by this plugin are designed to have legal value in many jurisdictions, in compliance with:

- eIDAS Regulation (EU)
- ESIGN Act (United States)
- Electronic Signature Law (Canada)

However, legal requirements may vary across jurisdictions. Consult with a legal expert to confirm validity in your specific context.

---

## Technical Implementation

### Supported Signature Types

1. **Standard** - Simple electronic signature
2. **Advanced** - Advanced electronic signature with signer identification
3. **Qualified** - Qualified electronic signature with certification by an authority

### Cryptographic Algorithms

- **Signature**: RSA-PSS with SHA-256
- **Hash**: SHA-256
- **Certificates**: X.509 v3

### Default Rate Limits

| Endpoint | Limit (per minute) |
|----------|---------------------|
| /sign/document | 20 |
| /sign/batch | 5 |
| /timestamp/create | 30 |
| /verify/signature | 50 |
| /verify/timestamp | 50 |
| /verify/legal-evidence | 10 |
