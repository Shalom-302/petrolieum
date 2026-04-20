# Advanced Logging Plugin

The Advanced Logging plugin provides comprehensive logging capabilities for your application, with features designed to enhance debugging, monitoring, and system analysis.

## Features

* **Structured Logging**: All logs are stored in a structured format, making them easily searchable and analyzable.
* **Log Levels**: Supports multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL) for proper categorization.
* **Context Enrichment**: Automatically enriches logs with contextual information like timestamps, service names, and request IDs.
* **Database Storage**: Persists logs to a database for long-term storage and analysis.
* **Grafana Integration**: Compatible with Grafana dashboards for visual log analysis.
* **Performance Optimized**: Asynchronous logging to minimize impact on application performance.

## Use Cases

1. **Application Debugging**:
   * Trace the execution path of complex operations
   * Identify bottlenecks and performance issues
   * Troubleshoot unexpected behavior

2. **Error Monitoring**:
   * Track error frequency and patterns
   * Receive alerts for critical failures
   * Analyze error contexts to determine root causes

3. **User Activity Tracking**:
   * Monitor user actions and behaviors
   * Identify suspicious activities
   * Analyze usage patterns for product improvements

4. **Performance Analysis**:
   * Track response times of key operations
   * Monitor resource utilization
   * Identify slow database queries or API calls

5. **Compliance and Auditing**:
   * Maintain complete audit trails for sensitive operations
   * Support regulatory compliance requirements
   * Provide evidence for security investigations

## Configuration

The Advanced Logging plugin is configurable through environment variables:

```bash
LOG_LEVEL=INFO                       # Minimum log level to record
LOG_FORMAT=json                      # Output format (json or text)
LOG_DB_TABLE=application_logs        # Database table for log storage
LOG_RETENTION_DAYS=30                # Number of days to retain logs
```

## Testing with Sample Data

To verify the functionality of the Advanced Logging plugin and populate its Grafana dashboard with representative data, you can use the included data generation script:

### Prerequisites

Before running the test data generation script, make sure to install the required dependencies:

```bash
# Navigate to the advanced_logging plugin directory
cd app/plugins/advanced_logging

# Install the required dependencies
pip install -r requirements.txt
```

This will install all the necessary packages including:

* `asyncpg` for database operations
* `structlog` and `python-json-logger` for structured logging
* Other required dependencies

### Generate Log Events

The `generate_log_events.py` script creates various sample log entries to populate the advanced-logging dashboard in Grafana:

```bash
# Run from the plugin directory
docker exec -it kaapi-api bash
cd app/plugins/advanced_logging
python generate_log_events.py --db-url "postgresql://postgres:postgres@localhost:5432/kaapi" --count 500
```

Options:

* `--db-url`: PostgreSQL database URL (default: "postgresql://postgres:postgres@localhost:5432/kaapi")
* `--table`: Name of the logs table to use (default: "application_logs")
* `--count`: Number of log events to generate (default: 200)
* `--delay`: Delay between generating events in seconds (default: 0.05)

### Verifying Dashboard Data

After running the script:

1. Open Grafana at <http://localhost:3001>
2. Navigate to the "Advanced Logging" dashboard
3. You should see various visualizations including:

* Log volume by level (ERROR, WARNING, INFO, DEBUG)
* Log trends over time
* Error distribution by service/component
* Log source distribution
* Timeline of critical events

If some panels display "No Data", ensure that:

* The database connection is properly configured
* The logs table has been created and populated
* Prometheus is correctly scraping the metrics

## Integration with Application Code

To use the Advanced Logging plugin in your application code:

```python
from plugins.advanced_logging import logger

# Basic usage
logger.info("User login successful", user_id=user.id)
logger.error("Database connection failed", retry_attempt=3, error=str(e))

# With context manager for operation tracking
with logger.operation_context("user_registration"):
    # All logs within this context will be grouped together
    logger.info("Starting user registration")
    # ... registration code ...
```
