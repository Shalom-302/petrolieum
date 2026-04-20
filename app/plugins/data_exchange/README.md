# Data Exchange Plugin

A powerful data import/export plugin for Kaapi that enables seamless data exchange between your application and various file formats.

## Features

- **Multi-format Support**: Import and export data in CSV, JSON, Excel, and XML formats
- **Data Validation**: Define and apply validation rules to ensure data integrity
- **Scheduling**: Schedule import and export jobs to run automatically at specified intervals
- **Templates**: Create reusable templates for common import/export operations
- **Background Processing**: Handle large datasets efficiently with asynchronous processing
- **Preview & Mapping**: Preview data and map fields before importing
- **Detailed Logging**: Track the status and results of import/export jobs

## API Endpoints

### Import Routes

- `POST /api/data-exchange/import/`: Create a new import job
- `GET /api/data-exchange/import/preview/`: Preview data from an uploaded file
- `GET /api/data-exchange/import/validate/`: Validate data without importing
- `GET /api/data-exchange/import/jobs/`: List all import jobs
- `GET /api/data-exchange/import/jobs/{job_id}/`: Get details of a specific import job
- `DELETE /api/data-exchange/import/jobs/{job_id}/`: Delete an import job

### Export Routes

- `POST /api/data-exchange/export/`: Create a new export job
- `GET /api/data-exchange/export/download/{job_id}/`: Download a completed export file
- `GET /api/data-exchange/export/jobs/`: List all export jobs
- `GET /api/data-exchange/export/jobs/{job_id}/`: Get details of a specific export job
- `DELETE /api/data-exchange/export/jobs/{job_id}/`: Delete an export job
- `GET /api/data-exchange/export/entities/`: List entities available for export

### Template Routes

- `POST /api/data-exchange/templates/`: Create a new template
- `GET /api/data-exchange/templates/`: List all templates
- `GET /api/data-exchange/templates/{template_id}/`: Get details of a specific template
- `PUT /api/data-exchange/templates/{template_id}/`: Update a template
- `DELETE /api/data-exchange/templates/{template_id}/`: Delete a template
- `POST /api/data-exchange/templates/duplicate/{template_id}/`: Duplicate a template
- `GET /api/data-exchange/templates/shared/`: List templates shared by admin users

### Schedule Routes

- `POST /api/data-exchange/schedules/`: Create a new schedule
- `GET /api/data-exchange/schedules/`: List all schedules
- `GET /api/data-exchange/schedules/{schedule_id}/`: Get details of a specific schedule
- `PUT /api/data-exchange/schedules/{schedule_id}/`: Update a schedule
- `DELETE /api/data-exchange/schedules/{schedule_id}/`: Delete a schedule
- `POST /api/data-exchange/schedules/{schedule_id}/activate/`: Activate a schedule
- `POST /api/data-exchange/schedules/{schedule_id}/deactivate/`: Deactivate a schedule
- `GET /api/data-exchange/schedules/{schedule_id}/jobs/`: List jobs associated with a schedule

### Validation Routes

- `POST /api/data-exchange/validation/rules/`: Create a new validation rule
- `GET /api/data-exchange/validation/rules/`: List all validation rules
- `GET /api/data-exchange/validation/rules/{rule_id}/`: Get details of a specific validation rule
- `PUT /api/data-exchange/validation/rules/{rule_id}/`: Update a validation rule
- `DELETE /api/data-exchange/validation/rules/{rule_id}/`: Delete a validation rule
- `GET /api/data-exchange/validation/rule-types/`: List available validation rule types
- `POST /api/data-exchange/validation/validate/`: Validate a sample data value

## Usage Examples

### Importing Data

```python
# Example: Import data from a CSV file
import requests

url = "http://localhost:8000/api/data-exchange/import/"
files = {"file": open("data.csv", "rb")}
data = {
    "format_type": "csv",
    "target_entity": "products",
    "configuration": {
        "delimiter": ",",
        "quotechar": "\"",
        "column_mapping": {
            "Product Name": "name",
            "Product Description": "description",
            "Price": "price"
        }
    }
}

response = requests.post(url, files=files, data=data)
print(response.json())
```

### Exporting Data

```python
# Example: Export data to a JSON file
import requests

url = "http://localhost:8000/api/data-exchange/export/"
data = {
    "format_type": "json",
    "target_entity": "orders",
    "query_filters": {
        "status": "completed",
        "date_from": "2023-01-01",
        "date_to": "2023-12-31"
    },
    "configuration": {
        "indent": 2,
        "as_array": True
    }
}

response = requests.post(url, json=data)
print(response.json())
```

### Creating a Scheduled Export

```python
# Example: Schedule a weekly export
import requests

url = "http://localhost:8000/api/data-exchange/schedules/"
data = {
    "name": "Weekly Sales Report",
    "description": "Export sales data every Monday at 6 AM",
    "frequency": "weekly",
    "parameters": {
        "is_import": False,
        "format_type": "excel",
        "source_path": "sales",
        "target_entity": "weekly_sales_report.xlsx",
        "day_of_week": 0,  # Monday
        "hour": 6,
        "minute": 0,
        "configuration": {
            "sheet_name": "Sales Data"
        }
    }
}

response = requests.post(url, json=data)
print(response.json())
```

## Configuration Options

### CSV Import Options

| Option | Description | Default |
|--------|-------------|---------|
| delimiter | Field delimiter character | , |
| quotechar | Character used for quoting fields | " |
| encoding | File encoding | utf-8 |

### JSON Export Options

| Option | Description | Default |
|--------|-------------|---------|
| indent | Number of spaces for indentation | 2 |
| as_array | Export as array instead of object | True |
| root_key | Root key when exporting as object | data |

### Excel Import/Export Options

| Option | Description | Default |
|--------|-------------|---------|
| sheet_name | Sheet name to read/write | Data |
| header | Row to use for header (import) | 0 |
| index | Include row index (export) | False |

## Validation Rule Types

- **required**: Field must have a value
- **regex**: Field must match a regular expression pattern
- **range**: Numeric value must be within a specified range
- **enum**: Value must be one of a predefined set
- **date**: Value must be a valid date within a range
- **email**: Value must be a valid email address
- **url**: Value must be a valid URL
- **length**: String length must be within a range
- **unique**: Value must be unique in the dataset
- **custom**: Custom validation with Python code

## Schedule Frequencies

- **once**: Run once at a specified date/time
- **hourly**: Run every specified number of hours
- **daily**: Run every day at a specified time
- **weekly**: Run on specified days of the week
- **monthly**: Run on specified days of the month
- **cron**: Run according to a cron expression

## Installation

This plugin is included in the standard Kaapi installation. If you're adding it manually, make sure to:

1. Include the plugin in your app's configuration
2. Run database migrations to create the necessary tables
3. Start the scheduler on application startup

## UI Integration

The Data Exchange plugin integrates seamlessly with the Kaapi UI, providing:

- Modern, glass-effect cards for displaying import/export jobs
- Gradient backgrounds with subtle geometric patterns
- Intuitive flow for mapping and validation
- Interactive previews of data before import/export
- Elegant status indicators with hover effects

## Dependencies

- FastAPI for API endpoints
- SQLAlchemy for database operations
- Pydantic for data validation
- pandas for Excel support
- APScheduler for job scheduling
- dicttoxml for XML support
