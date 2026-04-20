# Kaapi Payment Plugin

A comprehensive payment processing plugin for Kaapi that supports various payment methods, including those specific to African markets, and incorporates multi-user approval workflows.

## Features

- **Multiple Payment Providers**: Support for various payment providers including M-Pesa, Flutterwave, and more
- **African Payment Methods**: Specialized support for payment methods common in African markets
- **Multi-user Approval Workflows**: Configurable approval processes including:
  - Standard sequential approval
  - Hierarchical approval (role-based)
  - Amount-based approval (threshold-based)
- **Comprehensive Payment Lifecycle**: Full support for payment creation, processing, approval, rejection, and cancellation
- **Refund Support**: Complete and partial refund capabilities across supported payment providers
- **Notification System**: Automatic notifications for payment status changes, approvals, and refunds
- **Webhook Support**: Handler for receiving updates from payment providers
- **Testing Tools**: Mock payment provider and tools for testing payment flows without making real transactions

## Installation

The payment plugin is included in the Kaapi application templates. To use it in your project:

1. Ensure the plugin directory is properly included in your Kaapi application structure
2. Configure the necessary environment variables (see Configuration section)
3. The plugin will be automatically loaded when the application starts

## Configuration

### Environment Variables

Configure these environment variables to set up the payment plugin:

```
# General settings
PAYMENT_BASE_URL=http://localhost:8000
PAYMENT_TEST_MODE=true

# M-Pesa configuration
PAYMENT_MPESA_API_KEY=your_mpesa_api_key
PAYMENT_MPESA_API_SECRET=your_mpesa_api_secret
PAYMENT_MPESA_BUSINESS_SHORTCODE=your_mpesa_shortcode
PAYMENT_MPESA_PASSKEY=your_mpesa_passkey

# Flutterwave configuration
PAYMENT_FLUTTERWAVE_API_KEY=your_flutterwave_api_key
PAYMENT_FLUTTERWAVE_API_SECRET=your_flutterwave_api_secret
PAYMENT_FLUTTERWAVE_MERCHANT_ID=your_flutterwave_merchant_id
PAYMENT_FLUTTERWAVE_WEBHOOK_SECRET=your_flutterwave_webhook_secret

# Optional - other providers
PAYMENT_STRIPE_API_KEY=your_stripe_api_key
PAYMENT_STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret
PAYMENT_PAYPAL_CLIENT_ID=your_paypal_client_id
PAYMENT_PAYPAL_CLIENT_SECRET=your_paypal_client_secret
PAYMENT_PAYSTACK_API_KEY=your_paystack_api_key
PAYMENT_PAYSTACK_WEBHOOK_SECRET=your_paystack_webhook_secret

# Approval settings
PAYMENT_DEFAULT_APPROVAL_WORKFLOW=standard_payment_approval
PAYMENT_REQUIRE_APPROVAL_THRESHOLD=1000.0
```

### Configuration File

The plugin also uses a `config.json` file for more detailed configuration. A default configuration is provided, but you can modify it to suit your needs:

```json
{
  "general": {
    "test_mode": true,
    "require_approval_threshold": 1000.0,
    "default_approval_workflow": "standard_payment_approval"
  },
  "providers": {
    "mpesa": {
      "enabled": true,
      "display_name": "M-Pesa",
      "countries": ["Kenya", "Tanzania", "Mozambique"],
      "currencies": ["KES", "TZS", "MZN"]
    },
    "flutterwave": {
      "enabled": true,
      "display_name": "Flutterwave",
      "countries": ["Nigeria", "Ghana", "Kenya", "South Africa", "Uganda", "Tanzania"],
      "currencies": ["NGN", "GHS", "KES", "ZAR", "UGX", "TZS", "USD", "EUR"]
    }
  },
  "approval_workflows": {
    "standard_payment_approval": {
      "description": "Sequential approval from a list of approvers",
      "min_approvers": 1,
      "approval_timeout_hours": 48
    },
    "hierarchical_approval": {
      "description": "Role-based approvals from different management levels",
      "required_roles": ["supervisor", "manager", "finance_director"],
      "approval_timeout_hours": 72
    },
    "amount_based_approval": {
      "description": "Approval requirements based on payment amount",
      "thresholds": [
        {
          "amount": 100,
          "currency": "USD",
          "required_roles": ["supervisor"]
        },
        {
          "amount": 1000,
          "currency": "USD",
          "required_roles": ["supervisor", "manager"]
        },
        {
          "amount": 10000,
          "currency": "USD",
          "required_roles": ["supervisor", "manager", "finance_director"]
        }
      ],
      "approval_timeout_hours": 96
    }
  }
}
```

## API Usage

### Creating a Payment

```python
from app.plugins.payment.models.payment import PaymentCreate, PaymentMethod, Currency

# Create a payment
payment = await create_payment_service(
    db=db,
    payment=PaymentCreate(
        amount=100.0,
        currency=Currency.USD,
        payment_method=PaymentMethod.CREDIT_CARD,
        description="Product purchase",
        provider="flutterwave",  # Optional, will be auto-selected if not provided
        require_approval=True,   # Whether this payment needs approval
        approvers=[1, 2, 3],     # User IDs of approvers
        approval_workflow="standard_payment_approval"  # Workflow to use
    ),
    current_user=user
)
```

### Processing a Payment

```python
# Process a payment (will initiate payment with the provider)
processed_payment = await process_payment_service(
    db=db,
    payment_id=payment.id,
    current_user=user
)

# After processing, a payment URL may be returned
payment_url = processed_payment.payment_url
```

### Approving a Payment

```python
from app.plugins.payment.models.payment import PaymentApproval

# Approve a payment
approved_payment = await approve_payment_service(
    db=db,
    payment_id=payment.id,
    approval=PaymentApproval(comments="Approved for business expense"),
    current_user=user
)
```

### Rejecting a Payment

```python
# Reject a payment
rejected_payment = await reject_payment_service(
    db=db,
    payment_id=payment.id,
    reason="Budget exceeded",
    current_user=user
)
```

### Cancelling a Payment

```python
# Cancel a payment
cancelled_payment = await cancel_payment_service(
    db=db,
    payment_id=payment.id,
    current_user=user
)
```

### Processing Refunds

```python
from app.plugins.payment.models.payment import RefundCreate

# Create a complete refund
refund = await create_refund_service(
    db=db,
    payment_id=payment.id,
    refund=RefundCreate(
        amount=None,  # Full refund (will use the payment amount)
        reason="Customer requested refund",
    ),
    current_user=user
)

# Create a partial refund
partial_refund = await create_refund_service(
    db=db,
    payment_id=payment.id,
    refund=RefundCreate(
        amount=50.0,  # Partial refund amount
        currency=Currency.USD,
        reason="Partial order cancellation",
    ),
    current_user=user
)

# Process a refund (sends to payment provider)
processed_refund = await process_refund_service(
    db=db,
    refund_id=refund.id,
    current_user=user
)

# Verify refund status with provider
refund_status = await verify_refund_service(
    db=db,
    refund_id=refund.id,
    current_user=user
)

# Cancel a pending refund
cancelled_refund = await cancel_refund_service(
    db=db,
    refund_id=refund.id,
    current_user=user
)
```

## REST API Endpoints

The plugin exposes the following REST API endpoints:

* `GET /apipayments/`: List payments with optional filters
* `GET /apipayments/{payment_id}`: Get a specific payment
* `POST /apipayments/`: Create a new payment
* `PUT /apipayments/{payment_id}`: Update an existing payment
* `POST /apipayments/{payment_id}/process`: Process a payment
* `POST /apipayments/{payment_id}/cancel`: Cancel a payment
* `POST /apipayments/{payment_id}/approve`: Approve a payment
* `POST /apipayments/{payment_id}/reject`: Reject a payment
* `GET /apipayments/providers/list`: Get available payment providers
* `GET /apipayments/methods/list`: Get available payment methods
* `POST /apipayments/webhook/{provider}`: Webhook handler for payment providers

### Refund Endpoints

- **POST** `/apipayments/{payment_id}/refunds` - Create a new refund request for a payment
- **GET** `/apipayments/{payment_id}/refunds` - Get all refunds for a payment
- **GET** `/apipayments/refunds/{refund_id}` - Get details of a specific refund
- **POST** `/apipayments/refunds/{refund_id}/process` - Process a refund with the payment provider
- **POST** `/apipayments/refunds/{refund_id}/verify` - Verify the status of a refund with the payment provider
- **POST** `/apipayments/refunds/{refund_id}/cancel` - Cancel a pending refund

## Provider Integration

The payment plugin includes several integrated payment providers:

- **M-Pesa**: Mobile payment service for users in Kenya, Tanzania, and other African countries
- **Flutterwave**: Payment gateway with wide coverage across Africa
- **Stripe**: Global payment processor with support for cards and other payment methods
- **PayPal**: International payment processor with wide adoption
- **Paystack**: Payment gateway focused on African markets

### Provider Features Matrix

| Provider    | Credit Card | Bank Transfer | Mobile Money | Refunds | Partial Refunds |
|-------------|-------------|---------------|--------------|---------|-----------------|
| M-Pesa      | ❌          | ❌            | ✅           | ✅      | ❌              |
| Flutterwave | ✅          | ✅            | ✅           | ✅      | ✅              |
| Stripe      | ✅          | ✅            | ❌           | ✅      | ✅              |
| PayPal      | ✅          | ✅            | ❌           | ✅      | ✅              |
| Paystack    | ✅          | ✅            | ✅           | ✅      | ✅              |

## Refund Implementation Details

The refund system supports both complete and partial refunds for eligible payments. Key features include:

- **Status Tracking**: Refunds go through several statuses (PENDING, PROCESSING, COMPLETED, FAILED)
- **Partial Refunds**: Support for refunding a portion of the original payment amount
- **Multiple Refunds**: A payment can have multiple partial refunds up to the original amount
- **Automatic Payment Status Updates**: Payment statuses automatically update to REFUNDED or PARTIALLY_REFUNDED
- **Provider Integration**: Seamless refund processing with supported payment providers
- **Notifications**: Automatic notifications for refund status changes

### Refund Validation Rules

Refunds are validated against several rules:

1. Payment must be in COMPLETED status to be eligible for refund
2. Refund amount cannot exceed the remaining balance (original amount minus already refunded amount)
3. Currency must match the original payment currency
4. Provider must support refunds (specified in provider configuration)
5. For partial refunds, provider must specifically support partial refunds

## Testing

The plugin includes tools for testing payment flows without making real transactions:

```python
from app.plugins.payment.tests.test_providers import create_test_payment, complete_test_payment

# Create a test payment
test_payment = await create_test_payment(
    db=db,
    user=current_user,
    amount=100.0,
    currency="USD",
    provider="mock_provider",
    should_fail=False,
    require_approval=True,
    approvers=[1, 2, 3]
)

# Complete the test payment
completed_payment = await complete_test_payment(
    db=db,
    payment=test_payment,
    status="completed"
)
```

There's also a test UI available at `/apipayments/test/mock/{reference}` that simulates a payment provider interface.

## Integrating New Payment Providers

To add a new payment provider:

1. Create a new provider class that inherits from `BasePaymentProvider`
2. Implement all required methods: `process_payment`, `verify_payment`, `cancel_payment`, and `handle_webhook`
3. Register the provider with the factory in `providers/__init__.py`

Example:

```python
from app.plugins.payment.providers.base_provider import BasePaymentProvider
from app.plugins.payment.providers.provider_factory import PaymentProviderFactory

class MyCustomProvider(BasePaymentProvider):
    @property
    def id(self) -> str:
        return "my_custom_provider"
    
    # Implement other required methods...

# Register the provider
PaymentProviderFactory.register_provider(MyCustomProvider)
```

## Security Considerations

- All sensitive payment provider credentials should be stored as environment variables, not in code
- Webhook endpoints should verify signatures where possible
- Consider using IP whitelisting for webhook endpoints in production
- Ensure proper user permissions for payment approval actions
- Use TLS/HTTPS for all payment-related communications

## Database Tables

The plugin uses the following database tables:

- `payments`: Stores payment records
- `payment_approval_steps`: Tracks approval steps for payments
- `payment_transactions`: Records payment transaction history

## Dependencies

- `fastapi`: For the API framework
- `sqlalchemy`: For database ORM
- `requests`: For making HTTP requests to payment providers
- `pydantic`: For data validation and settings management

## Support

For issues and feature requests, please open an issue in the Kaapi repository.
