# API Changelog Plugin

## Overview

The API Changelog plugin provides a system for tracking API changes and generating comprehensive changelogs. Rather than maintaining multiple active API versions simultaneously, this plugin focuses on documenting the evolution of your API over time.

## Features

- **API Change Tracking**: Record different changes to your API (e.g., additions, modifications, removals)
- **Endpoint Documentation**: Document API endpoints for each change
- **Changelog Generation**: Generate comprehensive changelogs for each change
- **Beautiful Modern UI**: View API changes with a stunning glassmorphism design

## Installation

The API Changelog plugin is pre-installed with Kaapi. No additional installation steps are required.

## Usage

### Tracking API Changes

Each time you make significant changes to your API, you can create a new change:

```python
from app.plugins.api_changelog.crud import create_api_change
from app.dependencies import get_db

# Get database session
db = next(get_db())

# Create new change
try:
    new_change = create_api_change(
        db,
        change_type="added",
        description="Added user management features",
        endpoint_path="/users",
        details={"request_model": "UserCreate", "response_model": "UserResponse"}
    )
finally:
    db.close()
```

### Generating Changelogs

You can generate a changelog for a specific change:

```python
from app.plugins.api_changelog.integration import generate_changelog
from app.dependencies import get_db

# Get database session
db = next(get_db())

try:
    # Get the change
    from app.plugins.api_changelog.utils.database import get_api_change_by_id
    change = get_api_change_by_id(db, new_change.id)
    
    # Generate changelog
    changelog = generate_changelog(change_id=change.id, db=db)
    
    # Use the changelog in your application
    print(changelog)
finally:
    db.close()
```

## Web Interface

The API Changelog plugin provides a beautiful web interface for viewing API changes and changelogs. The interface features:

### Modern Design Elements

- **Glassmorphism Cards**: Each change and endpoint is displayed in a stunning glassmorphism card with subtle transparency and blur effects
- **Gradient Backgrounds**: Blue/indigo gradient backgrounds with subtle geometric shapes enhance the visual experience
- **Interactive Elements**: "See more" buttons with elegant hover effects for exploring change details
- **Cohesive Styling**: All elements follow a consistent, modern design language

### Interface Sections

1. **Changes Overview**: View all API changes in chronological order
2. **Change Details**: See detailed information about a specific change
3. **Changelog View**: View changes with visual indicators for additions, modifications, and removals
4. **Endpoint Explorer**: Browse all endpoints in the current change

## API Routes

The plugin provides the following API routes:

### Changes

- `GET /plugins/api-changelog/changes`: List all API changes
- `POST /plugins/api-changelog/changes`: Create a new API change (admin only)
- `PUT /plugins/api-changelog/changes/{change_id}`: Update an API change (admin only)
- `DELETE /plugins/api-changelog/changes/{change_id}`: Delete an API change (admin only)

### Endpoints

- `GET /plugins/api-changelog/endpoints`: List all API endpoints in the current change
- `POST /plugins/api-changelog/endpoints`: Register a new API endpoint (admin only)

### Changelogs

- `GET /plugins/api-changelog/changelog`: Generate a complete changelog
- `GET /plugins/api-changelog/changes/{change_id}/changelog`: Generate a changelog for a specific change

## Integration with Main Application

The API Changelog plugin is integrated with the main Kaapi application through the `register_with_main_app` function in the `integration.py` module. This function sets up the necessary middleware and event handlers.

## Customization

You can customize the plugin by modifying the following files:

- `app/plugins/api_changelog/main.py`: Main router and endpoints
- `app/plugins/api_changelog/models.py`: Database models
- `app/plugins/api_changelog/schemas.py`: Pydantic schemas
- `app/plugins/api_changelog/crud.py`: CRUD operations
- `app/plugins/api_changelog/integration.py`: Integration with main app
- `app/plugins/api_changelog/utils`: Utility functions

## Contributing

Contributions to the API Changelog plugin are welcome. Please feel free to submit issues or pull requests.

## Testing and Dashboard Visualization

To test the API versioning functionality and populate related Grafana dashboards with representative data, you can use the included data generation script:

### Prerequisites

Before running the test data generation script, make sure to install the required dependencies:

```bash
# Navigate to the api_versioning plugin directory
cd app/plugins/api_versioning

# Install the required dependencies
pip install -r requirements.txt
```

This will install all the necessary packages including:

* `aiohttp` for generating HTTP requests
* Other required dependencies

### Generate API Traffic

The `generate_api_traffic.py` script creates sample API requests against various endpoints to populate API-related dashboards in Grafana:

```bash
# Run from the plugin directory
python generate_api_traffic.py --base-url "http://localhost:8000" --duration 60 --requests-per-second 10
```

Options:
- `--base-url`: Base URL for the API (default: "http://localhost:8000")
- `--duration`: Duration of the test in seconds (default: 60)
- `--requests-per-second`: Number of requests per second (default: 5)
- `--auth-token`: Optional authentication token for protected endpoints

### Verifying Dashboard Data

After running the script:

1. Open Grafana at http://localhost:3001
2. Navigate to the "API Performance" dashboard
3. You should see various visualizations including:
   - Request volume by endpoint
   - Response time distribution
   - Success/failure rates
   - Version usage statistics
   - Request methods distribution

If some panels display "No Data", ensure that:
- The API server is running and accessible
- The endpoints being tested exist and are properly configured
- Prometheus is correctly scraping the metrics
