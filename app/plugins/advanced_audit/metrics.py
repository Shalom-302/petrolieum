from prometheus_client import Counter, Gauge, REGISTRY
import time
## Define Prometheus audit-specific metrics

# Counter for total number of audit events
AUDIT_EVENTS_COUNTER = Counter(
    'kaapi_advanced_audit_events_total',
    'Count of audit events created via advanced_audit plugin',
    ['resource', 'action'],
    registry=REGISTRY
)

# Gauge for audit events by resource
AUDIT_EVENTS_BY_RESOURCE = Gauge(
    'kaapi_advanced_audit_events_by_resource',
    'Count of audit events by resource type',
    ['resource'],
    registry=REGISTRY
)

# Gauge for audit events by action
AUDIT_EVENTS_BY_ACTION = Gauge(
    'kaapi_advanced_audit_events_by_action',
    'Count of audit events by action type',
    ['action'],
    registry=REGISTRY
)

# Timestamp of the last audit event
LAST_AUDIT_EVENT_TIMESTAMP = Gauge(
    'kaapi_advanced_audit_last_event_timestamp',
    'Timestamp of the last audit event',
    registry=REGISTRY
)

# Initialize with current timestamp
LAST_AUDIT_EVENT_TIMESTAMP.set(time.time())
