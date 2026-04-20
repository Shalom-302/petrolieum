
### Example 1: Basic Webhook for User Signup

When a new user is created, you might want to notify an external service (e.g. to send a welcome email).

```json
{
  "name": "User Signup Notification",
  "event": "user.created",
  "url": "https://example.com/webhook/user-created",
  "secret": "mysecretkey",
  "is_enabled": true,
  "config": {}
}
```

*   **name:** A descriptive name for the webhook.
*   **event:**  The event name that triggers the webhook (in this case, "user.created").
*   **url:**  The endpoint to which the webhook payload will be POSTed.
*   **secret:**  A secret key used to sign the payload (optional).
*   **is_enabled:**  Whether the webhook is active.
*   **config:** A JSON object to include additional options (empty here).


### Example 2: Order Placed Webhook with Custom Config

For an e-commerce application, you might trigger a webhook when an order is placed. In this example, additional settings such as retry attempts and a timeout are included.

```json
{
  "name": "Order Confirmation Webhook",
  "event": "order.placed",
  "url": "https://orders.example.com/webhook/order",
  "secret": "orderSecret123",
  "is_enabled": true,
  "config": {
    "retry": 3,
    "timeout": 10
  }
}
```

*   **config.retry**: The number of times to retry delivery if the request fails.
    
*   **config.timeout**: The maximum time (in seconds) to wait for a response from the webhook endpoint.



### Example 3: Comment Updated Notification

This webhook is designed for a content management system. It fires when a comment is updated, alerting a moderation service or updating a cache.

```json
{
  "name": "Comment Update Notifier",
  "event": "comment.updated",
  "url": "https://blog.example.com/webhook/comment",
  "secret": "",
  "is_enabled": true,
  "config": {}
}
```

*   **config.retry**: In this example the secret is left empty, meaning no signature is applied.
    
*   **config.timeout**: The webhook triggers for the event "comment.updated".


### Example 4: Inventory Low Alert Webhook

This webhook triggers when the inventory level for an item falls below a specified threshold. The payload might include the item details and the current stock level so that your system (or supplier) can take action, such as reordering or sending an alert email.

```json
{
  "name": "Inventory Low Alert",
  "event": "inventory.low",
  "url": "https://inventory.example.com/alert",
  "secret": "secureSecretKey123",
  "is_enabled": true,
  "config": {
    "threshold": 10,
    "notify_email": "warehouse@example.com"
  }
}
```

*   **name:**: A descriptive name for this webhook.
*   **event:**: The event that triggers the webhook, here "inventory.low".
*   **url:** The destination endpoint that will receive the webhook payload.
*   **secret:**: An optional key used to sign the payload for security.
*   **is_enabled:**: Indicates whether the webhook is active.
*   **config:**: Additional settings:
  *   **threeshold:**  The stock level below which the webhook is triggered.
  *   **notify_email:**  The email address to notify when the event occurs.


### How It Works

1. *   **Event Triggering:**
Your system monitors inventory levels. When an item’s stock falls below the threshold (in this case, 10 units), an event ("inventory.low") is raised.

2. *   **Webhook Execution:**
The webhook plugin queries the database for subscriptions with the event "inventory.low" that are enabled. For each subscription found, it enqueues a background task (using Celery) to deliver a JSON payload to the configured url.

3. *   **Payload Example::**
The payload sent might look like:

```json
{
  "event": "inventory.low",
  "data": {
    "item_id": 123,
    "name": "Wireless Mouse",
    "current_stock": 8,
    "threshold": 10
  }
}
```
If a secret is provided, the delivery task signs the payload using HMAC-SHA256 and includes the signature in an HTTP header (for example, X-Webhook-Signature).


### Why This Approach is Useful

*   **Customizable Thresholds:** The config field allows each webhook to define its own threshold and notification settings.

*   **Decoupled Systems:** The external system (e.g. an inventory management service) only needs to expose an HTTP endpoint to receive alerts, without tightly coupling to your application’s internal logic.

*   **Security:** The optional secret provides a way to verify the integrity of incoming webhook requests.

*   **Scalability:** This configuration can be extended to include additional parameters as needed (such as retry policies or formatting options).


### How to Use These Configurations

1.  **Creating a Webhook**:When an admin creates a new webhook, they fill in the form with the fields shown above. The plugin stores these values in the database table (e.g. kaapi\_webhooks).
    
2.  ```json
{
  "event": "user.created",
  "data": {
    "id": 42,
    "username": "johndoe",
    "email": "john@example.com"
  }
}
```
    
3.  **Security**:If a secret is provided, the plugin’s delivery task signs the payload (e.g., using HMAC with SHA256) and sends the signature in an HTTP header (e.g., X-Webhook-Signature). The receiving service can then verify the authenticity of the payload.

**How to Fire the Webhooks** (example usage)
------------------------------------------------

Anywhere in your code where an event occurs, for example:

````python   
# Suppose in app/routers/user.py or your business logic  
from app.plugins.webhooks.tasks import deliver_webhook  
from app.plugins.webhooks.models import WebhookSubscription  
def create_user(...):      
  user = User(...)      
  db.add(user)      
  db.commit()      
  db.refresh(user)      
  
  # Now we want to call all webhooks for event "user.created"      
  webhooks = db.query(WebhookSubscription).filter_by(event="user.created", is_enabled=True).all()      
  payload = {        
    "event": "user.created",        
    "data": {           
      "id": user.id,           
      "username": user.username,
      ...        
      }      
    }      
    for wh in webhooks:          
      deliver_webhook.delay(              
        webhook_id=wh.id,              
        url=wh.url,              
        event=wh.event,              
        payload=payload,              
        secret=wh.secret or ""          
      )      
    return user
````

**That is how** you actually generate and enqueue the webhook deliveries in the background.