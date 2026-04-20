# Advanced Audit Plugin

The Advanced Audit plugin provides comprehensive tracking of user actions and system events within your application, offering detailed insights into who did what and when.

## Features

* Tracks user actions with timestamps and metadata
* Records resource access and modifications
* Provides detailed audit logs for compliance purposes
* Includes Grafana dashboards for visualization
* Supports filtering and searching of audit events

## Example Use Cases

Below are several example use cases to illustrate the benefits of the Advanced Audit plugin:

1. **User Activity Tracking**

   * **Example:** Log when a user account is created, updated, or deleted.
   * **Use Case:** Helps administrators track and review changes to user records, which is useful for security audits and troubleshooting user-related issues.

1. **Content Management Auditing**

   * **Example:** Record events such as when a blog post or article is published, updated, or removed.
   * **Use Case:** Provides a historical trail of content changes, allowing editors to revert undesirable changes and monitor editorial activity.

1. **Data Modification Monitoring**

   * **Example:** Capture changes to sensitive data in an e-commerce platform (e.g., order status, pricing changes, inventory updates).
   * **Use Case:** Assists in identifying unauthorized modifications, ensuring data integrity, and complying with regulations such as PCI DSS.

1. **Administrative Actions**

   * **Example:** Log actions performed by administrators such as role changes, configuration updates, or system settings adjustments.
   * **Use Case:** Enhances accountability by creating an audit trail of critical changes, which is essential for compliance and forensic investigations.

1. **Security and Compliance**

   * **Example:** Track security-related events like password changes, multi-factor authentication (MFA) setup, or changes in permissions.
   * **Use Case:** Supports compliance with security standards by ensuring all critical security actions are recorded for review.

1. **Integration and Workflow Triggers**

   * **Example:** When a specific event (like an order cancellation) is logged, trigger external notifications or workflows.
   * **Use Case:** Enables automated downstream processes such as alerting customer service, updating external inventory systems, or generating reports.

1. **Change Management**

   * **Example:** Maintain logs for any changes made to configuration files, feature toggles, or application policies.
   * **Use Case:** Provides transparency and helps troubleshoot issues by understanding when and why a particular change was made.

These examples illustrate how the Advanced Audit plugin can serve various needs—from basic tracking of user and content changes to more advanced security and compliance functions. By integrating this plugin, administrators and auditors gain visibility into the application's operations and user activities, thereby enhancing accountability and facilitating troubleshooting and compliance efforts.

## Prerequisites

Before using the Advanced Audit plugin, make sure you have the following prerequisites installed:

* Docker and Docker Compose
* Python 3.8 or higher

## Installation

The Advanced Audit plugin is included in the default Kaapi installation. To ensure all dependencies are installed:

```bash
# Access the API container shell
docker exec -it kaapi-api bash

# Navigate to the advanced audit plugin directory
cd app/plugins/advanced_audit

# Install the required dependencies
pip install -r requirements.txt
```

This will install all the necessary packages including:

* `asyncpg` for database operations
* `structlog` and `python-json-logger` for structured logging
* Other required dependencies

## Generate Audit Events

To test the Advanced Audit dashboard with simulated events, use Docker to run the script inside the API container:

```bash
# Access the API container shell
docker exec -it kaapi-api bash

# Navigate to the advanced audit plugin directory
cd app/plugins/advanced_audit

# Generate audit events
python generate_audit_events.py
```

Options:

* `--db-url`: PostgreSQL database URL (default: "postgresql://postgres:postgres@postgres:5432/kaapi")
* `--table`: Name of the audit events table to use (default: "audit_events")
* `--count`: Number of audit events to generate (default: 100)
* `--delay`: Delay between generating events in seconds (default: 0.1)

## Verifying Dashboard Data

To verify the data in Grafana:

1. Open Grafana at [http://localhost:3001](http://localhost:3001)
2. Navigate to the "Advanced Audit" dashboard
3. You should see various visualizations including:

   * Audit events by user
   * Actions frequency
   * Events by resource type
   * Status distribution (success/failure)
   * Timeline of events

If some panels display "No Data", ensure that:

* The database connection is properly configured
* The audit events table has been created and populated
* Prometheus is correctly scraping the metrics

## Troubleshooting

If you encounter issues with the Advanced Audit plugin:

* Check if the database is accessible from the API container
* Verify that the audit events table exists in the database
* Check application logs for any audit-related errors
* Ensure that the audit plugin is enabled in your configuration
