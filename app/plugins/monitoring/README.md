# Monitoring Plugin

This plugin provides comprehensive monitoring capabilities for your FastAPI application.

## Features

* **Prometheus Integration**: Exports metrics in Prometheus format
* **Performance Metrics**: Tracks request duration, database query time, and more
* **Health Checks**: Includes endpoints for checking system health
* **Customizable Dashboard**: Pre-configured Grafana dashboard for visualization
* **Low Overhead**: Minimal impact on application performance
* **Alert Management**: Integrated alerting system with multi-channel notifications

## Installation

The monitoring plugin is pre-installed with Kaapi. No additional installation steps are required.

## Usage

### Prometheus Metrics

The plugin automatically collects metrics for each endpoint. Access the metrics at:

```bash
curl http://localhost:8000/metrics
```

### Health Check

```bash
curl http://localhost:8000/health
```

Response:

```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime": "10h 30m 5s"
}
```

### Grafana Integration

1. Access Grafana at [http://localhost:3001](http://localhost:3001)
2. Log in with the default credentials (admin/admin)
3. Navigate to Dashboards > Browse
4. Select the "Application Monitoring" dashboard

### Generate Database Load

To test the monitoring dashboard with simulated database load, you need to use Docker to run the script inside the API container:

```bash
# Access the API container shell
docker exec -it kaapi-api bash

# Navigate to the monitoring plugin directory
cd app/plugins/monitoring

# Generate database load
python generate_db_load.py --duration 60 --db-url "postgresql://postgres:postgres@kaapi-db:5432/kaapi"
```

Options:

* `--db-url`: PostgreSQL database URL (default: "postgresql://postgres:postgres@localhost:5432/kaapi")
  * Note: When running inside Docker, use `kaapi-db` instead of `localhost` as the database host
* `--table`: Name of the table to use for test data (default varies)
* `--duration`: Duration in seconds to generate load (default: 60)
* `--connections`: Number of concurrent connections to use (default: 10)
* `--delay`: Delay in seconds between operations (default: 0.5)

### Generate HTTP Traffic

To test the monitoring dashboard with simulated HTTP traffic, use Docker to run the script inside the API container:

```bash
# Access the API container shell
docker exec -it kaapi-api bash

# Navigate to the monitoring plugin directory
cd app/plugins/monitoring

# Generate HTTP traffic
python generate_http_traffic.py --duration 60 --requests-per-second 10
```

Options:

* `--base-url`: Base URL for the API (default: "[http://localhost:8000](http://localhost:8000)")
* `--duration`: Duration in seconds to generate traffic (default: 60)
* `--requests-per-second`: Number of requests per second (default: 5)

### Verifying Dashboard Data

After running both scripts:

1. Open Grafana at [http://localhost:3001](http://localhost:3001)
2. Navigate to the "Application Monitoring" dashboard
3. You should see data populating various panels

## Configuration

Configure the plugin via environment variables:

```bash
PROMETHEUS_MULTIPROC_DIR=/tmp  # Required for multi-process setups
METRICS_PREFIX=app_            # Prefix for all metrics
ENABLE_DATABASE_METRICS=true   # Track database performance
ENABLE_REQUEST_METRICS=true    # Track HTTP request performance
```

## Grafana Alerts

The monitoring plugin includes a pre-configured AlertManager integration that allows you to set up and manage alerts based on the metrics collected by your application.

### Setting Up Alerts in Grafana

1. Access Grafana at [http://localhost:3001](http://localhost:3001)
2. Navigate to "Alerting" in the left sidebar
3. Click on "Alert Rules" to create a new alert
4. Configure the alert with the following settings:
   * **Rule Name**: Provide a descriptive name (e.g., "High API Error Rate")
   * **Data Source**: Select "Prometheus"
   * **Expression**: Enter a PromQL query (e.g., `rate(http_requests_total{status_code=~"5.."}[5m]) > 0.1`)
   * **Evaluation Interval**: How often the alert should be evaluated (e.g., "1m")
   * **For**: Duration the condition must be met before alerting (e.g., "5m")
   * **Labels**: Add `severity: critical` for critical alerts or `severity: warning` for warnings
   * **Annotations**: Add descriptive information to include in notifications

### Visualizing Alerts in Grafana

To view and monitor alerts in Grafana:

1. Access Grafana at [http://localhost:3001](http://localhost:3001)
2. Navigate to "Alerting" in the left sidebar
3. Click on "Alert Rules" to see all configured alert rules
4. Use the "State" filter to view alerts by their current state:
   * **Normal**: Alert conditions are not met
   * **Pending**: Alert conditions are met but haven't been firing for the required duration
   * **Alerting**: Alert is actively firing
   * **No Data**: The alert query returned no data
   * **Error**: There was an error while evaluating the alert

#### Viewing Alert History

To view the history of alert state changes:

1. Go to "Alerting" > "Alert Rules" in the Grafana UI
2. Click on a specific alert rule
3. Navigate to the "State History" tab to see when the alert changed states
4. The history includes:
   * When the alert started firing
   * When it was resolved
   * Duration of the alert
   * Values that triggered the alert

#### Adding Alerts to Dashboards

You can also visualize alerts directly on your monitoring dashboards:

1. Open the "Application Monitoring" dashboard
2. Edit a panel where you want to show alert thresholds
3. In the panel edit mode, go to the "Alert" tab
4. Click "Create Alert" to add a new alert rule, or select an existing one
5. The alert thresholds will be visualized on the panel with colored lines

#### Creating a Test Alert for Quick Demonstration

If you want to see an alert in action immediately, you can create a quick test alert with minimal waiting time:

1. Go to Alerting > Alert Rules in Grafana
2. Click "New alert rule"
3. Configure the new rule with these settings:
   * Rule name: "Quick Test Alert"
   * For Grafana managed alerts, use:
     * Data source: Prometheus
     * Expression: `sum(rate(kaapi_http_requests_total{status=~"4.."}[1m])) > 0`
     * This will trigger as soon as any 4xx errors are detected
   * Set "Evaluate every" to "10s" (the minimum)
   * Set "For" to "0m" (trigger immediately)
   * Add the label `severity: warning`
   * Add a summary annotation: "Test alert for 4xx errors"
4. Save the rule

Once configured, run the HTTP traffic generator again:

```bash
docker exec kaapi-api bash -c "cd app/plugins/monitoring && python generate_http_traffic.py --duration 60 --requests-per-second 50 --base-url 'http://localhost:8000'"
```

This should trigger your test alert within seconds.

> **Important Note About Metrics Names**: The Kaapi application prefixes all its metrics with `kaapi_`. When creating alert rules, be sure to use metrics names like `kaapi_http_requests_total` and `kaapi_http_request_processing_seconds_bucket` rather than the generic names like `http_requests_total`.

#### Alert Overview Dashboard

A pre-configured "Alert Overview" dashboard is available to provide a centralized view of all alerts:

1. Navigate to Dashboards > Browse
2. Select the "Alert Overview" dashboard
3. This dashboard displays:
   * Total number of alerts by state
   * Alert history timeline
   * Top firing alerts
   * Alert groups by severity
   * Alert notifications history

If this dashboard isn't available, you can create it:

1. Import a new dashboard
2. Use the dashboard ID `13639` (Grafana Alert Overview)
3. Select your Prometheus data source

### Alert Notification Channels

Alerts are routed based on the configuration in `alertmanager.yml`. The current configuration includes:

* **Email Notifications**: Default alert channel for normal severity alerts
* **PagerDuty**: For critical severity alerts that require immediate attention
* **Slack Notifications**: For warning severity alerts
* **SOC Team**: Special channel for security-related alerts (intrusion detection)
* **DevOps Team**: For specific crypto health check failures

### Configuring Email Notifications for Alerts

To receive alert notifications by email when an alert is triggered, follow these steps:

1. **Update the AlertManager Configuration**:

   Edit the `alertmanager.yml` file to configure your email settings:

   ```yaml
   receivers:
     - name: 'email-notifications'
       email_configs:
         - to: 'your-email@example.com'           # Change to your email address
           from: 'alertmanager@yourdomain.com'    # Change to a valid sender address
           smarthost: 'smtp.yourdomain.com:587'   # Your SMTP server and port
           username: 'your-smtp-username'    # SMTP authentication username
           auth_identity: 'your-smtp-username'    # Usually same as username
           auth_password: 'your-smtp-password'    # SMTP authentication password
           send_resolved: true                    # Send a resolution notification
   ```

2. **Configure SMTP Settings**:

   For Gmail as an example:

   ```yaml
   smarthost: 'smtp.gmail.com:587'
   username: 'your-gmail@gmail.com'
   auth_identity: 'your-gmail@gmail.com'
   auth_password: 'your-app-password'  # Use an App Password if 2FA is enabled
   ```

3. **Restart AlertManager**:

   ```bash
   docker restart alertmanager
   ```

4. **Test the Email Configuration**:

   Trigger a test alert using the HTTP traffic generator and verify that you receive an email notification.

> **Security Note**: Never commit SMTP credentials to your repository. For production environments, consider using Docker secrets or environment variables to inject sensitive credentials.
> **Gmail Users**: If you're using Gmail, you might need to create an "App Password" in your Google Account security settings if you have 2-factor authentication enabled.

### Custom Alert Routes

To customize how alerts are routed:

1. Edit the `/app/plugins/monitoring/alertmanager.yml` file
2. Modify existing routes or add new ones based on alert labels
3. Configure receivers with appropriate notification methods

Example route configuration:

```yaml
route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 3h
  receiver: 'email-notifications'

  routes:
    - match:
        severity: 'critical'
      receiver: 'pagerduty'
```

### Testing Alerts

You can trigger test alerts by:

1. Running the load generation scripts with high values:

   ```bash
   # Generate high database load to trigger alerts
   docker exec kaapi-api bash -c "cd app/plugins/monitoring && python generate_db_load.py --duration 60 --connections 50 --delay 0.1 --db-url 'postgresql://postgres:postgres@kaapi-db:5432/kaapi'"
   
   # Generate high HTTP traffic to trigger alerts (more requests = more errors)
   docker exec kaapi-api bash -c "cd app/plugins/monitoring && python generate_http_traffic.py --duration 60 --requests-per-second 50"
   ```

2. Or manually using the Grafana UI:
   * Go to Alerting > Alert Rules
   * Find your alert rule
   * Click "Test Rule" to simulate an alert firing

### Alert Manager API Integration

The plugin includes an `AlertManager` class that can be used to programmatically send alerts:

```python
from plugins.monitoring.alert_manager import AlertManager

# Initialize with configuration
alert_manager = AlertManager(config)

# Send an alert
await alert_manager.send_alert(
    message="Database connection pool exhausted",
    priority="high"
)
```

## Troubleshooting

### No Data in Grafana

If you don't see data in Grafana:

* Verify Prometheus is running (`docker ps`)
* Check that metrics are being exposed (`curl [http://localhost:8000/metrics](http://localhost:8000/metrics)`)
* Ensure Prometheus is scraping your application (`curl [http://localhost:9090/targets](http://localhost:9090/targets)`)
* Check Grafana data source configuration

### Common Issues

* Missing data: Increase the frequency of metrics collection
* High cardinality warnings: Reduce the number of unique label combinations
* Performance impact: Adjust collection frequency or disable high-overhead metrics
