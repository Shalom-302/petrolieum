# 🚀 Kaapi Backend

## Overview

The backend Kaapi is a RESTful API built with FastAPI, designed to be extensible via a plugin system. This architecture allows easily adding new features without modifying the core application.

## Quick Start

```bash

# Build all my services
./docker-run.sh build

# Start all services (without monitoring)
./docker-run.sh up

# Start in development mode with API logs visible
./docker-run.sh dev

# Start with complete monitoring (Prometheus, Grafana, etc.)
./docker-run.sh dev --monitoring
```

## 🗃️ Database Initialisation

```bash
# View alembic migrations preview
./kaapi db preview 

# Generate the initialisation migration
./kaapi db generate --message "Initial migration"

# Apply
./kaapi db apply

# Create first admin user
./kaapi auth init-simple

# Init storage
./kaapi storage init
```

## 🗃️ Database Migrations

Kaapi includes a dedicated CLI tool for managing database migrations:

```bash
# View available commands
./kaapi -help

# Database preview
./kaapi db preview

# Generate a new migration
./kaapi db generate --message "Add new tables"

# Apply pending migrations
./kaapi db apply

# Preview changes before generating a migration
./kaapi db preview

# Check pending migrations
./kaapi db pending
```

Migrations are automatically applied at application startup, but you can manually control them with these commands.

## 📊 Monitoring and Observability

The backend Kaapi integrates a complete monitoring stack based on Prometheus, Grafana, Loki, and Alertmanager.

### Monitoring Services

| Service | URL | Description |
|---------|-----|-------------|
| Grafana | http://localhost:3002 | Interface of visualization with modern dashboards (login: admin/admin) |
| Prometheus | http://localhost:9090 | Storage and query of metrics |
| Alertmanager | http://localhost:9093 | Alert management and routing |
| Loki | http://localhost:3100 | Storage and query of logs |

### Activate Monitoring

```bash
# Option 1: Start with monitoring
./docker-run.sh up --monitoring

# Option 2: Use docker-compose files directly
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

### Grafana Dashboards

Several pre-configured dashboards are available in Grafana:

- **API Performance** - Response time, error rate, and endpoint traffic
- **Infrastructure** - CPU, memory, and network usage of containers
- **Logs** - Real-time visualization and search in application logs

### Exposed Metrics

The backend exposes Prometheus metrics at the `/metrics` endpoint, including:

- Counters and histograms for HTTP requests
- Database performance metrics
- Metrics specific to active plugins
- Celery task status

## 🔌 Plugin Architecture

The backend is structured around a plugin system that allows easily extending core functionality:

```
app/
├── plugins/
│   ├── advanced_audit/
│   ├── ai_integration/
│   ├── monitoring/       # ← Monitoring plugin
│   ├── security/
│   └── ...
```

Each plugin can be enabled/disabled via configuration.

## 🛠️ Useful Commands

```bash
# Access the API container shell
./docker-run.sh api

# Display real-time logs
./docker-run.sh logs

# Restart the API container
./docker-run.sh restart-api

# Connect to the database
./docker-run.sh db
```

## 🔐 Environment Variables

The main environment variables are defined in the `.env` file:

- `DATABASE_URL`: Database connection URL
- `REDIS_URL`: Redis connection URL for cache and Celery files
- `SECRET_KEY`: JWT and security key
- `ENVIRONMENT`: Execution environment (development, testing, production)

## 🧪 Tests

```bash
# Run unit tests
docker exec -it kaapi_api pytest

# Run tests with coverage
docker exec -it kaapi_api pytest --cov=app
```