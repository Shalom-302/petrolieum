# app/plugins/advanced_audit/loki_integration.py

import os
import json
import requests
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

# Configuration
LOKI_URL = os.environ.get("LOKI_URL", "http://loki:3100")
PUSH_ENDPOINT = f"{LOKI_URL}/loki/api/push"

logger = logging.getLogger(__name__)

def push_audit_log_to_loki(
    user_id: Optional[int],
    action: str,
    resource: str,
    details: Optional[str] = None,
    timestamp: Optional[float] = None
):
    """
    Pushes an audit log entry to Loki in the format: datetime [resource] action by user ID
    """
    if timestamp is None:
        timestamp = time.time()
    
    # Convert timestamp to nanoseconds for Loki
    timestamp_ns = int(timestamp * 1_000_000_000)
    
    # Format the log entry string: datetime [resource] action by user ID
    dt_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    user_str = f"user {user_id}" if user_id is not None else "system"
    log_message = f"{dt_str} [{resource}] {action} by {user_str}"
    
    # Add details if available
    if details:
        log_message += f" - {details}"
    
    # Prepare the payload for Loki
    payload = {
        "streams": [
            {
                "stream": {
                    "job": "kaapi_advanced_audit",
                    "resource": resource,
                    "action": action,
                    "user_id": str(user_id) if user_id is not None else "system"
                },
                "values": [
                    [str(timestamp_ns), log_message]
                ]
            }
        ]
    }
    
    try:
        response = requests.post(
            PUSH_ENDPOINT,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=2
        )
        
        if response.status_code >= 400:
            logger.error(f"Failed to push audit log to Loki: {response.text}")
        
        return response.status_code < 400
    except Exception as e:
        logger.exception(f"Error pushing audit log to Loki: {str(e)}")
        return False
